import logging
import uuid

from celery import shared_task
from celery.app.task import Task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from kombu.exceptions import OperationalError

from .models import Sermon
from .processing import (
    PermanentProcessingError,
    RetryableProcessingError,
    get_sermon_processor,
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

    Sermon.objects.filter(
        id=sermon_id,
        processing_status=Sermon.ProcessingStatus.PROCESSING,
        processing_claim_id=claim_id,
    ).update(**changes)


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
        get_sermon_processor().process(sermon)
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
