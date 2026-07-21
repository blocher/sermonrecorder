from unittest.mock import patch

from celery.exceptions import Retry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import DeviceRegistration, User

from .models import ProcessingAlert, Sermon
from .push_alerts import InvalidDeviceRegistrationError, PushAlert
from .tasks import (
    deliver_processing_alert,
    dispatch_pending_processing_alerts,
    process_sermon,
)


class RecordingPushAlertSender:
    sent: list[tuple[str, str, PushAlert]] = []

    def send(self, platform: str, token: str, alert: PushAlert) -> None:
        self.sent.append((platform, token, alert))


class InvalidPushAlertSender:
    def send(self, platform: str, token: str, alert: PushAlert) -> None:
        raise InvalidDeviceRegistrationError("The native token has expired.")


class TemporarilyFailingPushAlertSender:
    def send(self, platform: str, token: str, alert: PushAlert) -> None:
        raise RuntimeError("The push gateway is unavailable.")


class SermonProcessingAlertTests(TestCase):
    def setUp(self):
        RecordingPushAlertSender.sent = []
        self.owner = User.objects.create_user(
            email="alert-owner@example.com",
            password="safe-test-password",
        )
        self.other_user = User.objects.create_user(
            email="alert-other@example.com",
            password="safe-test-password",
        )
        self.device = DeviceRegistration.objects.create(
            owner=self.owner,
            platform=DeviceRegistration.Platform.IOS,
            token="owner-native-token",
        )
        DeviceRegistration.objects.create(
            owner=self.other_user,
            platform=DeviceRegistration.Platform.ANDROID,
            token="other-native-token",
        )

    def sermon(self) -> Sermon:
        return Sermon.objects.create(
            owner=self.owner,
            source_draft_id=f"alert-draft-{Sermon.objects.count()}",
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

    @override_settings(
        SERMON_PROCESSOR="sermons.test_processing.SuccessfulProcessor",
        PUSH_ALERT_SENDER="sermons.test_push_alerts.RecordingPushAlertSender",
    )
    def test_ready_sermon_alert_is_owner_only_durable_and_idempotent(self):
        sermon = self.sermon()
        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="ready-alert-job",
            throw=True,
        )
        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="duplicate-ready-alert-job",
            throw=True,
        )

        alert = ProcessingAlert.objects.get()
        self.assertEqual(alert.device, self.device)
        self.assertEqual(alert.processing_status, Sermon.ProcessingStatus.READY)
        self.assertEqual(alert.delivery_status, ProcessingAlert.DeliveryStatus.PENDING)

        deliver_processing_alert.apply(args=(str(alert.id),), throw=True)
        deliver_processing_alert.apply(args=(str(alert.id),), throw=True)

        alert.refresh_from_db()
        self.assertEqual(alert.delivery_status, ProcessingAlert.DeliveryStatus.SENT)
        self.assertEqual(alert.delivery_attempts, 1)
        self.assertIsNotNone(alert.sent_at)
        self.assertEqual(len(RecordingPushAlertSender.sent), 1)
        platform, token, message = RecordingPushAlertSender.sent[0]
        self.assertEqual(platform, DeviceRegistration.Platform.IOS)
        self.assertEqual(token, "owner-native-token")
        self.assertEqual(message.title, "Your Sermon is ready")
        self.assertEqual(message.data["sermon_id"], str(sermon.id))

    @override_settings(
        SERMON_PROCESSOR="sermons.test_processing.PermanentlyFailingProcessor",
        PUSH_ALERT_SENDER="sermons.test_push_alerts.InvalidPushAlertSender",
    )
    def test_failed_sermon_alert_deactivates_an_expired_native_token(self):
        sermon = self.sermon()
        process_sermon.apply(
            args=(str(sermon.id),),
            task_id="failed-alert-job",
            throw=True,
        )
        alert = ProcessingAlert.objects.get()

        deliver_processing_alert.apply(args=(str(alert.id),), throw=True)

        sermon.refresh_from_db()
        alert.refresh_from_db()
        self.device.refresh_from_db()
        self.assertEqual(sermon.processing_status, Sermon.ProcessingStatus.FAILED)
        self.assertEqual(alert.processing_status, Sermon.ProcessingStatus.FAILED)
        self.assertEqual(alert.delivery_status, ProcessingAlert.DeliveryStatus.FAILED)
        self.assertIn("expired", alert.delivery_error)
        self.assertFalse(self.device.active)

    @override_settings(
        PUSH_ALERT_SENDER="sermons.test_push_alerts.TemporarilyFailingPushAlertSender",
        PUSH_ALERT_RETRY_DELAYS=(60,),
    )
    def test_temporary_delivery_failure_observes_backoff_before_recovery(self):
        alert = ProcessingAlert.objects.create(
            sermon=self.sermon(),
            device=self.device,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        with patch.object(
            deliver_processing_alert,
            "retry",
            side_effect=Retry("scheduled retry"),
        ):
            with self.assertRaises(Retry):
                deliver_processing_alert.run(str(alert.id))

        alert.refresh_from_db()
        self.assertEqual(alert.delivery_status, ProcessingAlert.DeliveryStatus.PENDING)
        self.assertGreater(alert.next_attempt_at, timezone.now())
        with patch("sermons.tasks.enqueue_processing_alert") as enqueue:
            queued = dispatch_pending_processing_alerts()
        self.assertEqual(queued, 0)
        enqueue.assert_not_called()

    @override_settings(
        PUSH_ALERT_SENDER="sermons.test_push_alerts.RecordingPushAlertSender",
    )
    def test_delivery_stops_if_a_device_moves_to_another_account(self):
        alert = ProcessingAlert.objects.create(
            sermon=self.sermon(),
            device=self.device,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        DeviceRegistration.objects.filter(id=self.device.id).update(
            owner=self.other_user
        )

        deliver_processing_alert.apply(args=(str(alert.id),), throw=True)

        alert.refresh_from_db()
        self.assertEqual(alert.delivery_status, ProcessingAlert.DeliveryStatus.FAILED)
        self.assertIn("another account", alert.delivery_error)
        self.assertEqual(RecordingPushAlertSender.sent, [])
