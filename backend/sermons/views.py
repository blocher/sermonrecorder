from django.db import transaction
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Sermon
from .serializers import SermonDetailSerializer, SermonSerializer
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
        queryset = Sermon.objects.filter(owner=self.request.user)
        if self.action == "list":
            queryset = queryset.prefetch_related("study_artifacts", "tag_suggestions")
        elif self.action == "retrieve":
            queryset = queryset.select_related("transcript").prefetch_related(
                "study_artifacts",
                "scripture_references",
                "tag_suggestions",
                "related_sermons__related_sermon",
            )
        return queryset

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
