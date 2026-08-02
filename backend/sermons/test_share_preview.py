from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Church, Preacher, Sermon, ShareLink, StudyArtifact
from .share_preview import build_share_preview, inject_share_preview_meta
from .sharing import _share_token


class BuildSharePreviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="preview-owner@example.com",
            password="safe-test-password",
        )
        self.church = Church.objects.create(owner=self.owner, name="Grace Parish")
        self.preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.sermon = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="preview-sermon",
            title="The Banquet Table",
            captured_at=datetime(2026, 1, 15, 16, 0, tzinfo=ZoneInfo("UTC")),
            duration_seconds=900,
            audio_mime_type="audio/mp4",
            audio_size_bytes=12,
            church=self.church,
            preacher=self.preacher,
            liturgical_day="Second Sunday after Epiphany",
            processing_status=Sermon.ProcessingStatus.READY,
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content=(
                "Grace sets a table before strangers and asks the church to make room "
                "before it knows what can be returned."
            ),
        )

    def test_preview_includes_title_preacher_date_and_summary(self):
        with override_settings(TIME_ZONE="America/New_York"):
            preview = build_share_preview(self.sermon)

        self.assertEqual(preview.title, "The Banquet Table")
        self.assertIn("Rev. Miriam Cho", preview.description)
        self.assertIn("Jan 15, 2026", preview.description)
        self.assertIn("Grace Parish", preview.description)
        self.assertIn("Second Sunday after Epiphany", preview.description)
        self.assertIn("Grace sets a table", preview.description)
        self.assertEqual(preview.page_title, "The Banquet Table · Pewcorder")

    def test_untitled_sermon_falls_back_to_dated_label(self):
        self.sermon.title = ""
        self.sermon.save(update_fields=["title"])

        with override_settings(TIME_ZONE="UTC"):
            preview = build_share_preview(self.sermon)

        self.assertEqual(preview.title, "Sermon · Jan 15, 2026")

    def test_long_summary_is_truncated(self):
        StudyArtifact.objects.filter(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
        ).update(content=("Grace welcomes the lost. " * 40).strip())

        preview = build_share_preview(self.sermon)

        self.assertLessEqual(len(preview.description), 220)
        self.assertTrue(preview.description.endswith("…"))


class InjectSharePreviewMetaTests(TestCase):
    def test_replaces_default_title_and_description(self):
        shell = (
            "<!doctype html><html><head>"
            "<meta name=\"description\" content=\"Generic app blurb.\" />"
            "<title>Pewcorder · AI Sermon Journal</title>"
            "</head><body><div id=\"app\"></div></body></html>"
        )
        from .share_preview import SharePreview

        html_document = inject_share_preview_meta(
            shell,
            preview=SharePreview(
                title="The Banquet Table",
                description="Rev. Miriam Cho · Jan 15, 2026",
                page_title="The Banquet Table · Pewcorder",
            ),
            canonical_url="https://listen.example.test/share/token",
            image_url="https://listen.example.test/og-share.png",
        )

        self.assertIn("<title>The Banquet Table · Pewcorder</title>", html_document)
        self.assertIn('property="og:title" content="The Banquet Table"', html_document)
        self.assertIn(
            'property="og:description" content="Rev. Miriam Cho · Jan 15, 2026"',
            html_document,
        )
        self.assertIn(
            'property="og:image" content="https://listen.example.test/og-share.png"',
            html_document,
        )
        self.assertNotIn("Generic app blurb.", html_document)
        self.assertNotIn("Pewcorder · AI Sermon Journal", html_document)
        self.assertIn('<div id="app"></div>', html_document)


@override_settings(PEWCORDER_PUBLIC_WEB_URL="https://listen.example.test")
class SharedSermonPageTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="share-page-owner@example.com",
            password="safe-test-password",
        )
        self.preacher = Preacher.objects.create(
            owner=self.owner,
            name="Rev. Miriam Cho",
        )
        self.sermon = Sermon.objects.create(
            owner=self.owner,
            source_draft_id="share-page-sermon",
            title="The Banquet Table",
            captured_at=timezone.now(),
            duration_seconds=900,
            audio_mime_type="audio/mp4",
            audio_size_bytes=12,
            preacher=self.preacher,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        StudyArtifact.objects.create(
            sermon=self.sermon,
            kind=StudyArtifact.Kind.SHORT_SUMMARY,
            content="Grace sets a table before strangers.",
        )
        self.share_link = ShareLink.objects.create(sermon=self.sermon)
        self.token = _share_token(self.share_link)

    def test_share_page_serves_open_graph_tags(self):
        with TemporaryDirectory() as dist_dir:
            Path(dist_dir, "index.html").write_text(
                (
                    "<!doctype html><html><head>"
                    "<title>Pewcorder · AI Sermon Journal</title>"
                    '<meta name="description" content="Private journal." />'
                    '<script type="module" src="/assets/index.js"></script>'
                    "</head><body><div id=\"app\"></div></body></html>"
                ),
                encoding="utf-8",
            )
            with override_settings(PEWCORDER_WEB_DIST_DIR=dist_dir):
                response = self.client.get(f"/share/{self.token}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        body = response.content.decode()
        self.assertIn('property="og:title" content="The Banquet Table"', body)
        self.assertIn("Rev. Miriam Cho", body)
        self.assertIn("Grace sets a table before strangers.", body)
        self.assertIn(
            'property="og:image" content="https://listen.example.test/og-share.png"',
            body,
        )
        self.assertIn('src="/assets/index.js"', body)
        self.assertIn('<div id="app"></div>', body)

    def test_revoked_share_page_is_not_found(self):
        self.share_link.revoked_at = timezone.now()
        self.share_link.save(update_fields=["revoked_at"])

        response = self.client.get(f"/share/{self.token}")

        self.assertEqual(response.status_code, 404)
        self.assertIn("unavailable", response.content.decode().lower())

    def test_fallback_html_when_spa_dist_missing(self):
        with TemporaryDirectory() as empty_dir:
            with override_settings(PEWCORDER_WEB_DIST_DIR=empty_dir):
                response = self.client.get(f"/share/{self.token}")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('property="og:title" content="The Banquet Table"', body)
        self.assertIn("Opening shared sermon", body)
