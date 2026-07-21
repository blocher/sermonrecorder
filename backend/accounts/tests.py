from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import DeviceRegistration, ExternalIdentity, SavedRecipient, User
from .social_auth import InvalidSocialCredential, VerifiedSocialIdentity
from sermons.models import ProcessingAlert, Sermon


class AccountApiTests(APITestCase):
    def test_registration_returns_tokens_and_current_user(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "Congregant@Example.com",
                "display_name": "A Congregant",
                "password": "a-secure-pew-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], "Congregant@example.com")
        self.assertEqual(User.objects.count(), 1)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        current_user = self.client.get("/api/auth/me/")
        self.assertEqual(current_user.status_code, status.HTTP_200_OK)
        self.assertEqual(current_user.data["display_name"], "A Congregant")

    def test_email_and_password_issue_a_jwt_pair(self):
        User.objects.create_user(
            email="listener@example.com", password="strong-password"
        )

        response = self.client.post(
            "/api/auth/token/",
            {"email": "listener@example.com", "password": "strong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    @patch("accounts.views.verify_social_identity")
    def test_verified_social_identity_creates_and_reuses_one_account(self, verify):
        verify.side_effect = (
            VerifiedSocialIdentity(
                provider=ExternalIdentity.Provider.GOOGLE,
                subject="google-account-123",
                email="listener@example.com",
                display_name="A Listener",
            ),
            VerifiedSocialIdentity(
                provider=ExternalIdentity.Provider.GOOGLE,
                subject="google-account-123",
                email=None,
            ),
        )

        created = self.client.post(
            "/api/auth/social/",
            {"provider": "google", "id_token": "first-google-token"},
            format="json",
        )
        repeated = self.client.post(
            "/api/auth/social/",
            {"provider": "google", "id_token": "later-google-token"},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(created.data["user"], repeated.data["user"])
        self.assertIn("access", created.data)
        self.assertIn("refresh", created.data)
        user = User.objects.get()
        self.assertEqual(user.email, "listener@example.com")
        self.assertEqual(user.display_name, "A Listener")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.external_identities.count(), 1)

    @patch("accounts.views.verify_social_identity")
    def test_social_identity_links_a_matching_existing_private_library(self, verify):
        user = User.objects.create_user(
            email="listener@example.com",
            password="existing-password",
            display_name="Existing Listener",
        )
        verify.return_value = VerifiedSocialIdentity(
            provider=ExternalIdentity.Provider.APPLE,
            subject="apple-private-subject",
            email="LISTENER@example.com",
        )

        response = self.client.post(
            "/api/auth/social/",
            {"provider": "apple", "id_token": "apple-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["id"], str(user.id))
        self.assertTrue(user.has_usable_password())
        self.assertTrue(
            ExternalIdentity.objects.filter(
                owner=user,
                provider=ExternalIdentity.Provider.APPLE,
                subject="apple-private-subject",
            ).exists()
        )

    @patch("accounts.views.verify_social_identity")
    def test_rejected_provider_credential_never_creates_an_account(self, verify):
        verify.side_effect = InvalidSocialCredential(
            "Google rejected this sign-in credential."
        )

        response = self.client.post(
            "/api/auth/social/",
            {"provider": "google", "id_token": "forged-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())
        self.assertFalse(ExternalIdentity.objects.exists())

    @patch("accounts.views.verify_social_identity")
    def test_social_sign_in_respects_account_deactivation(self, verify):
        user = User.objects.create_user(
            email="inactive@example.com",
            password=None,
            is_active=False,
        )
        ExternalIdentity.objects.create(
            owner=user,
            provider=ExternalIdentity.Provider.GOOGLE,
            subject="inactive-google-subject",
        )
        verify.return_value = VerifiedSocialIdentity(
            provider=ExternalIdentity.Provider.GOOGLE,
            subject="inactive-google-subject",
            email="inactive@example.com",
        )

        response = self.client.post(
            "/api/auth/social/",
            {"provider": "google", "id_token": "valid-provider-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SavedRecipientApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="recipient-owner@example.com",
            password="strong-password",
        )
        self.other_user = User.objects.create_user(
            email="recipient-other@example.com",
            password="strong-password",
        )

    def test_congregant_can_save_and_reuse_normalized_email_recipients(self):
        self.client.force_authenticate(user=self.user)

        created = self.client.post(
            "/api/auth/recipients/",
            {"name": "  Family group  ", "email": "FAMILY@EXAMPLE.COM"},
            format="json",
        )
        listed = self.client.get("/api/auth/recipients/")
        duplicate = self.client.post(
            "/api/auth/recipients/",
            {"name": "Family again", "email": "family@example.com"},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["name"], "Family group")
        self.assertEqual(created.data["email"], "family@example.com")
        self.assertEqual(listed.data, [created.data])
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_saved_recipient_changes_are_owner_only(self):
        recipient = SavedRecipient.objects.create(
            owner=self.user,
            name="Anna",
            email="anna@example.com",
        )
        url = f"/api/auth/recipients/{recipient.id}/"
        self.client.force_authenticate(user=self.other_user)

        hidden = self.client.get(url)
        denied_update = self.client.patch(url, {"name": "Taken"}, format="json")
        denied_delete = self.client.delete(url)

        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(denied_update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(denied_delete.status_code, status.HTTP_404_NOT_FOUND)
        recipient.refresh_from_db()
        self.assertEqual(recipient.name, "Anna")


class DeviceRegistrationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="device-owner@example.com",
            password="strong-password",
        )
        self.other_user = User.objects.create_user(
            email="device-other@example.com",
            password="strong-password",
        )

    def test_native_token_is_private_and_follows_the_current_account(self):
        self.client.force_authenticate(user=self.user)
        created = self.client.post(
            "/api/auth/devices/",
            {"platform": "ios", "token": "  native-push-token  "},
            format="json",
        )
        registration = DeviceRegistration.objects.get()
        sermon = Sermon.objects.create(
            owner=self.user,
            source_draft_id="device-registration-alert",
            captured_at=timezone.now(),
            duration_seconds=60,
            audio_mime_type="audio/mp4",
            audio_size_bytes=1,
        )
        ProcessingAlert.objects.create(
            sermon=sermon,
            device=registration,
            processing_status=Sermon.ProcessingStatus.READY,
        )
        self.client.force_authenticate(user=self.other_user)
        reassigned = self.client.post(
            "/api/auth/devices/",
            {"platform": "android", "token": "native-push-token"},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("token", created.data)
        self.assertEqual(reassigned.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reassigned.data["id"], created.data["id"])
        registration.refresh_from_db()
        self.assertEqual(registration.owner, self.other_user)
        self.assertEqual(registration.platform, DeviceRegistration.Platform.ANDROID)
        self.assertTrue(registration.active)
        self.assertFalse(ProcessingAlert.objects.exists())

    def test_device_registration_deletion_is_owner_only(self):
        registration = DeviceRegistration.objects.create(
            owner=self.user,
            platform=DeviceRegistration.Platform.IOS,
            token="private-native-token",
        )
        url = f"/api/auth/devices/{registration.id}/"
        self.client.force_authenticate(user=self.other_user)
        hidden = self.client.delete(url)
        self.client.force_authenticate(user=self.user)
        removed = self.client.delete(url)

        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeviceRegistration.objects.exists())
