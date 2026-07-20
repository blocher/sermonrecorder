from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from .models import Sermon


class SermonProcessingError(Exception):
    """An expected failure while preparing a Sermon."""


class RetryableProcessingError(SermonProcessingError):
    """A temporary failure that should be retried."""


class PermanentProcessingError(SermonProcessingError):
    """A failure that requires configuration or Congregant action."""


class SermonProcessor(Protocol):
    def process(self, sermon: Sermon) -> None:
        """Persist every required result, returning only when the Sermon is Ready."""


class UnconfiguredSermonProcessor:
    def process(self, sermon: Sermon) -> None:
        raise PermanentProcessingError(
            "No Sermon processor is configured. Set SERMON_PROCESSOR before running workers."
        )


def get_sermon_processor() -> SermonProcessor:
    processor_class = import_string(settings.SERMON_PROCESSOR)
    return processor_class()
