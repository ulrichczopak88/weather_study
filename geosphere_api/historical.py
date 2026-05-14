from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from requests import HTTPError

from .client import API_BASE, get_json, metadata
from .frames import response_to_frame
from .timeutils import api_datetime, time_window


RESOURCE_BY_RESOLUTION = {
    "10min": "klima-v2-10min",
    "1h": "klima-v2-1h",
    "1d": "klima-v2-1d",
}
TAWES_RESOURCE = "tawes-v1-10min"

DEFAULT_PARAMETERS = ("TL", "RF", "P", "FFAM", "FFX", "RR")


def endpoint(resolution: str = "10min", source: str = "klima") -> str:
    if source == "tawes":
        if resolution != "10min":
            raise ValueError("source='tawes' is only available with resolution='10min'")
        return f"{API_BASE}/station/historical/{TAWES_RESOURCE}"

    resource_id = RESOURCE_BY_RESOLUTION[resolution]
    return f"{API_BASE}/station/historical/{resource_id}"


def fetch_historical(
    station: Any,
    time: str | timedelta = "12h",
    resolution: str = "10min",
    parameters: str | list[str] | tuple[str, ...] = DEFAULT_PARAMETERS,
    start: datetime | str | None = None,
    end: datetime | str | None = None,
    timezone: str = "Europe/Vienna",
    source: str = "klima",
    allow_partial: bool = True,
) -> pd.DataFrame:
    if start is None:
        start_value, end_value = time_window(time, end=end)
    else:
        start_value = api_datetime(start)
        end_value = api_datetime(end or datetime.now())

    request_endpoint = endpoint(resolution, source=source)
    params = {
        "station_ids": _station_id_for_endpoint(station, request_endpoint, source=source),
        "parameters": _join(parameters),
        "start": start_value,
        "end": end_value,
    }

    data, skipped = _get_historical_json(request_endpoint, params, allow_partial=allow_partial)
    frame = response_to_frame(data, timezone=timezone)
    _add_parameter_aliases(frame)
    _add_derived_columns(frame)
    frame.attrs.update(
        {
            "kind": "historical",
            "station": station,
            "resolution": resolution,
            "source": source,
            "parameters": params["parameters"],
            "skipped_parameters": skipped,
            "endpoint": request_endpoint,
        }
    )
    return frame


def _join(values: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(values, str):
        return values
    return ",".join(values)


def _get_historical_json(
    request_endpoint: str,
    params: dict[str, Any],
    allow_partial: bool,
) -> tuple[dict[str, Any], list[str]]:
    original_error: HTTPError | None = None
    try:
        return get_json(request_endpoint, params=params), []
    except HTTPError as exc:
        original_error = exc
        if not allow_partial:
            raise

    requested = [part.strip() for part in str(params["parameters"]).split(",") if part.strip()]
    if len(requested) <= 1:
        raise original_error

    merged: dict[str, Any] | None = None
    skipped: list[str] = []

    for parameter in requested:
        single_params = dict(params)
        single_params["parameters"] = parameter
        try:
            data = get_json(request_endpoint, params=single_params)
        except HTTPError:
            skipped.append(parameter)
            continue

        if merged is None:
            merged = data
            continue

        _merge_parameter_data(merged, data)

    if merged is None:
        raise original_error

    return merged, skipped


def _merge_parameter_data(target: dict[str, Any], source: dict[str, Any]) -> None:
    target_features = target.get("features", [])
    source_features = source.get("features", [])

    for target_feature, source_feature in zip(target_features, source_features):
        target_parameters = target_feature.setdefault("properties", {}).setdefault("parameters", {})
        source_parameters = source_feature.get("properties", {}).get("parameters", {})
        target_parameters.update(source_parameters)


def _station_id_for_endpoint(station: Any, request_endpoint: str, source: str) -> str:
    if source != "tawes":
        return str(station.id)

    meta = metadata(request_endpoint)
    stations = meta.get("stations", [])
    station_name = str(getattr(station, "name", "")).casefold()
    station_lat = float(getattr(station, "lat"))
    station_lon = float(getattr(station, "lon"))

    exact = [
        item
        for item in stations
        if str(item.get("name", "")).casefold() == station_name
    ]
    if exact:
        return str(exact[0]["id"])

    nearest = min(
        stations,
        key=lambda item: (float(item.get("lat", 999)) - station_lat) ** 2
        + (float(item.get("lon", 999)) - station_lon) ** 2,
    )
    return str(nearest["id"])


def _add_parameter_aliases(frame: pd.DataFrame) -> None:
    parameter_columns = dict(frame.attrs.get("parameter_columns", {}))

    if "TL" in parameter_columns:
        parameter_columns.setdefault("t2m", parameter_columns["TL"])
        parameter_columns.setdefault("T2M", parameter_columns["TL"])

    if "RR" in parameter_columns:
        parameter_columns.setdefault("rr", parameter_columns["RR"])
        parameter_columns.setdefault("rr_acc", parameter_columns["RR"])

    if "FFX" in parameter_columns:
        parameter_columns.setdefault("gust", parameter_columns["FFX"])

    if "RF" in parameter_columns:
        parameter_columns.setdefault("rh2m", parameter_columns["RF"])
        parameter_columns.setdefault("RH", parameter_columns["RF"])

    if "P" in parameter_columns:
        parameter_columns.setdefault("sp", parameter_columns["P"])
        parameter_columns.setdefault("pressure", parameter_columns["P"])

    if "PRED" in parameter_columns:
        parameter_columns.setdefault("pred", parameter_columns["PRED"])
        parameter_columns.setdefault("reduced_pressure", parameter_columns["PRED"])

    if "pred" in parameter_columns:
        parameter_columns.setdefault("PRED", parameter_columns["pred"])
        parameter_columns.setdefault("reduced_pressure", parameter_columns["pred"])

    frame.attrs["parameter_columns"] = parameter_columns


def _add_derived_columns(frame: pd.DataFrame) -> None:
    parameter_columns = dict(frame.attrs.get("parameter_columns", {}))
    temp_column = parameter_columns.get("TL")
    rh_column = parameter_columns.get("RF")

    if temp_column in frame and rh_column in frame:
        dewpoint = "Taupunkt (deg C)"
        frame[dewpoint] = _dewpoint_c(frame[temp_column], frame[rh_column])
        parameter_columns["TD"] = dewpoint
        parameter_columns["TD2M"] = dewpoint
        parameter_columns["dewpoint"] = dewpoint

    frame.attrs["parameter_columns"] = parameter_columns


def _dewpoint_c(temp_c: pd.Series, rh_percent: pd.Series) -> pd.Series:
    rh = rh_percent.clip(lower=1, upper=100)
    alpha = np.log(rh / 100) + (17.625 * temp_c) / (243.04 + temp_c)
    return (243.04 * alpha) / (17.625 - alpha)
