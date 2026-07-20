from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


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
