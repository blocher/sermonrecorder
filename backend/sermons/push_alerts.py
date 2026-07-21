import logging
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushAlert:
    title: str
    body: str
    data: dict[str, str]


class InvalidDeviceRegistrationError(Exception):
    pass


class PushAlertSender(Protocol):
    def send(self, platform: str, token: str, alert: PushAlert) -> None: ...


class LoggingPushAlertSender:
    def send(self, platform: str, token: str, alert: PushAlert) -> None:
        logger.info(
            "Development push alert",
            extra={
                "platform": platform,
                "token_suffix": token[-8:],
                "title": alert.title,
                "data": alert.data,
            },
        )


def get_push_alert_sender() -> PushAlertSender:
    sender_class = import_string(settings.PUSH_ALERT_SENDER)
    return sender_class()
