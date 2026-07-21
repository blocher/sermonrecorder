import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx
import jwt
from django.conf import settings
from django.utils.module_loading import import_string
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushAlert:
    title: str
    body: str
    data: dict[str, str]


class InvalidDeviceRegistrationError(Exception):
    pass


class PermanentPushAlertError(Exception):
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


@lru_cache(maxsize=4)
def _fcm_credentials(service_account_file: str):
    return service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=("https://www.googleapis.com/auth/firebase.messaging",),
    )


class NativePushAlertSender:
    def send(self, platform: str, token: str, alert: PushAlert) -> None:
        if platform == "ios":
            self._send_apns(token, alert)
            return
        if platform == "android":
            self._send_fcm(token, alert)
            return
        raise PermanentPushAlertError(f"Unsupported push platform: {platform}")

    def _send_apns(self, token: str, alert: PushAlert) -> None:
        key_id = settings.APNS_KEY_ID
        team_id = settings.APNS_TEAM_ID
        key_path = settings.APNS_AUTH_KEY_PATH
        topic = settings.APNS_TOPIC
        if not all((key_id, team_id, key_path, topic)):
            raise PermanentPushAlertError(
                "APNs credentials and topic are not configured."
            )
        try:
            private_key = Path(key_path).read_text()
        except OSError as error:
            raise PermanentPushAlertError(
                "The APNs authentication key could not be read."
            ) from error

        try:
            provider_token = jwt.encode(
                {"iss": team_id, "iat": int(time.time())},
                private_key,
                algorithm="ES256",
                headers={"kid": key_id},
            )
        except Exception as error:
            raise PermanentPushAlertError(
                "The APNs authentication key is invalid."
            ) from error
        host = (
            "https://api.sandbox.push.apple.com"
            if settings.APNS_USE_SANDBOX
            else "https://api.push.apple.com"
        )
        with httpx.Client(
            http2=True,
            timeout=settings.PUSH_ALERT_TIMEOUT_SECONDS,
        ) as client:
            response = client.post(
                f"{host}/3/device/{token}",
                headers={
                    "authorization": f"bearer {provider_token}",
                    "apns-topic": topic,
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                },
                json={
                    "aps": {
                        "alert": {"title": alert.title, "body": alert.body},
                        "sound": "default",
                    },
                    **alert.data,
                },
            )
        if response.status_code == 200:
            return

        reason = _response_error_code(response)
        if reason == "Unregistered":
            raise InvalidDeviceRegistrationError(reason)
        if response.status_code == 429 or response.status_code >= 500:
            raise RuntimeError(f"APNs temporarily rejected the alert: {reason}")
        raise PermanentPushAlertError(f"APNs rejected the alert: {reason}")

    def _send_fcm(self, token: str, alert: PushAlert) -> None:
        project_id = settings.FCM_PROJECT_ID
        service_account_file = settings.FCM_SERVICE_ACCOUNT_FILE
        if not project_id or not service_account_file:
            raise PermanentPushAlertError(
                "FCM project and service-account credentials are not configured."
            )
        try:
            credentials = _fcm_credentials(service_account_file)
        except Exception as error:
            raise PermanentPushAlertError(
                "FCM service-account credentials could not be loaded."
            ) from error
        if not credentials.valid:
            try:
                credentials.refresh(GoogleAuthRequest())
            except Exception as error:
                raise RuntimeError(
                    "FCM OAuth credentials could not be refreshed."
                ) from error

        with httpx.Client(timeout=settings.PUSH_ALERT_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
                headers={"authorization": f"Bearer {credentials.token}"},
                json={
                    "message": {
                        "token": token,
                        "notification": {
                            "title": alert.title,
                            "body": alert.body,
                        },
                        "data": alert.data,
                        "android": {"priority": "high"},
                    }
                },
            )
        if response.status_code == 200:
            return

        error_code = _response_error_code(response)
        if error_code == "UNREGISTERED":
            raise InvalidDeviceRegistrationError(error_code)
        if response.status_code == 429 or response.status_code >= 500:
            raise RuntimeError(f"FCM temporarily rejected the alert: {error_code}")
        raise PermanentPushAlertError(f"FCM rejected the alert: {error_code}")


def _response_error_code(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    if not isinstance(data, dict):
        return f"HTTP {response.status_code}"

    reason = data.get("reason")
    if isinstance(reason, str):
        return reason
    error = data.get("error")
    if not isinstance(error, dict):
        return f"HTTP {response.status_code}"
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict) and isinstance(detail.get("errorCode"), str):
                return detail["errorCode"]
    status = error.get("status")
    return status if isinstance(status, str) else f"HTTP {response.status_code}"


def get_push_alert_sender() -> PushAlertSender:
    sender_class = import_string(settings.PUSH_ALERT_SENDER)
    return sender_class()
