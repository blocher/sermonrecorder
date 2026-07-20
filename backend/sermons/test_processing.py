from unittest.mock import patch

from celery.exceptions import Retry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from kombu.exceptions import OperationalError

from accounts.models import User

from .models import Sermon
from .processing import PermanentProcessingError, RetryableProcessingError
from .tasks import enqueue_sermon_processing, process_sermon


class SuccessfulProcessor:
    def process(self, sermon: Sermon) -> None:
        return None


class TemporarilyFailingProcessor:
    def process(self, sermon: Sermon) -> None:
        raise RetryableProcessingError(
            "transcription provider is temporarily unavailable"
        )


class PermanentlyFailingProcessor:
    def process(self, sermon: Sermon) -> None:
        raise PermanentProcessingError("the audio format cannot be decoded")


class SermonProcessingTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="processor@example.com",
            password="safe-test-password",
        )

    def sermon(self) -> Sermon:
        return Sermon.objects.create(
            owner=self.user,
            source_draft_id=f"draft-{Sermon.objects.count()}",
            captured_at=timezone.now(),
            duration_seconds=120,
            audio=SimpleUploadedFile(
                "sermon.m4a",
                b"test audio",
                content_type="audio/mp4",
            ),
            audio_mime_type="audio/mp4",
            audio_size_bytes=10,
        )

    @override_settings(SERMON_PROCESSOR="sermons.test_processing.SuccessfulProcessor")
    def test_successful_processing_marks_the_sermon_ready_once(self):
        sermon = self.sermon()

        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="successful-job",
            throw=True,
        )
        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="duplicate-job",
            throw=True,
        )

        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.READY)
        self.assertEqual(sermon.processing_attempts, 1)
        self.assertEqual(sermon.processing_error, "")
        self.assertEqual(sermon.processing_claim_id, "")
        self.assertIsNotNone(sermon.processing_started_at)
        self.assertIsNotNone(sermon.processing_finished_at)

    @override_settings(SERMON_PROCESSOR="sermons.test_processing.SuccessfulProcessor")
    def test_competing_job_cannot_take_an_active_claim(self):
        sermon = self.sermon()
        sermon.processing_status = Sermon.ProcessingStatus.PROCESSING
        sermon.processing_attempts = 1
        sermon.processing_claim_id = "active-job"
        sermon.processing_started_at = timezone.now()
        sermon.save(
            update_fields=(
                "processing_status",
                "processing_attempts",
                "processing_claim_id",
                "processing_started_at",
                "updated_at",
            )
        )

        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="competing-job",
            throw=True,
        )

        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.PROCESSING)
        self.assertEqual(sermon.processing_attempts, 1)
        self.assertEqual(sermon.processing_claim_id, "active-job")

    @override_settings(
        SERMON_PROCESSOR="sermons.test_processing.PermanentlyFailingProcessor"
    )
    def test_permanent_failure_stops_without_retrying(self):
        sermon = self.sermon()

        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="permanent-job",
            throw=True,
        )

        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.FAILED)
        self.assertEqual(sermon.processing_attempts, 1)
        self.assertIn("cannot be decoded", sermon.processing_error)
        self.assertIsNotNone(sermon.processing_finished_at)

    @override_settings(
        SERMON_PROCESSOR="sermons.test_processing.TemporarilyFailingProcessor"
    )
    def test_temporary_failure_returns_to_uploaded_while_waiting_to_retry(self):
        sermon = self.sermon()

        with patch.object(
            process_sermon,
            "retry",
            side_effect=Retry("scheduled retry"),
        ):
            with self.assertRaises(Retry):
                process_sermon.run(str(sermon.id))

        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.UPLOADED)
        self.assertEqual(sermon.processing_attempts, 1)
        self.assertIn("temporarily unavailable", sermon.processing_error)
        self.assertEqual(sermon.processing_claim_id, "")
        self.assertIsNone(sermon.processing_started_at)
        self.assertIsNone(sermon.processing_finished_at)

    @override_settings(
        SERMON_PROCESSOR="sermons.test_processing.TemporarilyFailingProcessor"
    )
    def test_retry_exhaustion_marks_the_sermon_failed(self):
        sermon = self.sermon()

        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="exhausted-job",
            throw=False,
        )

        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.FAILED)
        self.assertEqual(sermon.processing_attempts, 4)
        self.assertIn("temporarily unavailable", sermon.processing_error)
        self.assertIsNotNone(sermon.processing_finished_at)

    def test_broker_failure_leaves_the_sermon_available_for_recovery(self):
        sermon = self.sermon()

        with patch(
            "sermons.tasks.process_sermon.apply_async",
            side_effect=OperationalError("redis unavailable"),
        ):
            queued = enqueue_sermon_processing(str(sermon.id))

        self.assertFalse(queued)
        sermon.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.UPLOADED)
        self.assertEqual(sermon.processing_attempts, 0)
