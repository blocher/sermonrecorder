from rest_framework import status
from rest_framework.test import APITestCase

from .models import SavedRecipient, User


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
