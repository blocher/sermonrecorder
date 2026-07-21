from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Sermon
from .serializers import (
    LibrarySearchQuerySerializer,
    SermonDetailSerializer,
    SermonSerializer,
)
from .tasks import enqueue_sermon_processing

UPLOAD_METADATA_FIELDS = ("source_draft_id", "captured_at", "duration_seconds")


class SermonViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (permissions.IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = SermonSerializer

    def get_queryset(self):
        queryset = Sermon.objects.filter(owner=self.request.user).select_related(
            "church",
            "preacher",
        )
        if self.action == "list":
            query_serializer = LibrarySearchQuerySerializer(
                data=self.request.query_params
            )
            query_serializer.is_valid(raise_exception=True)
            queryset = self._filter_library(
                queryset,
                query_serializer.validated_data,
            )
            queryset = queryset.prefetch_related("study_artifacts", "tag_suggestions")
        elif self.action == "retrieve":
            queryset = queryset.select_related("transcript").prefetch_related(
                "study_artifacts",
                "scripture_references",
                "tag_suggestions",
                "related_sermons__related_sermon",
                "reflections",
            )
        return queryset

    def _filter_library(self, queryset, query):
        search = query.get("search", "").strip()
        for term in search.split():
            term_query = (
                Q(transcript__text__icontains=term)
                | Q(study_artifacts__content__icontains=term)
                | Q(scripture_references__book__icontains=term)
                | Q(tag_suggestions__name__icontains=term)
                | Q(reflections__prompt__icontains=term)
                | Q(reflections__content__icontains=term)
                | Q(related_sermons__reason__icontains=term)
                | Q(church__name__icontains=term)
                | Q(church__address__icontains=term)
                | Q(preacher__name__icontains=term)
                | Q(occasion_kind__icontains=term)
                | Q(liturgical_day__icontains=term)
            )
            if term.isdecimal():
                number = int(term)
                term_query |= (
                    Q(scripture_references__chapter_start=number)
                    | Q(scripture_references__verse_start=number)
                    | Q(scripture_references__chapter_end=number)
                    | Q(scripture_references__verse_end=number)
                )
            queryset = queryset.filter(term_query)

        if church := query.get("church"):
            queryset = queryset.filter(church_id=church)
        if preacher := query.get("preacher"):
            queryset = queryset.filter(preacher_id=preacher)
        if occasion := query.get("occasion"):
            queryset = queryset.filter(occasion_kind=occasion)
        if tag := query.get("tag"):
            queryset = queryset.filter(
                tag_suggestions__normalized_name=" ".join(tag.split()).casefold()
            )
        if date_from := query.get("date_from"):
            queryset = queryset.filter(captured_at__date__gte=date_from)
        if date_to := query.get("date_to"):
            queryset = queryset.filter(captured_at__date__lte=date_to)
        if processing_status := query.get("processing_status"):
            queryset = queryset.filter(processing_status=processing_status)

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SermonDetailSerializer
        return SermonSerializer

    def create(self, request, *args, **kwargs):
        source_draft_id = request.data.get(
            "source_draft_id"
        ) or request.query_params.get("source_draft_id")
        if source_draft_id:
            existing = (
                self.get_queryset().filter(source_draft_id=source_draft_id).first()
            )
            if existing:
                return Response(
                    self.get_serializer(existing).data, status=status.HTTP_200_OK
                )

        data = request.data.copy()
        for field in UPLOAD_METADATA_FIELDS:
            if field not in data and field in request.query_params:
                data[field] = request.query_params[field]

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        sermon = serializer.save(owner=request.user)
        transaction.on_commit(lambda: enqueue_sermon_processing(str(sermon.id)))
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )
