from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .client import API_BASE, metadata


DEFAULT_STATION_RESOURCE = "klima-v2-10min"
DEFAULT_STATION_ENDPOINT = f"{API_BASE}/station/historical/{DEFAULT_STATION_RESOURCE}"


class MultipleStationsFound(ValueError):
    pass


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    lat: float
    lon: float
    raw: dict[str, Any]

    def historical(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        from .historical import fetch_historical

        return fetch_historical(self, *args, **kwargs)

    def forecast(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        from .forecast import fetch_forecast

        return fetch_forecast(self, *args, **kwargs)


class StationMatches:
    def __init__(self, matches: list[Station]):
        self.matches = matches

    def __len__(self) -> int:
        return len(self.matches)

    def __iter__(self):
        return iter(self.matches)

    def __getitem__(self, index: int) -> Station:
        return self.matches[index]

    def __repr__(self) -> str:
        lines = ["Multiple stations found. Select one with `.select(index)`:"]
        for index, item in enumerate(self.matches):
            lines.append(f"{index}: {item.name} | id={item.id} | lat={item.lat:.5f}, lon={item.lon:.5f}")
        return "\n".join(lines)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"index": i, "id": s.id, "name": s.name, "lat": s.lat, "lon": s.lon}
                for i, s in enumerate(self.matches)
            ]
        )

    def select(self, index: int) -> Station:
        return self.matches[index]


def station(query: str, choose: int | None = None, resource_id: str = DEFAULT_STATION_RESOURCE) -> Station | StationMatches:
    matches = search_station(query, resource_id=resource_id)

    if not matches:
        raise LookupError(f"No station found for {query!r}")

    if choose is not None:
        return matches[choose]

    if len(matches) == 1:
        return matches[0]

    return StationMatches(matches)


def search_station(query: str, resource_id: str = DEFAULT_STATION_RESOURCE) -> list[Station]:
    endpoint = f"{API_BASE}/station/historical/{resource_id}"
    meta = metadata(endpoint)
    stations = meta.get("stations", [])
    query_lower = query.casefold()

    matches: list[Station] = []
    for item in stations:
        name = _station_name(item)
        if query_lower in name.casefold():
            matches.append(_station_from_metadata(item))

    return matches


def _station_from_metadata(item: dict[str, Any]) -> Station:
    return Station(
        id=str(_first_present(item, "id", "station_id", "synop_id", "wmo_id")),
        name=_station_name(item),
        lat=float(_latitude(item)),
        lon=float(_longitude(item)),
        raw=item,
    )


def _station_name(item: dict[str, Any]) -> str:
    value = _first_present(item, "name", "station_name", "display_name", "long_name")
    return str(value)


def _latitude(item: dict[str, Any]) -> float:
    value = _first_present(item, "lat", "latitude", "Lat", "Latitude", "geo_lat", "station_latitude")
    if value is not None:
        return float(value)

    coordinates = _coordinates(item)
    if coordinates:
        return float(coordinates[1])

    raise KeyError(f"No latitude field found for station {item}")


def _longitude(item: dict[str, Any]) -> float:
    value = _first_present(item, "lon", "lng", "longitude", "Lon", "Longitude", "geo_lon", "station_longitude")
    if value is not None:
        return float(value)

    coordinates = _coordinates(item)
    if coordinates:
        return float(coordinates[0])

    raise KeyError(f"No longitude field found for station {item}")


def _coordinates(item: dict[str, Any]) -> list[float] | tuple[float, float] | None:
    geometry = item.get("geometry")
    if isinstance(geometry, dict) and isinstance(geometry.get("coordinates"), (list, tuple)):
        return geometry["coordinates"]

    coordinates = item.get("coordinates")
    if isinstance(coordinates, (list, tuple)):
        return coordinates

    return None


def _first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None:
            return value
    return None
