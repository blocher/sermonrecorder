from smtplib import SMTPException
from uuid import UUID

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import SavedRecipient

from .models import Sermon, StudyArtifact
from .sharing import ensure_share_link, share_link_payload


class SermonEmailSerializer(serializers.Serializer):
    recipient_ids = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
        max_length=20,
    )
    subject = serializers.CharField(max_length=180)
    note = serializers.CharField(max_length=5_000, allow_blank=True)

    def validate_recipient_ids(self, recipient_ids: list[UUID]) -> list[UUID]:
        if len(set(recipient_ids)) != len(recipient_ids):
            raise serializers.ValidationError("Choose each saved recipient once.")
        return recipient_ids

    def validate_subject(self, subject: str) -> str:
        subject = subject.strip()
        if "\r" in subject or "\n" in subject:
            raise serializers.ValidationError("The subject must stay on one line.")
        return subject


def _short_summary(sermon: Sermon) -> str:
    artifact = next(
        (
            artifact
            for artifact in sermon.study_artifacts.all()
            if artifact.kind == StudyArtifact.Kind.SHORT_SUMMARY
        ),
        None,
    )
    return artifact.content if artifact else ""


class SermonEmailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request: Request, sermon_id: UUID) -> Response:
        sermon = get_object_or_404(
            Sermon.objects.prefetch_related("study_artifacts"),
            id=sermon_id,
            owner=request.user,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        serializer = SermonEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipient_ids = serializer.validated_data["recipient_ids"]
        recipients = list(
            SavedRecipient.objects.filter(
                owner=request.user,
                id__in=recipient_ids,
            )
        )
        if len(recipients) != len(recipient_ids):
            return Response(
                {"recipient_ids": ["Choose recipients saved to your account."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        share_link, _ = ensure_share_link(sermon)
        share_url = share_link_payload(share_link)["url"]
        summary = _short_summary(sermon)
        subject = serializer.validated_data["subject"]
        note = serializer.validated_data["note"]
        messages = [
            self._message(
                recipient=recipient,
                sermon=sermon,
                subject=subject,
                note=note,
                summary=summary,
                share_url=share_url,
                reply_to=request.user.email,
            )
            for recipient in recipients
        ]

        try:
            sent_count = get_connection().send_messages(messages)
        except (OSError, SMTPException):
            return Response(
                {"detail": "The email provider could not accept this handout."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if sent_count != len(messages):
            return Response(
                {"detail": "Not every email was accepted. Try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "sent_count": sent_count,
                "share_url": share_url,
            }
        )

    def _message(
        self,
        *,
        recipient: SavedRecipient,
        sermon: Sermon,
        subject: str,
        note: str,
        summary: str,
        share_url: str,
        reply_to: str,
    ) -> EmailMultiAlternatives:
        context = {
            "recipient": recipient,
            "sermon": sermon,
            "subject": subject,
            "note": note,
            "summary": summary,
            "share_url": share_url,
            "duration_minutes": max(1, round(sermon.duration_seconds / 60)),
        }
        body = render_to_string("sermons/sermon_email.txt", context)
        html = render_to_string("sermons/sermon_email.html", context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
            reply_to=[reply_to],
        )
        message.attach_alternative(html, "text/html")
        return message
