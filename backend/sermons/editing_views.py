from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Reflection,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)
from .serializers import (
    ReflectionSerializer,
    ScriptureReferenceSerializer,
    ScriptureReferencesEditSerializer,
    StudyArtifactEditSerializer,
    TagsEditSerializer,
    TranscriptEditSerializer,
    TranscriptSerializer,
)


def _owned_ready_sermon(request: Request, sermon_id: UUID) -> Sermon:
    return get_object_or_404(
        Sermon,
        id=sermon_id,
        owner=request.user,
        processing_status=Sermon.ProcessingStatus.READY,
    )


class StudyArtifactDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self, request: Request, sermon_id: UUID, kind: str) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        artifact = get_object_or_404(
            StudyArtifact,
            sermon=sermon,
            kind=kind,
        )
        serializer = StudyArtifactEditSerializer(
            artifact,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(edited_at=timezone.now())
        return Response(serializer.data)


class TranscriptDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        transcript = get_object_or_404(Transcript, sermon=sermon)
        serializer = TranscriptEditSerializer(
            data=request.data,
            context={"transcript": transcript},
        )
        serializer.is_valid(raise_exception=True)
        transcript.segments = serializer.validated_data["segments"]
        transcript.text = " ".join(segment["text"] for segment in transcript.segments)
        transcript.save(update_fields=("segments", "text", "updated_at"))
        return Response(TranscriptSerializer(transcript).data)


class TagsDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic
    def put(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        serializer = TagsEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tags = serializer.validated_data["tags"]
        sermon.tag_suggestions.all().delete()
        TagSuggestion.objects.bulk_create(
            TagSuggestion(
                sermon=sermon,
                name=tag["name"],
                normalized_name=tag["normalized_name"],
                sort_order=index,
            )
            for index, tag in enumerate(tags)
        )
        return Response({"tags": [tag["name"] for tag in tags]})


class ScriptureReferencesDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @transaction.atomic
    def put(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        serializer = ScriptureReferencesEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        references = serializer.validated_data["scripture_references"]
        sermon.scripture_references.all().delete()
        ScriptureReference.objects.bulk_create(
            ScriptureReference(
                sermon=sermon,
                book=reference["book"],
                chapter_start=reference["chapter_start"],
                verse_start=reference["verse_start"],
                chapter_end=reference["chapter_end"],
                verse_end=reference["verse_end"],
                sort_order=index,
            )
            for index, reference in enumerate(references)
        )
        saved = sermon.scripture_references.all()
        return Response(
            {
                "scripture_references": ScriptureReferenceSerializer(
                    saved,
                    many=True,
                ).data
            }
        )


class ReflectionListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        serializer = ReflectionSerializer(sermon.reflections.all(), many=True)
        return Response(serializer.data)

    def post(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        serializer = ReflectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(sermon=sermon)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReflectionDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(
        self,
        request: Request,
        sermon_id: UUID,
        reflection_id: UUID,
    ) -> Response:
        reflection = self._reflection(request, sermon_id, reflection_id)
        serializer = ReflectionSerializer(
            reflection,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(
        self,
        request: Request,
        sermon_id: UUID,
        reflection_id: UUID,
    ) -> Response:
        reflection = self._reflection(request, sermon_id, reflection_id)
        reflection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _reflection(
        self,
        request: Request,
        sermon_id: UUID,
        reflection_id: UUID,
    ) -> Reflection:
        return get_object_or_404(
            Reflection,
            id=reflection_id,
            sermon_id=sermon_id,
            sermon__owner=request.user,
            sermon__processing_status=Sermon.ProcessingStatus.READY,
        )
