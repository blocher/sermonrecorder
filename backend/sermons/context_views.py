from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Church, Preacher, Sermon
from .serializers import (
    ChurchSerializer,
    PreacherSerializer,
    SermonContextUpdateSerializer,
    SermonSerializer,
)


class ChurchListCreateView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChurchSerializer

    def get_queryset(self):
        return Church.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ChurchDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = ChurchSerializer

    def get_queryset(self):
        return Church.objects.filter(owner=self.request.user)


class PreacherListCreateView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PreacherSerializer

    def get_queryset(self):
        return Preacher.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class PreacherDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = PreacherSerializer

    def get_queryset(self):
        return Preacher.objects.filter(owner=self.request.user)


class SermonContextView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def patch(self, request: Request, sermon_id: UUID) -> Response:
        sermon = get_object_or_404(
            Sermon.objects.select_related("church", "preacher"),
            id=sermon_id,
            owner=request.user,
        )
        serializer = SermonContextUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        update_fields = []

        if "church_id" in values:
            sermon.church = self._church(request, values["church_id"])
            update_fields.append("church")
        if "preacher_id" in values:
            sermon.preacher = self._preacher(request, values["preacher_id"])
            update_fields.append("preacher")
        for field in ("occasion_kind", "liturgical_day"):
            if field in values:
                setattr(sermon, field, values[field])
                update_fields.append(field)

        if update_fields:
            sermon.save(update_fields=(*update_fields, "updated_at"))
        return Response(SermonSerializer(sermon, context={"request": request}).data)

    def _church(self, request: Request, church_id: UUID | None) -> Church | None:
        if church_id is None:
            return None
        return get_object_or_404(Church, id=church_id, owner=request.user)

    def _preacher(self, request: Request, preacher_id: UUID | None) -> Preacher | None:
        if preacher_id is None:
            return None
        return get_object_or_404(Preacher, id=preacher_id, owner=request.user)
