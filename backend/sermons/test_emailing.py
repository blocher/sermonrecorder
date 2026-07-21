from tempfile import TemporaryDirectory

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import SavedRecipient, User

from .models import Church, Preacher, Reflection, Sermon, ShareLink, StudyArtifact


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Pewcorder <share@pewcorder.test>",
    PEWCORDER_PUBLIC_WEB_URL="https://listen.example.test",
)
class SermonEmailTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(
            email="email-owner@example.com",
            display_name="Email Owner",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="email-other@example.com",
            password="safe-test-password",
        )
        church = Church.objects.create(
            owner=self.owner,
            name="Grace Parish",
        )
        preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.sermon = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="email-ready-sermon",
            captured_at=timezone.now(),
            duration_seconds=1_800,
            audio=SimpleUploadedFile(
                "sermon.m4a",
                b"email-sermon-audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=len(b"email-sermon-audio"),
            church=church,
            preacher=preacher,
            occasion_kind=Sermon.OccasionKind.SUNDAY,
            liturgical_day="Third Sunday of Ordinary Time",
            processing_status=Sermon.ProcessingStatus.READY,
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="Grace makes room at the table.",
        )
        Reflection.objects.create(
            sermon=self.sermon,
            prompt="What will I do?",
            content="Private words must stay private.",
        )
        self.anna = SavedRecipient.objects.create(
            owner=self.owner,
            name="Anna",
            email="anna@example.com",
        )
        self.family = SavedRecipient.objects.create(
            owner=self.owner,
            name="Family",
            email="family@example.com",
        )
        self.other_recipient = SavedRecipient.objects.create(
            owner=self.other_user,
            name="Someone else's recipient",
            email="hidden@example.com",
        )

    @property
    def url(self) -> str:
        return f"/api/sermons/{self.sermon.id}/email/"

    def test_owner_sends_one_private_beautiful_email_per_saved_recipient(self):
        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            self.url,
            {
                "recipient_ids": [str(self.anna.id), str(self.family.id)],
                "subject": "A sermon worth revisiting",
                "note": "I thought of our conversation.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sent_count"], 2)
        self.assertTrue(
            response.data["share_url"].startswith("https://listen.example.test")
        )
        self.assertEqual(ShareLink.objects.filter(revoked_at=None).count(), 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            {message.to[0] for message in mail.outbox},
            {
                "anna@example.com",
                "family@example.com",
            },
        )
        for message in mail.outbox:
            self.assertEqual(message.subject, "A sermon worth revisiting")
            self.assertEqual(message.reply_to, [self.owner.email])
            self.assertEqual(len(message.to), 1)
            self.assertIn("Grace makes room at the table.", message.body)
            self.assertIn(response.data["share_url"], message.body)
            self.assertNotIn("Private words must stay private.", message.body)
            html = message.alternatives[0].content
            self.assertIn("background:#f1eee4", html)
            self.assertIn("Read and listen", html)
            self.assertIn("Third Sunday of Ordinary Time", html)
            self.assertIn("Rev. Miriam Cho", html)
            self.assertIn("Grace Parish", html)
            self.assertNotIn("Private words must stay private.", html)

    def test_email_rejects_foreign_recipients_and_non_owned_sermons(self):
        self.client.force_authenticate(user=self.owner)
        foreign_recipient = self.client.post(
            self.url,
            {
                "recipient_ids": [str(self.other_recipient.id)],
                "subject": "Should not send",
                "note": "",
            },
            format="json",
        )
        self.client.force_authenticate(user=self.other_user)
        foreign_sermon = self.client.post(
            self.url,
            {
                "recipient_ids": [str(self.other_recipient.id)],
                "subject": "Should not send",
                "note": "",
            },
            format="json",
        )

        self.assertEqual(foreign_recipient.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign_sermon.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ShareLink.objects.exists())

    def test_email_validates_recipient_count_and_header_safe_subject(self):
        self.client.force_authenticate(user=self.owner)

        no_recipients = self.client.post(
            self.url,
            {
                "recipient_ids": [],
                "subject": "Nobody",
                "note": "",
            },
            format="json",
        )
        unsafe_subject = self.client.post(
            self.url,
            {
                "recipient_ids": [str(self.anna.id)],
                "subject": "Hello\nBcc: hidden@example.com",
                "note": "",
            },
            format="json",
        )

        self.assertEqual(no_recipients.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(unsafe_subject.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)
