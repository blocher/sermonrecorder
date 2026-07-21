from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .church_suggestions import (
    ChurchSuggestion,
    OverpassChurchSuggestionProvider,
)


class FakeChurchSuggestionProvider:
    calls = []

    def nearby(self, latitude, longitude, radius_meters):
        self.calls.append((latitude, longitude, radius_meters))
        return [
            ChurchSuggestion(
                provider_id="osm:node:42",
                name="Grace Parish",
                address="12 Cedar Lane",
                latitude=40.001,
                longitude=-75.001,
                distance_meters=140,
            )
        ]


@override_settings(
    OVERPASS_API_URL="https://overpass.example.test/interpreter",
    OVERPASS_USER_AGENT="Pewcorder tests",
    CHURCH_SUGGESTION_TIMEOUT_SECONDS=7,
    CHURCH_SUGGESTION_LIMIT=5,
)
class OverpassChurchSuggestionProviderTests(SimpleTestCase):
    def test_maps_deduplicates_and_orders_named_christian_places(self):
        response = httpx.Response(
            200,
            request=httpx.Request(
                "POST",
                "https://overpass.example.test/interpreter",
            ),
            json={
                "elements": [
                    {
                        "type": "way",
                        "id": 2,
                        "center": {"lat": 40.002, "lon": -75.002},
                        "tags": {
                            "name": "Grace Parish",
                            "addr:housenumber": "12",
                            "addr:street": "Cedar Lane",
                        },
                    },
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 40.001,
                        "lon": -75.001,
                        "tags": {
                            "name": "Grace Parish",
                            "addr:full": "12 Cedar Lane",
                        },
                    },
                    {"type": "node", "id": 3, "lat": 40, "lon": -75, "tags": {}},
                ]
            },
        )
        with patch(
            "sermons.church_suggestions.httpx.post", return_value=response
        ) as post:
            suggestions = OverpassChurchSuggestionProvider().nearby(40, -75, 1_500)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].provider_id, "osm:node:1")
        self.assertEqual(suggestions[0].address, "12 Cedar Lane")
        post.assert_called_once()
        self.assertIn('["religion"="christian"]', post.call_args.kwargs["content"])
        self.assertEqual(
            post.call_args.kwargs["headers"]["User-Agent"], "Pewcorder tests"
        )


@override_settings(
    CHURCH_SUGGESTION_PROVIDER=(
        "sermons.test_church_suggestions.FakeChurchSuggestionProvider"
    )
)
class ChurchSuggestionApiTests(APITestCase):
    def setUp(self):
        FakeChurchSuggestionProvider.calls = []
        self.user = User.objects.create_user(
            email="location-owner@example.com",
            password="safe-test-password",
        )

    def test_suggestions_require_auth_and_do_not_persist_the_precise_fix(self):
        url = "/api/sermons/churches/suggestions/"
        denied = self.client.post(
            url,
            {"latitude": 40, "longitude": -75},
            format="json",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            url,
            {"latitude": 40, "longitude": -75, "radius_meters": 900},
            format="json",
        )

        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "Grace Parish")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(FakeChurchSuggestionProvider.calls, [(40.0, -75.0, 900)])
        self.assertEqual(self.user.churches.count(), 0)

    def test_rejects_invalid_or_excessively_broad_coordinates(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/sermons/churches/suggestions/",
            {"latitude": 91, "longitude": -75, "radius_meters": 10_000},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(FakeChurchSuggestionProvider.calls, [])
