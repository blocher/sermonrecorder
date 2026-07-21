import math
from dataclasses import asdict, dataclass
from typing import Protocol

import httpx
from django.conf import settings
from django.utils.module_loading import import_string


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
        try:
            response = httpx.post(
                settings.OVERPASS_API_URL,
                content=query,
                headers={
                    "Content-Type": "text/plain",
                    "User-Agent": settings.OVERPASS_USER_AGENT,
                },
                timeout=settings.CHURCH_SUGGESTION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            elements = response.json().get("elements", [])
        except (httpx.HTTPError, ValueError, AttributeError) as error:
            raise ChurchSuggestionUnavailable(
                "Nearby Churches are temporarily unavailable."
            ) from error

        suggestions: dict[tuple[str, str], ChurchSuggestion] = {}
        for element in elements:
            suggestion = _suggestion(element, latitude, longitude)
            if suggestion is None:
                continue
            identity = (suggestion.name.casefold(), suggestion.address.casefold())
            current = suggestions.get(identity)
            if current is None or suggestion.distance_meters < current.distance_meters:
                suggestions[identity] = suggestion
        return sorted(
            suggestions.values(),
            key=lambda suggestion: (suggestion.distance_meters, suggestion.name),
        )[: settings.CHURCH_SUGGESTION_LIMIT]


def _suggestion(
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
