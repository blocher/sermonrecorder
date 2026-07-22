from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Church, Preacher, Sermon


class SermonContextTests(APITestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(
            email="context-owner@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="context-other@example.com",
            password="safe-test-password",
        )
        self.sermon = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="context-sermon",
            captured_at=timezone.now(),
            duration_seconds=1_800,
            audio=SimpleUploadedFile(
                "sermon.m4a",
                b"context-sermon-audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=len(b"context-sermon-audio"),
            processing_status=Sermon.ProcessingStatus.READY,
        )

    def test_personal_church_and_preacher_books_normalize_and_deduplicate(self):
        self.client.force_authenticate(user=self.owner)
        church = self.client.post(
            "/api/sermons/churches/",
            {
                "name": "  St. Anselm   Church ",
                "address": " 14 Oak   Street ",
                "latitude": "40.712800",
                "longitude": "-74.006000",
            },
            format="json",
        )
        preacher = self.client.post(
            "/api/sermons/preachers/",
            {"name": "  Fr. Daniel   Ortiz  "},
            format="json",
        )
        duplicate_church = self.client.post(
            "/api/sermons/churches/",
            {"name": "st. anselm church", "address": "14 oak street"},
            format="json",
        )
        duplicate_preacher = self.client.post(
            "/api/sermons/preachers/",
            {"name": "fr. daniel ortiz"},
            format="json",
        )

        self.assertEqual(church.status_code, status.HTTP_201_CREATED)
        self.assertEqual(church.data["name"], "St. Anselm Church")
        self.assertEqual(church.data["address"], "14 Oak Street")
        self.assertEqual(preacher.status_code, status.HTTP_201_CREATED)
        self.assertEqual(preacher.data["name"], "Fr. Daniel Ortiz")
        self.assertEqual(duplicate_church.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_preacher.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(user=self.other_user)
        other_list = self.client.get("/api/sermons/churches/")
        same_name_for_other_owner = self.client.post(
            "/api/sermons/churches/",
            {"name": "St. Anselm Church", "address": "14 Oak Street"},
            format="json",
        )
        self.assertEqual(other_list.data, [])
        self.assertEqual(
            same_name_for_other_owner.status_code,
            status.HTTP_201_CREATED,
        )

    def test_owner_assigns_reusable_context_and_can_clear_it(self):
        church = Church.objects.create(
            owner=self.owner,
            name="Grace Parish",
            address="1 Main Street",
        )
        preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.client.force_authenticate(user=self.owner)

        assigned = self.client.patch(
            f"/api/sermons/{self.sermon.id}/context/",
            {
                "title": "  Bread   for the Journey ",
                "church_id": str(church.id),
                "preacher_id": str(preacher.id),
                "occasion_kind": Sermon.OccasionKind.SUNDAY,
                "liturgical_day": "  Third Sunday   of Ordinary Time ",
            },
            format="json",
        )

        self.assertEqual(assigned.status_code, status.HTTP_200_OK)
        self.assertEqual(assigned.data["title"], "Bread for the Journey")
        self.assertEqual(assigned.data["church"]["name"], "Grace Parish")
        self.assertEqual(assigned.data["preacher"]["name"], "Rev. Miriam Cho")
        self.assertEqual(assigned.data["occasion_kind"], "sunday")
        self.assertEqual(
            assigned.data["liturgical_day"],
            "Third Sunday of Ordinary Time",
        )
        self.sermon.refresh_from_db()
        self.assertIsNotNone(self.sermon.title_edited_at)

        cleared = self.client.patch(
            f"/api/sermons/{self.sermon.id}/context/",
            {
                "church_id": None,
                "preacher_id": None,
                "occasion_kind": "",
                "liturgical_day": "",
            },
            format="json",
        )
        self.assertEqual(cleared.status_code, status.HTTP_200_OK)
        self.assertIsNone(cleared.data["church"])
        self.assertIsNone(cleared.data["preacher"])

    def test_context_assignment_rejects_another_congregants_books(self):
        foreign_church = Church.objects.create(
            owner=self.other_user,
            name="Hidden Church",
        )
        foreign_preacher = Preacher.objects.create(
            owner=self.other_user,
            name="Hidden Preacher",
        )
        self.client.force_authenticate(user=self.owner)

        church_response = self.client.patch(
            f"/api/sermons/{self.sermon.id}/context/",
            {"church_id": str(foreign_church.id)},
            format="json",
        )
        preacher_response = self.client.patch(
            f"/api/sermons/{self.sermon.id}/context/",
            {"preacher_id": str(foreign_preacher.id)},
            format="json",
        )
        invalid_occasion = self.client.patch(
            f"/api/sermons/{self.sermon.id}/context/",
            {"occasion_kind": "invented"},
            format="json",
        )

        self.assertEqual(church_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(preacher_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(invalid_occasion.status_code, status.HTTP_400_BAD_REQUEST)
        self.sermon.refresh_from_db()
        self.assertIsNone(self.sermon.church)
        self.assertIsNone(self.sermon.preacher)
