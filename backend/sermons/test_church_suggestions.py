from unittest.mock import patch

import httpx
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .church_suggestions import (
    ChurchSuggestion,
    ChurchSuggestionUnavailable,
    GooglePlacesChurchSuggestionProvider,
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


def _overpass_response(url: str, payload: dict | None = None, status_code: int = 200):
    request = httpx.Request("POST", url)
    if status_code >= 400:
        response = httpx.Response(status_code, request=request)
        return response
    return httpx.Response(status_code, request=request, json=payload or {"elements": []})


@override_settings(
    OVERPASS_API_URLS=["https://overpass.example.test/interpreter"],
    OVERPASS_API_URL="https://overpass.example.test/interpreter",
    OVERPASS_USER_AGENT="Pewcorder tests",
    CHURCH_SUGGESTION_TIMEOUT_SECONDS=7,
    CHURCH_SUGGESTION_LIMIT=5,
)
class OverpassChurchSuggestionProviderTests(SimpleTestCase):
    def test_maps_deduplicates_and_orders_named_christian_places(self):
        response = _overpass_response(
            "https://overpass.example.test/interpreter",
            {
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

    def test_retries_next_overpass_mirror_after_retryable_failure(self):
        urls = [
            "https://overpass-a.example.test/interpreter",
            "https://overpass-b.example.test/interpreter",
        ]
        busy = _overpass_response(urls[0], status_code=504)
        ok = _overpass_response(
            urls[1],
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 9,
                        "lat": 40.001,
                        "lon": -75.001,
                        "tags": {
                            "name": "Grace Parish",
                            "addr:full": "12 Cedar Lane",
                        },
                    }
                ]
            },
        )
        with override_settings(OVERPASS_API_URLS=urls, OVERPASS_API_URL=urls[0]):
            with patch(
                "sermons.church_suggestions.httpx.post",
                side_effect=[busy, ok],
            ) as post:
                suggestions = OverpassChurchSuggestionProvider().nearby(40, -75, 1_500)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].name, "Grace Parish")
        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            urls,
        )

    def test_raises_when_every_overpass_mirror_fails(self):
        urls = [
            "https://overpass-a.example.test/interpreter",
            "https://overpass-b.example.test/interpreter",
        ]
        with override_settings(OVERPASS_API_URLS=urls, OVERPASS_API_URL=urls[0]):
            with patch(
                "sermons.church_suggestions.httpx.post",
                side_effect=[
                    _overpass_response(urls[0], status_code=429),
                    _overpass_response(urls[1], status_code=503),
                ],
            ):
                with self.assertRaises(ChurchSuggestionUnavailable):
                    OverpassChurchSuggestionProvider().nearby(40, -75, 1_500)


@override_settings(
    GOOGLE_PLACES_API_KEY="test-places-key",
    GOOGLE_PLACES_NEARBY_SEARCH_URL="https://places.example.test/v1/places:searchNearby",
    CHURCH_SUGGESTION_TIMEOUT_SECONDS=7,
    CHURCH_SUGGESTION_LIMIT=5,
)
class GooglePlacesChurchSuggestionProviderTests(SimpleTestCase):
    def test_maps_distance_ordered_churches_from_nearby_search(self):
        response = httpx.Response(
            200,
            request=httpx.Request(
                "POST",
                "https://places.example.test/v1/places:searchNearby",
            ),
            json={
                "places": [
                    {
                        "id": "abc",
                        "displayName": {"text": "Grace Parish"},
                        "formattedAddress": "12 Cedar Lane, Philadelphia, PA",
                        "location": {"latitude": 40.001, "longitude": -75.001},
                    },
                    {
                        "id": "def",
                        "displayName": {"text": "  "},
                        "formattedAddress": "No Name Ave",
                        "location": {"latitude": 40.002, "longitude": -75.002},
                    },
                ]
            },
        )
        with patch(
            "sermons.church_suggestions.httpx.post", return_value=response
        ) as post:
            suggestions = GooglePlacesChurchSuggestionProvider().nearby(40, -75, 1_500)

        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].provider_id, "google:abc")
        self.assertEqual(suggestions[0].name, "Grace Parish")
        self.assertEqual(
            suggestions[0].address, "12 Cedar Lane, Philadelphia, PA"
        )
        headers = post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Goog-Api-Key"], "test-places-key")
        self.assertIn("places.displayName", headers["X-Goog-FieldMask"])
        self.assertEqual(post.call_args.kwargs["json"]["includedTypes"], ["church"])
        self.assertEqual(post.call_args.kwargs["json"]["rankPreference"], "DISTANCE")

    def test_requires_api_key_and_maps_provider_errors(self):
        with override_settings(GOOGLE_PLACES_API_KEY=""):
            with self.assertRaises(ChurchSuggestionUnavailable):
                GooglePlacesChurchSuggestionProvider().nearby(40, -75, 1_500)

        error_response = httpx.Response(
            403,
            request=httpx.Request(
                "POST",
                "https://places.example.test/v1/places:searchNearby",
            ),
        )
        with patch(
            "sermons.church_suggestions.httpx.post",
            return_value=error_response,
        ):
            with self.assertRaises(ChurchSuggestionUnavailable):
                GooglePlacesChurchSuggestionProvider().nearby(40, -75, 1_500)


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
