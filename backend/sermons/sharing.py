from urllib.parse import quote
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.http import Http404
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Sermon, ShareLink
from .private_audio import sermon_audio_response
from .serializers import PublicSharedSermonSerializer

SHARE_TOKEN_SALT = "pewcorder.unlisted-sermon-share"


def _share_token(share_link: ShareLink) -> str:
    return signing.Signer(salt=SHARE_TOKEN_SALT).sign_object(
        str(share_link.id),
        compress=True,
    )


def _share_payload(share_link: ShareLink) -> dict[str, str]:
    token = _share_token(share_link)
    public_base_url = settings.PEWCORDER_PUBLIC_WEB_URL.rstrip("/")
    return {
        "url": f"{public_base_url}/share/{quote(token, safe='')}",
        "created_at": share_link.created_at.isoformat(),
    }


def _owned_ready_sermon(request: Request, sermon_id: UUID) -> Sermon:
    return get_object_or_404(
        Sermon,
        id=sermon_id,
        owner=request.user,
        processing_status=Sermon.ProcessingStatus.READY,
    )


def _active_share_link(token: str) -> ShareLink:
    try:
        share_link_id = signing.Signer(salt=SHARE_TOKEN_SALT).unsign_object(token)
        share_link_id = UUID(share_link_id)
    except (signing.BadSignature, TypeError, ValueError) as error:
        raise NotFound() from error

    return get_object_or_404(
        ShareLink.objects.select_related("sermon").prefetch_related(
            "sermon__study_artifacts",
            "sermon__scripture_references",
            "sermon__tag_suggestions",
        ),
        id=share_link_id,
        revoked_at__isnull=True,
        sermon__processing_status=Sermon.ProcessingStatus.READY,
    )


class SermonShareLinkView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        share_link = sermon.share_links.filter(revoked_at__isnull=True).first()
        return Response(
            {"share_link": _share_payload(share_link) if share_link else None}
        )

    def post(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        share_link = sermon.share_links.filter(revoked_at__isnull=True).first()
        created = share_link is None
        if share_link is None:
            try:
                with transaction.atomic():
                    share_link = ShareLink.objects.create(sermon=sermon)
            except IntegrityError:
                share_link = ShareLink.objects.get(
                    sermon=sermon,
                    revoked_at__isnull=True,
                )
                created = False

        return Response(
            _share_payload(share_link),
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request: Request, sermon_id: UUID) -> Response:
        sermon = _owned_ready_sermon(request, sermon_id)
        sermon.share_links.filter(revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicSharedSermonView(APIView):
    authentication_classes = ()
    permission_classes = (permissions.AllowAny,)

    def get(self, request: Request, token: str) -> Response:
        share_link = _active_share_link(token)
        serializer = PublicSharedSermonSerializer(
            share_link.sermon,
            context={"request": request, "share_token": token},
        )
        response = Response(serializer.data)
        response["Cache-Control"] = "private, no-store"
        return response


@require_GET
def shared_sermon_audio(request: HttpRequest, token: str) -> HttpResponse:
    try:
        share_link = _active_share_link(token)
    except (Http404, NotFound):
        return HttpResponse(status=404)
    response = sermon_audio_response(request, share_link.sermon)
    response["Cache-Control"] = "private, no-store"
    return response
