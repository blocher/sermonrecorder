from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

import httpx
from django.test import SimpleTestCase, override_settings

from .push_alerts import (
    InvalidDeviceRegistrationError,
    NativePushAlertSender,
    PermanentPushAlertError,
    PushAlert,
)


class NativePushAlertSenderTests(SimpleTestCase):
    def setUp(self):
        self.alert = PushAlert(
            title="Your Sermon is ready",
            body="Study materials are ready.",
            data={"sermon_id": "sermon-id", "status": "ready"},
        )

    @override_settings(
        APNS_KEY_ID="KEY123",
        APNS_TEAM_ID="TEAM123",
        APNS_TOPIC="com.pewcorder.app",
        APNS_USE_SANDBOX=True,
        PUSH_ALERT_TIMEOUT_SECONDS=12,
    )
    def test_apns_uses_http2_token_auth_and_owner_safe_deep_link_data(self):
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = httpx.Response(200)
        with NamedTemporaryFile(mode="w", suffix=".p8") as key_file:
            key_file.write("private-key")
            key_file.flush()
            with (
                self.settings(APNS_AUTH_KEY_PATH=key_file.name),
                patch("sermons.push_alerts.jwt.encode", return_value="provider-token"),
                patch(
                    "sermons.push_alerts.httpx.Client", return_value=client
                ) as factory,
            ):
                NativePushAlertSender().send("ios", "apns-device-token", self.alert)

        factory.assert_called_once_with(http2=True, timeout=12)
        client.post.assert_called_once_with(
            "https://api.sandbox.push.apple.com/3/device/apns-device-token",
            headers={
                "authorization": "bearer provider-token",
                "apns-topic": "com.pewcorder.app",
                "apns-push-type": "alert",
                "apns-priority": "10",
            },
            json={
                "aps": {
                    "alert": {
                        "title": "Your Sermon is ready",
                        "body": "Study materials are ready.",
                    },
                    "sound": "default",
                },
                "sermon_id": "sermon-id",
                "status": "ready",
            },
        )

    @override_settings(
        APNS_KEY_ID="KEY123",
        APNS_TEAM_ID="TEAM123",
        APNS_TOPIC="com.pewcorder.app",
        APNS_USE_SANDBOX=False,
        PUSH_ALERT_TIMEOUT_SECONDS=12,
    )
    def test_apns_deactivates_only_confirmed_unregistered_tokens(self):
        client = MagicMock()
        client.__enter__.return_value = client
        with NamedTemporaryFile(mode="w", suffix=".p8") as key_file:
            key_file.write("private-key")
            key_file.flush()
            with (
                self.settings(APNS_AUTH_KEY_PATH=key_file.name),
                patch("sermons.push_alerts.jwt.encode", return_value="provider-token"),
                patch("sermons.push_alerts.httpx.Client", return_value=client),
            ):
                client.post.return_value = httpx.Response(
                    410,
                    json={"reason": "Unregistered"},
                )
                with self.assertRaises(InvalidDeviceRegistrationError):
                    NativePushAlertSender().send(
                        "ios",
                        "expired-token",
                        self.alert,
                    )

                client.post.return_value = httpx.Response(
                    400,
                    json={"reason": "DeviceTokenNotForTopic"},
                )
                with self.assertRaises(PermanentPushAlertError):
                    NativePushAlertSender().send(
                        "ios",
                        "wrong-topic-token",
                        self.alert,
                    )

    @override_settings(
        FCM_PROJECT_ID="pewcorder-project",
        FCM_SERVICE_ACCOUNT_FILE="/private/firebase.json",
        PUSH_ALERT_TIMEOUT_SECONDS=9,
    )
    def test_fcm_uses_http_v1_oauth_and_maps_unregistered_tokens(self):
        credentials = MagicMock(valid=True, token="oauth-token")
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = httpx.Response(200, json={"name": "message-id"})
        with (
            patch("sermons.push_alerts._fcm_credentials", return_value=credentials),
            patch("sermons.push_alerts.httpx.Client", return_value=client) as factory,
        ):
            NativePushAlertSender().send("android", "fcm-token", self.alert)

        factory.assert_called_once_with(timeout=9)
        client.post.assert_called_once_with(
            "https://fcm.googleapis.com/v1/projects/pewcorder-project/messages:send",
            headers={"authorization": "Bearer oauth-token"},
            json={
                "message": {
                    "token": "fcm-token",
                    "notification": {
                        "title": "Your Sermon is ready",
                        "body": "Study materials are ready.",
                    },
                    "data": {"sermon_id": "sermon-id", "status": "ready"},
                    "android": {"priority": "high"},
                }
            },
        )

        client.post.return_value = httpx.Response(
            404,
            json={
                "error": {
                    "status": "NOT_FOUND",
                    "details": [{"errorCode": "UNREGISTERED"}],
                }
            },
        )
        with (
            patch("sermons.push_alerts._fcm_credentials", return_value=credentials),
            patch("sermons.push_alerts.httpx.Client", return_value=client),
            self.assertRaises(InvalidDeviceRegistrationError),
        ):
            NativePushAlertSender().send("android", "expired-token", self.alert)

    @override_settings(
        FCM_PROJECT_ID="pewcorder-project",
        FCM_SERVICE_ACCOUNT_FILE="/private/firebase.json",
        PUSH_ALERT_TIMEOUT_SECONDS=9,
    )
    def test_fcm_retries_gateway_outages_but_not_configuration_errors(self):
        credentials = MagicMock(valid=True, token="oauth-token")
        client = MagicMock()
        client.__enter__.return_value = client
        with (
            patch("sermons.push_alerts._fcm_credentials", return_value=credentials),
            patch("sermons.push_alerts.httpx.Client", return_value=client),
        ):
            client.post.return_value = httpx.Response(
                503,
                json={"error": {"status": "UNAVAILABLE"}},
            )
            with self.assertRaises(RuntimeError):
                NativePushAlertSender().send("android", "fcm-token", self.alert)

            client.post.return_value = httpx.Response(
                403,
                json={"error": {"status": "PERMISSION_DENIED"}},
            )
            with self.assertRaises(PermanentPushAlertError):
                NativePushAlertSender().send("android", "fcm-token", self.alert)
