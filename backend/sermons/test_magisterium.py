import json
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
import httpx

from accounts.models import User

from .magisterium_client import MagisteriumClient, MagisteriumSearchHit
from .magisterium_enrichment import (
    AssertionListOutput,
    MagisteriumArtifacts,
    MagisteriumEnricher,
    SearchQueryOutput,
)
from .magisterium_regeneration import regenerate_magisterium_artifacts
from .models import Sermon, StudyArtifact, Transcript
from .openai_transcriber import CleanedTranscript
from .processing import StudyArtifactResult, TranscriptSegment


@override_settings(
    MAGISTERIUM_API_KEY="test-key",
    MAGISTERIUM_TIER="pro",
    MAGISTERIUM_BASE_URL="https://magisterium.test/api/v1",
    MAGISTERIUM_TIMEOUT_SECONDS=5,
)
class MagisteriumClientTests(SimpleTestCase):
    def test_search_sends_tier_and_parses_results(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(request.headers["X-Magisterium-Tier"], "pro")
            payload = json.loads(request.content.decode())
            self.assertEqual(payload["tier"], "pro")
            self.assertEqual(payload["query"], "Catholic teaching on grace")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "results": [
                            {
                                "document_title": "Deus Caritas Est",
                                "title": "God Is Love",
                                "author": "Benedict XVI",
                                "ref": "1",
                                "text": "God is love.",
                                "url": "https://example.com/dce",
                                "category": "magisterial",
                            }
                        ]
                    }
                },
            )

        transport = httpx.MockTransport(handler)
        mock_client = httpx.Client(transport=transport)
        with patch("sermons.magisterium_client.httpx.Client", return_value=mock_client):
            hits = MagisteriumClient().search(
                "Catholic teaching on grace",
                num_results=3,
            )

        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].title, "Deus Caritas Est — God Is Love")
        self.assertEqual(hits[0].author, "Benedict XVI")
        self.assertEqual(hits[0].source_url, "https://example.com/dce")
        self.assertEqual(hits[0].year, "1")

    def test_chat_parses_citations(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "This claim is borderline.",
                            }
                        }
                    ],
                    "citations": [
                        {
                            "cited_text": "Faith works through love.",
                            "document_title": "Catechism of the Catholic Church",
                            "document_author": "",
                            "document_year": "",
                            "document_reference": "1815",
                            "source_url": "https://example.com/ccc",
                        }
                    ],
                },
            )

        transport = httpx.MockTransport(handler)
        mock_client = httpx.Client(transport=transport)
        with patch("sermons.magisterium_client.httpx.Client", return_value=mock_client):
            result = MagisteriumClient().chat("Review this assertion.")

        self.assertEqual(result.content, "This claim is borderline.")
        self.assertEqual(result.citations[0].document_reference, "1815")


@override_settings(MAGISTERIUM_API_KEY="", MAGISTERIUM_TIER="")
class MagisteriumEnricherTests(SimpleTestCase):
    def test_skips_network_when_api_key_missing(self):
        enricher = MagisteriumEnricher(client=MagisteriumClient())
        result = enricher.enrich(
            CleanedTranscript(
                text="Grace welcomes us home.",
                segments=(TranscriptSegment(0, 2, "Grace welcomes us home."),),
            )
        )
        kinds = {artifact.kind for artifact in result.study_artifacts}
        self.assertEqual(
            kinds,
            {
                StudyArtifact.Kind.RELATED_SOURCES,
                StudyArtifact.Kind.DOCTRINAL_REVIEW,
            },
        )
        related = json.loads(result.study_artifacts[0].content)
        self.assertEqual(related["sources"], [])

    def test_builds_related_sources_from_search_hits(self):
        client = Mock()
        client.configured = True
        client.search.return_value = (
            MagisteriumSearchHit(
                title="Deus Caritas Est",
                author="Benedict XVI",
                year="2005",
                excerpt="God is love.",
                source_url="https://example.com/dce",
                category="magisterial",
            ),
        )
        runner = Mock(
            side_effect=[
                SearchQueryOutput(queries=["Catholic teaching on love"]),
                AssertionListOutput(assertions=[]),
            ]
        )
        enricher = MagisteriumEnricher(client=client, runner=runner)
        result = enricher.enrich(
            CleanedTranscript(
                text="God is love and calls us to charity.",
                segments=(
                    TranscriptSegment(0, 3, "God is love and calls us to charity."),
                ),
            )
        )
        related = json.loads(
            next(
                artifact.content
                for artifact in result.study_artifacts
                if artifact.kind == StudyArtifact.Kind.RELATED_SOURCES
            )
        )
        self.assertEqual(related["sources"][0]["title"], "Deus Caritas Est")
        client.search.assert_called()
        client.chat.assert_not_called()


class MagisteriumRegenerationTests(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.user = User.objects.create_user(
            email="magisterium-regen@example.com",
            password="safe-test-password",
        )
        self.sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="magisterium-regen",
            captured_at=timezone.now(),
            duration_seconds=60,
            audio=SimpleUploadedFile(
                "sermon.m4a", b"audio", content_type="audio/mp4"
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=5,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        Transcript.objects.create(
            sermon=self.sermon,
            text="Grace alone sustains the Church.",
            segments=[
                {
                    "start_seconds": 0,
                    "end_seconds": 5,
                    "text": "Grace alone sustains the Church.",
                }
            ],
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="Keep me.",
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.RELATED_SOURCES,
            content='{"sources":[]}',
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.DOCTRINAL_REVIEW,
            content='{"findings":[],"summary":"old","citations":[]}',
        )

    def test_regeneration_rewrites_only_magisterium_artifacts(self):
        enricher = Mock()
        enricher.enrich.return_value = MagisteriumArtifacts(
            study_artifacts=(
                StudyArtifactResult(
                    kind=StudyArtifact.Kind.RELATED_SOURCES,
                    content='{"sources":[{"title":"Deus Caritas Est"}]}',
                ),
                StudyArtifactResult(
                    kind=StudyArtifact.Kind.DOCTRINAL_REVIEW,
                    content='{"findings":[],"summary":"fresh","citations":[]}',
                ),
            )
        )

        regenerate_magisterium_artifacts(self.sermon, enricher=enricher)

        related = StudyArtifact.objects.get(
            sermon=self.sermon, kind=StudyArtifact.Kind.RELATED_SOURCES
        )
        doctrinal = StudyArtifact.objects.get(
            sermon=self.sermon, kind=StudyArtifact.Kind.DOCTRINAL_REVIEW
        )
        summary = StudyArtifact.objects.get(
            sermon=self.sermon, kind=StudyArtifact.Kind.SHORT_SUMMARY
        )
        self.assertIn("Deus Caritas Est", related.content)
        self.assertIn("fresh", doctrinal.content)
        self.assertEqual(summary.content, "Keep me.")
        enricher.enrich.assert_called_once()
