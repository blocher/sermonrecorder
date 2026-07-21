import logging
import uuid
from datetime import timedelta

from celery import shared_task
from celery.app.task import Task
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from kombu.exceptions import OperationalError

from accounts.models import DeviceRegistration

from .models import ProcessingAlert, Sermon
from .processed_sermon_repository import persist_processed_sermon
from .processing import (
    PermanentProcessingError,
    RetryableProcessingError,
    get_sermon_processor,
)
from .push_alerts import (
    InvalidDeviceRegistrationError,
    PushAlert,
    get_push_alert_sender,
)

logger = logging.getLogger(__name__)


def _claim_sermon(sermon_id: str, claim_id: str) -> Sermon | None:
    with transaction.atomic():
        try:
            sermon = Sermon.objects.select_for_update().get(id=sermon_id)
        except (Sermon.DoesNotExist, ValueError):
            return None

        is_redelivery = (
            sermon.processing_status == Sermon.ProcessingStatus.PROCESSING
            and sermon.processing_claim_id == claim_id
        )
        if (
            sermon.processing_status != Sermon.ProcessingStatus.UPLOADED
            and not is_redelivery
        ):
            return None

        sermon.processing_status = Sermon.ProcessingStatus.PROCESSING
        sermon.processing_error = ""
        sermon.processing_attempts += 1
        sermon.processing_claim_id = claim_id
        sermon.processing_started_at = timezone.now()
        sermon.processing_finished_at = None
        sermon.save(
            update_fields=(
                "processing_status",
                "processing_error",
                "processing_attempts",
                "processing_claim_id",
                "processing_started_at",
                "processing_finished_at",
                "updated_at",
            )
        )
        return sermon


def _finish(sermon_id: uuid.UUID, claim_id: str, status: str, error: str = "") -> None:
    now = timezone.now()
    changes = {
        "processing_status": status,
        "processing_error": error,
        "processing_claim_id": "",
        "processing_finished_at": now,
        "updated_at": now,
    }
    if status == Sermon.ProcessingStatus.UPLOADED:
        changes["processing_started_at"] = None
        changes["processing_finished_at"] = None

    with transaction.atomic():
        updated = Sermon.objects.filter(
            id=sermon_id,
            processing_status=Sermon.ProcessingStatus.PROCESSING,
            processing_claim_id=claim_id,
        ).update(**changes)
        if not updated or status not in (
            Sermon.ProcessingStatus.READY,
            Sermon.ProcessingStatus.FAILED,
        ):
            return

        owner_id = Sermon.objects.values_list("owner_id", flat=True).get(id=sermon_id)
        device_ids = DeviceRegistration.objects.filter(
            owner_id=owner_id,
            active=True,
        ).values_list("id", flat=True)
        ProcessingAlert.objects.bulk_create(
            (
                ProcessingAlert(
                    sermon_id=sermon_id,
                    device_id=device_id,
                    processing_status=status,
                )
                for device_id in device_ids
            ),
            ignore_conflicts=True,
        )
        alert_ids = tuple(
            str(alert_id)
            for alert_id in ProcessingAlert.objects.filter(
                sermon_id=sermon_id,
                processing_status=status,
                delivery_status=ProcessingAlert.DeliveryStatus.PENDING,
            ).values_list("id", flat=True)
        )
        transaction.on_commit(lambda: _enqueue_processing_alerts(alert_ids))


def _retry_delay(retry_number: int) -> int:
    delays = settings.SERMON_PROCESSING_RETRY_DELAYS
    return delays[min(retry_number, len(delays) - 1)]


def _retry_or_fail(
    task: Task,
    sermon: Sermon,
    claim_id: str,
    error: Exception,
) -> None:
    max_retries = task.max_retries or 0
    if task.request.retries >= max_retries:
        _finish(
            sermon.id,
            claim_id,
            Sermon.ProcessingStatus.FAILED,
            str(error),
        )
        return

    _finish(
        sermon.id,
        claim_id,
        Sermon.ProcessingStatus.UPLOADED,
        str(error),
    )
    raise task.retry(
        exc=error,
        countdown=_retry_delay(task.request.retries),
    )


