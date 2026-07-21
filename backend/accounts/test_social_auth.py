from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .models import ExternalIdentity
from .social_auth import (
    InvalidSocialCredential,
    SocialProviderUnavailable,
    verify_social_identity,
)


class SocialIdentityVerificationTests(SimpleTestCase):
    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=("pewcorder-web-client",))
    @patch("accounts.social_auth.google_id_token.verify_oauth2_token")
    def test_google_requires_this_apps_audience_and_a_verified_email(self, verify):
        verify.return_value = {
            "aud": "pewcorder-web-client",
            "sub": "google-subject",
            "email": "Listener@Example.com",
            "email_verified": True,
            "name": "A Listener",
        }

        identity = verify_social_identity(
            ExternalIdentity.Provider.GOOGLE,
            "google-id-token",
        )

        self.assertEqual(identity.subject, "google-subject")
        self.assertEqual(identity.email, "listener@example.com")
        self.assertEqual(identity.display_name, "A Listener")

        verify.return_value["aud"] = "another-app"
        with self.assertRaises(InvalidSocialCredential):
            verify_social_identity(
                ExternalIdentity.Provider.GOOGLE,
                "wrong-audience-token",
            )

    @override_settings(APPLE_OAUTH_CLIENT_IDS=("com.pewcorder.app",))
    @patch("accounts.social_auth.jwt.decode")
    @patch("accounts.social_auth._apple_key_client")
    def test_apple_verifies_signature_claims_issuer_and_audience(
        self,
        key_client,
        decode,
    ):
        key_client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(
            key="apple-public-key"
        )
        decode.return_value = {
            "sub": "apple-subject",
            "email": "relay@privaterelay.appleid.com",
            "email_verified": "true",
        }

        identity = verify_social_identity(
            ExternalIdentity.Provider.APPLE,
            "apple-id-token",
        )

        self.assertEqual(identity.subject, "apple-subject")
        self.assertEqual(identity.email, "relay@privaterelay.appleid.com")
        decode.assert_called_once_with(
            "apple-id-token",
            "apple-public-key",
            algorithms=("RS256",),
            audience=("com.pewcorder.app",),
            issuer="https://appleid.apple.com",
            options={"require": ("exp", "iat", "iss", "aud", "sub")},
        )

    @override_settings(GOOGLE_OAUTH_CLIENT_IDS=())
    def test_unconfigured_provider_fails_closed(self):
        with self.assertRaises(SocialProviderUnavailable):
            verify_social_identity(
                ExternalIdentity.Provider.GOOGLE,
                "google-id-token",
            )
