from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .client import API_BASE, get_json, metadata
from .frames import response_to_frame
from .timeutils import api_datetime


ENDPOINTS = {
    "nowcast": f"{API_BASE}/timeseries/forecast/nowcast-v1-15min-1km",
    "nwp": f"{API_BASE}/timeseries/forecast/nwp-v1-1h-2500m",
}
ENDPOINT = ENDPOINTS["nwp"]
DEFAULT_MODEL = "nwp"
DEFAULT_PARAMETERS_BY_MODEL = {
    "nowcast": ("t2m", "rr"),
    "nwp": ("t2m", "rh2m", "rr_acc", "u10m", "v10m", "sp"),
}
PARAMETER_ALIASES = {
    "nowcast": {
        "TL": "t2m",
        "t2m": "t2m",
        "RR": "rr",
        "rr": "rr",
        "rr_acc": "rr",
    },
    "nwp": {
        "TL": "t2m",
        "T2M": "t2m",
        "t2m": "t2m",
        "RR": "rr_acc",
        "rr": "rr_acc",
        "rr_acc": "rr_acc",
        "RF": "rh2m",
        "RH": "rh2m",
        "rh2m": "rh2m",
        "FF": "u10m,v10m",
        "FFAM": "u10m,v10m",
        "FFX": "ugust,vgust",
        "gust": "ugust,vgust",
        "DD": "u10m,v10m",
        "u10m": "u10m",
        "v10m": "v10m",
        "ugust": "ugust",
        "vgust": "vgust",
        "P": "sp",
        "P0": "sp",
        "PRED": "sp",
        "pred": "sp",
        "pressure": "sp",
        "sp": "sp",
    },
}


def fetch_forecast(
    station: Any,
    max_time: datetime | str | None = None,
    parameters: str | list[str] | tuple[str, ...] | None = None,
    forecast_offset: int = 0,
    timezone: str = "Europe/Vienna",
    model: str = DEFAULT_MODEL,
) -> pd.DataFrame:
    model = _model_key(model)
    endpoint = ENDPOINTS[model]
    params = {
        "lat_lon": f"{station.lat},{station.lon}",
        "parameters": _forecast_parameters(parameters, model=model),
        "forecast_offset": forecast_offset,
    }

    if max_time is not None:
        params["end"] = api_datetime(max_time)

    data = get_json(endpoint, params=params)
    frame = response_to_frame(data, timezone=timezone)
    _add_parameter_aliases(frame)
    _add_derived_columns(frame)
    frame.attrs.update(
        {
            "kind": "forecast",
            "model": model,
            "station": station,
            "parameters": params["parameters"],
            "forecast_offset": forecast_offset,
            "endpoint": endpoint,
        }
    )
    return frame


def forecast_metadata(model: str = DEFAULT_MODEL) -> dict[str, Any]:
    return metadata(ENDPOINTS[_model_key(model)])


def forecast_parameters(model: str = DEFAULT_MODEL) -> pd.DataFrame:
    meta = forecast_metadata(model=model)
    parameters = meta.get("parameters", {})

    rows = []
    if isinstance(parameters, dict):
        items = parameters.items()
    else:
        items = [(value.get("name"), value) for value in parameters]

    for key, value in items:
        rows.append(
            {
                "parameter": key,
                "name": value.get("name"),
                "unit": value.get("unit"),
                "description": value.get("description"),
            }
        )

    return pd.DataFrame(rows)