@shared_task(
    bind=True,
    max_retries=3,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_sermon(self: Task, sermon_id: str) -> None:
    claim_id = self.request.id or f"eager-{uuid.uuid4()}"
    sermon = _claim_sermon(sermon_id, claim_id)
    if sermon is None:
        return

    try:
        result = get_sermon_processor().process(sermon)
        persist_processed_sermon(sermon, result)
    except PermanentProcessingError as error:
        _finish(
            sermon.id,
            claim_id,
            Sermon.ProcessingStatus.FAILED,
            str(error),
        )
    except RetryableProcessingError as error:
        _retry_or_fail(self, sermon, claim_id, error)
    except Exception as error:
        logger.exception(
            "Sermon processing attempt failed", extra={"sermon_id": sermon_id}
        )
        _retry_or_fail(self, sermon, claim_id, error)
    else:
        _finish(
            sermon.id,
            claim_id,
            Sermon.ProcessingStatus.READY,
        )


def enqueue_sermon_processing(sermon_id: str) -> bool:
    try:
        process_sermon.apply_async(args=(sermon_id,), retry=False)
    except (OperationalError, OSError):
        logger.warning(
            "Sermon remains safely uploaded because the worker broker is unavailable",
            extra={"sermon_id": sermon_id},
        )
        return False
    return True


def _alert_message(alert: ProcessingAlert) -> PushAlert:
    if alert.processing_status == Sermon.ProcessingStatus.READY:
        return PushAlert(
            title="Your Sermon is ready",
            body="The recording, Transcript, and Study materials are ready to revisit.",
            data={"sermon_id": str(alert.sermon_id), "status": "ready"},
        )
    return PushAlert(
        title="Your Sermon needs attention",
        body="Pewcorder could not finish this recording. Open the app for details.",
        data={"sermon_id": str(alert.sermon_id), "status": "failed"},
    )


def _alert_retry_delay(retry_number: int) -> int:
    delays = settings.PUSH_ALERT_RETRY_DELAYS
    return delays[min(retry_number, len(delays) - 1)]


@shared_task(bind=True, max_retries=5)
def deliver_processing_alert(self: Task, alert_id: str) -> None:
    now = timezone.now()
    claimed = (
        ProcessingAlert.objects.filter(
            id=alert_id,
            delivery_status=ProcessingAlert.DeliveryStatus.PENDING,
        )
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .update(
            delivery_status=ProcessingAlert.DeliveryStatus.DELIVERING,
            delivery_attempts=F("delivery_attempts") + 1,
            delivery_error="",
            next_attempt_at=None,
            updated_at=now,
        )
    )
    if not claimed:
        return

    alert = ProcessingAlert.objects.select_related("device", "sermon").get(id=alert_id)
    if alert.device.owner_id != alert.sermon.owner_id:
        ProcessingAlert.objects.filter(id=alert.id).update(
            delivery_status=ProcessingAlert.DeliveryStatus.FAILED,
            delivery_error="The device registration now belongs to another account.",
            updated_at=timezone.now(),
        )
        return
    try:
        get_push_alert_sender().send(
            alert.device.platform,
            alert.device.token,
            _alert_message(alert),
        )
    except InvalidDeviceRegistrationError as error:
        DeviceRegistration.objects.filter(id=alert.device_id).update(active=False)
        ProcessingAlert.objects.filter(id=alert.id).update(
            delivery_status=ProcessingAlert.DeliveryStatus.FAILED,
            delivery_error=str(error),
            updated_at=timezone.now(),
        )
    except Exception as error:
        if self.request.retries >= (self.max_retries or 0):
            ProcessingAlert.objects.filter(id=alert.id).update(
                delivery_status=ProcessingAlert.DeliveryStatus.FAILED,
                delivery_error=str(error),
                updated_at=timezone.now(),
            )
            return
        retry_delay = _alert_retry_delay(self.request.retries)
        ProcessingAlert.objects.filter(id=alert.id).update(
            delivery_status=ProcessingAlert.DeliveryStatus.PENDING,
            delivery_error=str(error),
            next_attempt_at=timezone.now() + timedelta(seconds=retry_delay),
            updated_at=timezone.now(),
        )
        raise self.retry(
            exc=error,
            countdown=retry_delay,
        )
    else:
        ProcessingAlert.objects.filter(id=alert.id).update(
            delivery_status=ProcessingAlert.DeliveryStatus.SENT,
            next_attempt_at=None,
            sent_at=timezone.now(),
            updated_at=timezone.now(),
        )


def enqueue_processing_alert(alert_id: str) -> bool:
    try:
        deliver_processing_alert.apply_async(args=(alert_id,), retry=False)
    except (OperationalError, OSError):
        logger.warning(
            "Processing alert remains queued because the worker broker is unavailable",
            extra={"alert_id": alert_id},
        )
        return False
    return True


def _enqueue_processing_alerts(alert_ids: tuple[str, ...]) -> None:
    for alert_id in alert_ids:
        enqueue_processing_alert(alert_id)


@shared_task
def dispatch_uploaded_sermons(limit: int = 100) -> int:
    queued = 0
    sermon_ids = Sermon.objects.filter(
        processing_status=Sermon.ProcessingStatus.UPLOADED
    ).values_list("id", flat=True)[:limit]

    for sermon_id in sermon_ids:
        if enqueue_sermon_processing(str(sermon_id)):
            queued += 1

    return queued


@shared_task
def dispatch_pending_processing_alerts(limit: int = 100) -> int:
    stalled_before = timezone.now() - timedelta(minutes=10)
    ProcessingAlert.objects.filter(
        delivery_status=ProcessingAlert.DeliveryStatus.DELIVERING,
        updated_at__lt=stalled_before,
    ).update(
        delivery_status=ProcessingAlert.DeliveryStatus.PENDING,
        delivery_error="Delivery claim expired and was recovered.",
        next_attempt_at=None,
        updated_at=timezone.now(),
    )

    queued = 0
    alert_ids = (
        ProcessingAlert.objects.filter(
            delivery_status=ProcessingAlert.DeliveryStatus.PENDING,
        )
        .filter(
            Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
        )
        .values_list("id", flat=True)[:limit]
    )
    for alert_id in alert_ids:
        if enqueue_processing_alert(str(alert_id)):
            queued += 1
    return queued
