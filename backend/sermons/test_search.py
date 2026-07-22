from datetime import datetime, timezone as datetime_timezone

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import (
    Church,
    Preacher,
    Reflection,
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)


class SermonLibrarySearchTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="search-owner@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="search-other@example.com",
            password="safe-test-password",
        )
        self.church = Church.objects.create(
            owner=self.owner,
            name="Grace Parish",
            address="12 Cedar Lane",
        )
        self.preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.sermon = self._sermon(
            owner=self.owner,
            source_draft_id="search-target",
            captured_at=datetime(2026, 1, 25, 15, tzinfo=datetime_timezone.utc),
            title="Bread for the Journey",
            church=self.church,
            preacher=self.preacher,
            occasion_kind=Sermon.OccasionKind.SUNDAY,
            liturgical_day="Third Sunday of Ordinary Time",
        )
        Transcript.objects.create(
            sermon=self.sermon,
            text="Faith can begin as quietly as a mustard seed.",
            segments=[],
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="Hospitality makes room for an unexpected neighbor.",
        )
        ScriptureReference.objects.create(
            sermon=self.sermon,
            book="Luke",
            chapter_start=14,
            verse_start=12,
        )
        TagSuggestion.objects.create(
            sermon=self.sermon,
            name="Welcome",
            normalized_name="welcome",
        )
        Reflection.objects.create(
            sermon=self.sermon,
            prompt="Where is the threshold?",
            content="Invite Elena to supper.",
        )

        self.related = self._sermon(
            owner=self.owner,
            source_draft_id="search-related",
            captured_at=datetime(2026, 2, 1, 15, tzinfo=datetime_timezone.utc),
        )
        RelatedSermon.objects.create(
            sermon=self.sermon,
            related_sermon=self.related,
            score=0.8,
            reason="Both examine radical generosity.",
        )
        self.other_sermon = self._sermon(
            owner=self.other_user,
            source_draft_id="foreign-search-match",
            captured_at=datetime(2026, 1, 25, 15, tzinfo=datetime_timezone.utc),
            liturgical_day="Mustard Welcome Sunday",
        )
        self.client.force_authenticate(user=self.owner)

    def _sermon(self, *, owner, source_draft_id, captured_at, **context):
        return Sermon.objects.create(
            owner=owner,
            source_draft_id=source_draft_id,
            captured_at=captured_at,
            duration_seconds=1_800,
            audio_mime_type="audio/mp4",
            audio_size_bytes=1,
            processing_status=Sermon.ProcessingStatus.READY,
            **context,
        )

    def _ids(self, response):
        return {item["id"] for item in response.data["results"]}

    def test_searches_private_content_and_metadata_without_exposing_reflections(self):
        searches = (
            "journey",
            "mustard",
            "hospitality",
            "Luke 14",
            "welcome",
            "threshold",
            "Elena",
            "generosity",
            "Grace",
            "Cedar",
            "Miriam",
            "ordinary",
        )

        for search in searches:
            with self.subTest(search=search):
                response = self.client.get("/api/sermons/", {"search": search})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(self._ids(response), {str(self.sermon.id)})
                self.assertNotIn("reflections", response.data["results"][0])

        response = self.client.get(
            "/api/sermons/",
            {"search": "mustard welcome"},
        )
        self.assertEqual(self._ids(response), {str(self.sermon.id)})

    def test_filters_by_context_tag_date_and_processing_status(self):
        filters = (
            {"church": str(self.church.id)},
            {"preacher": str(self.preacher.id)},
            {"occasion": Sermon.OccasionKind.SUNDAY},
            {"tag": "  WELCOME  "},
            {"date_from": "2026-01-25", "date_to": "2026-01-25"},
            {"processing_status": Sermon.ProcessingStatus.READY, "search": "mustard"},
        )

        for query in filters:
            with self.subTest(query=query):
                response = self.client.get("/api/sermons/", query)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(self._ids(response), {str(self.sermon.id)})

        response = self.client.get(
            "/api/sermons/",
            {"date_from": "2026-02-02", "date_to": "2026-02-01"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_never_returns_another_owners_matching_sermon(self):
        response = self.client.get(
            "/api/sermons/",
            {"search": "mustard welcome"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), {str(self.sermon.id)})
        self.assertNotIn(str(self.other_sermon.id), self._ids(response))

    def test_library_list_is_paginated_newest_first(self):
        for day in range(2, 27):
            self._sermon(
                owner=self.owner,
                source_draft_id=f"page-{day}",
                captured_at=datetime(2026, 1, day, 15, tzinfo=datetime_timezone.utc),
            )

        first_page = self.client.get(
            "/api/sermons/",
            {"processing_status": Sermon.ProcessingStatus.READY},
        )
        self.assertEqual(first_page.status_code, status.HTTP_200_OK)
        self.assertEqual(first_page.data["count"], 27)
        self.assertEqual(len(first_page.data["results"]), 20)
        self.assertIsNotNone(first_page.data["next"])
        self.assertEqual(
            first_page.data["results"][0]["id"],
            str(
                Sermon.objects.filter(owner=self.owner)
                .order_by("-captured_at")
                .first()
                .id
            ),
        )

        second_page = self.client.get(
            "/api/sermons/",
            {"processing_status": Sermon.ProcessingStatus.READY, "page": 2},
        )
        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 7)
        self.assertIsNone(second_page.data["next"])

    def test_in_progress_lists_only_unfinished_sermons(self):
        uploaded = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="still-processing",
            captured_at=datetime(2026, 2, 1, 15, tzinfo=datetime_timezone.utc),
            duration_seconds=1_200,
            audio_mime_type="audio/mp4",
            audio_size_bytes=1,
            processing_status=Sermon.ProcessingStatus.PROCESSING,
        )

        response = self.client.get("/api/sermons/", {"in_progress": "true"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._ids(response), {str(uploaded.id)})

        conflict = self.client.get(
            "/api/sermons/",
            {
                "in_progress": "true",
                "processing_status": Sermon.ProcessingStatus.READY,
            },
        )
        self.assertEqual(conflict.status_code, status.HTTP_400_BAD_REQUEST)