def _join(values: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(values, str):
        return values
    return ",".join(values)


def _forecast_parameters(values: str | list[str] | tuple[str, ...] | None, model: str = DEFAULT_MODEL) -> str:
    if values is None:
        values = DEFAULT_PARAMETERS_BY_MODEL[_model_key(model)]

    if isinstance(values, str):
        values = [part.strip() for part in values.split(",")]

    aliases = PARAMETER_ALIASES[_model_key(model)]
    mapped: list[str] = []
    for value in values:
        mapped.extend(part.strip() for part in aliases.get(value, value).split(","))

    return ",".join(dict.fromkeys(mapped))


def _add_parameter_aliases(frame: pd.DataFrame) -> None:
    parameter_columns = dict(frame.attrs.get("parameter_columns", {}))

    if "t2m" in parameter_columns:
        parameter_columns.setdefault("TL", parameter_columns["t2m"])
        parameter_columns.setdefault("T2M", parameter_columns["t2m"])

    if "T2M" in parameter_columns:
        parameter_columns.setdefault("TL", parameter_columns["T2M"])
        parameter_columns.setdefault("t2m", parameter_columns["T2M"])

    if "rr" in parameter_columns:
        parameter_columns.setdefault("RR", parameter_columns["rr"])
        parameter_columns.setdefault("rr_acc", parameter_columns["rr"])

    if "RR" in parameter_columns:
        parameter_columns.setdefault("rr", parameter_columns["RR"])

    if "rr_acc" in parameter_columns:
        parameter_columns.setdefault("RR", parameter_columns["rr_acc"])
        parameter_columns.setdefault("rr", parameter_columns["rr_acc"])
        precip = "Niederschlag pro Stunde (mm)"
        frame[precip] = frame[parameter_columns["rr_acc"]].diff().clip(lower=0)
        parameter_columns["RR_RATE"] = precip
        parameter_columns["precipitation"] = precip

    if "rh2m" in parameter_columns:
        parameter_columns.setdefault("RF", parameter_columns["rh2m"])
        parameter_columns.setdefault("RH", parameter_columns["rh2m"])

    if "sp" in parameter_columns:
        parameter_columns.setdefault("P", parameter_columns["sp"])
        parameter_columns.setdefault("PRED", parameter_columns["sp"])
        parameter_columns.setdefault("pred", parameter_columns["sp"])
        parameter_columns.setdefault("pressure", parameter_columns["sp"])

    frame.attrs["parameter_columns"] = parameter_columns


def _add_derived_columns(frame: pd.DataFrame) -> None:
    parameter_columns = dict(frame.attrs.get("parameter_columns", {}))

    temp_column = parameter_columns.get("t2m")
    if temp_column in frame and frame[temp_column].mean(skipna=True) > 100:
        celsius = f"{temp_column} derived Celsius"
        frame[celsius] = frame[temp_column] - 273.15
        parameter_columns["t2m"] = celsius
        parameter_columns["TL"] = celsius
        parameter_columns["T2M"] = celsius

    temp_column = parameter_columns.get("t2m")
    rh_column = parameter_columns.get("rh2m")
    if temp_column in frame and rh_column in frame:
        dewpoint = "Taupunkt (deg C)"
        frame[dewpoint] = _dewpoint_c(frame[temp_column], frame[rh_column])
        parameter_columns["TD"] = dewpoint
        parameter_columns["TD2M"] = dewpoint
        parameter_columns["dewpoint"] = dewpoint

    u_column = parameter_columns.get("u10m")
    v_column = parameter_columns.get("v10m")
    if u_column in frame and v_column in frame:
        speed = "Windgeschwindigkeit 10m (m/s)"
        direction = "Windrichtung 10m (deg)"
        frame[speed] = np.sqrt(frame[u_column] ** 2 + frame[v_column] ** 2)
        frame[direction] = (270 - np.degrees(np.arctan2(frame[v_column], frame[u_column]))) % 360
        parameter_columns["FF"] = speed
        parameter_columns["FFAM"] = speed
        parameter_columns["wind_speed"] = speed
        parameter_columns["DD"] = direction
        parameter_columns["wind_direction"] = direction

    ugust_column = parameter_columns.get("ugust")
    vgust_column = parameter_columns.get("vgust")
    if ugust_column in frame and vgust_column in frame:
        gust = "Windboe 10m (m/s)"
        frame[gust] = np.sqrt(frame[ugust_column] ** 2 + frame[vgust_column] ** 2)
        parameter_columns["FFX"] = gust
        parameter_columns["gust"] = gust

    frame.attrs["parameter_columns"] = parameter_columns


def _dewpoint_c(temp_c: pd.Series, rh_percent: pd.Series) -> pd.Series:
    rh = rh_percent.clip(lower=1, upper=100)
    alpha = np.log(rh / 100) + (17.625 * temp_c) / (243.04 + temp_c)
    return (243.04 * alpha) / (17.625 - alpha)


def _model_key(model: str) -> str:
    key = str(model).casefold()
    if key not in ENDPOINTS:
        allowed = "', '".join(ENDPOINTS)
        raise ValueError(f"Unknown forecast model {model!r}. Use one of '{allowed}'.")
    return key
