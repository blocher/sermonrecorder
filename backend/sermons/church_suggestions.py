import logging
import math
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx
from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class ChurchSuggestionUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ChurchSuggestion:
    provider_id: str
    name: str
    address: str
    latitude: float
    longitude: float
    distance_meters: int

    def payload(self) -> dict:
        return asdict(self)


class ChurchSuggestionProvider(Protocol):
    def nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[ChurchSuggestion]: ...


class OverpassChurchSuggestionProvider:
    def nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[ChurchSuggestion]:
        query = f"""
[out:json][timeout:15];
(
  nwr(around:{radius_meters},{latitude},{longitude})["amenity"="place_of_worship"]["religion"="christian"];
  nwr(around:{radius_meters},{latitude},{longitude})["building"~"^(church|cathedral|chapel)$"];
);
out center tags;
""".strip()
        elements = _fetch_overpass_elements(query)
        return _dedupe_and_limit(
            (
                suggestion
                for element in elements
                if (suggestion := _overpass_suggestion(element, latitude, longitude))
                is not None
            )
        )


class GooglePlacesChurchSuggestionProvider:
    """Nearby Search (New) for churches. Requires GOOGLE_PLACES_API_KEY."""

    def nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
    ) -> list[ChurchSuggestion]:
        api_key = (getattr(settings, "GOOGLE_PLACES_API_KEY", "") or "").strip()
        if not api_key:
            raise ChurchSuggestionUnavailable(
                "Nearby Churches are temporarily unavailable."
            )

        max_results = max(1, min(int(settings.CHURCH_SUGGESTION_LIMIT), 20))
        try:
            response = httpx.post(
                settings.GOOGLE_PLACES_NEARBY_SEARCH_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    # Pro SKU fields only — name, address, coordinates, id.
                    "X-Goog-FieldMask": (
                        "places.id,places.displayName,"
                        "places.formattedAddress,places.location"
                    ),
                },
                json={
                    "includedTypes": ["church"],
                    "maxResultCount": max_results,
                    "rankPreference": "DISTANCE",
                    "locationRestriction": {
                        "circle": {
                            "center": {
                                "latitude": latitude,
                                "longitude": longitude,
                            },
                            "radius": float(radius_meters),
                        }
                    },
                },
                timeout=settings.CHURCH_SUGGESTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            places = response.json().get("places", [])
        except (httpx.HTTPError, ValueError, AttributeError, TypeError) as error:
            logger.info("Google Places Nearby Search failed: %s", error)
            raise ChurchSuggestionUnavailable(
                "Nearby Churches are temporarily unavailable."
            ) from error

        return _dedupe_and_limit(
            (
                suggestion
                for place in places
                if (suggestion := _google_place_suggestion(place, latitude, longitude))
                is not None
            )
        )


def _dedupe_and_limit(suggestions) -> list[ChurchSuggestion]:
    unique: dict[tuple[str, str], ChurchSuggestion] = {}
    for suggestion in suggestions:
        identity = (suggestion.name.casefold(), suggestion.address.casefold())
        current = unique.get(identity)
        if current is None or suggestion.distance_meters < current.distance_meters:
            unique[identity] = suggestion
    return sorted(
        unique.values(),
        key=lambda item: (item.distance_meters, item.name),
    )[: settings.CHURCH_SUGGESTION_LIMIT]


def _overpass_endpoints() -> list[str]:
    urls = getattr(settings, "OVERPASS_API_URLS", None)
    if urls:
        return list(urls)
    primary = getattr(settings, "OVERPASS_API_URL", "")
    return [primary] if primary else []


def _is_retryable_overpass_error(error: Exception) -> bool:
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(error, (ValueError, AttributeError)):
        return True
    return False


def _fetch_overpass_elements(query: str) -> list:
    endpoints = _overpass_endpoints()
    if not endpoints:
        raise ChurchSuggestionUnavailable(
            "Nearby Churches are temporarily unavailable."
        )

    last_error: Exception | None = None
    headers = {
        "Content-Type": "text/plain",
        "User-Agent": settings.OVERPASS_USER_AGENT,
    }
    timeout = settings.CHURCH_SUGGESTION_TIMEOUT_SECONDS

    for index, url in enumerate(endpoints):
        try:
            response = httpx.post(
                url,
                content=query,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("elements", [])
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            last_error = error
            remaining = index < len(endpoints) - 1
            if remaining and _is_retryable_overpass_error(error):
                logger.info(
                    "Overpass endpoint %s failed (%s); trying next mirror.",
                    url,
                    error,
                )
                continue
            break

    raise ChurchSuggestionUnavailable(
        "Nearby Churches are temporarily unavailable."
    ) from last_error


def _overpass_suggestion(
    element: dict,
    origin_latitude: float,
    origin_longitude: float,
) -> ChurchSuggestion | None:
    tags = element.get("tags") or {}
    name = " ".join(str(tags.get("name", "")).split())
    point = element.get("center") or element
    try:
        latitude = float(point["lat"])
        longitude = float(point["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not name:
        return None

    address = tags.get("addr:full") or " ".join(
        part
        for part in (
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
            tags.get("addr:state"),
        )
        if part
    )
    return ChurchSuggestion(
        provider_id=f"osm:{element.get('type', 'element')}:{element.get('id', '')}",
        name=name,
        address=" ".join(str(address).split()),
        latitude=latitude,
        longitude=longitude,
        distance_meters=round(
            _distance_meters(
                origin_latitude,
                origin_longitude,
                latitude,
                longitude,
            )
        ),
    )


def _google_place_suggestion(
    place: dict,
    origin_latitude: float,
    origin_longitude: float,
) -> ChurchSuggestion | None:
    display = place.get("displayName") or {}
    name = " ".join(str(display.get("text", "")).split())
    if not name:
        return None
    location = place.get("location") or {}
    try:
        latitude = float(location["latitude"])
        longitude = float(location["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    place_id = str(place.get("id") or "").strip()
    if not place_id:
        resource_name = str(place.get("name") or "").strip()
        place_id = resource_name.removeprefix("places/") if resource_name else ""
    if not place_id:
        return None
    address = " ".join(str(place.get("formattedAddress") or "").split())
    return ChurchSuggestion(
        provider_id=f"google:{place_id}",
        name=name,
        address=address,
        latitude=latitude,
        longitude=longitude,
        distance_meters=round(
            _distance_meters(
                origin_latitude,
                origin_longitude,
                latitude,
                longitude,
            )
        ),
    )


def _distance_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius_meters = 6_371_000
    latitude_a_radians = math.radians(latitude_a)
    latitude_b_radians = math.radians(latitude_b)
    latitude_delta = math.radians(latitude_b - latitude_a)
    longitude_delta = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude_a_radians)
        * math.cos(latitude_b_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return (
        earth_radius_meters
        * 2
        * math.atan2(
            math.sqrt(haversine),
            math.sqrt(1 - haversine),
        )
    )


def get_church_suggestion_provider() -> ChurchSuggestionProvider:
    provider_class = import_string(settings.CHURCH_SUGGESTION_PROVIDER)
    return provider_class()
