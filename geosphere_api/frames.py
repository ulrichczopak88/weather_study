from __future__ import annotations

from typing import Any

import pandas as pd


def response_to_frame(data: dict[str, Any], timezone: str = "Europe/Vienna") -> pd.DataFrame:
    timestamps = pd.to_datetime(data.get("timestamps", []), utc=True)
    if timezone:
        timestamps = timestamps.tz_convert(timezone)

    frames: list[pd.DataFrame] = []
    parameter_columns: dict[str, str] = {}
    feature_parameter_columns: list[dict[str, Any]] = []
    features = data.get("features", [])

    for index, feature in enumerate(features):
        props = feature.get("properties", {})
        parameters = props.get("parameters", {})
        prefix = _feature_prefix(props, index, len(features))

        columns: dict[str, Any] = {}
        feature_columns: dict[str, str] = {}
        for key, parameter in parameters.items():
            values = parameter.get("data")
            if values is None:
                continue

            name = parameter.get("name") or key
            unit = parameter.get("unit")
            label = f"{name} ({unit})" if unit else name
            if prefix:
                label = f"{prefix}: {label}"
            columns[label] = values
            parameter_columns.setdefault(key, label)
            if prefix:
                parameter_columns[f"{prefix}:{key}"] = label
            feature_columns[key] = label

        if columns:
            frames.append(pd.DataFrame(columns, index=timestamps))
            feature_parameter_columns.append(
                {
                    "prefix": prefix,
                    "properties": props,
                    "parameter_columns": feature_columns,
                }
            )

    if not frames:
        frame = pd.DataFrame(index=timestamps)
        frame.attrs["parameter_columns"] = parameter_columns
        frame.attrs["feature_parameter_columns"] = feature_parameter_columns
        return frame

    frame = pd.concat(frames, axis=1)
    frame.attrs["parameter_columns"] = parameter_columns
    frame.attrs["feature_parameter_columns"] = feature_parameter_columns
    return frame


def _feature_prefix(props: dict[str, Any], index: int, feature_count: int) -> str:
    if feature_count <= 1:
        return ""

    for key in ("station", "station_name", "name", "id", "station_id"):
        value = props.get(key)
        if value:
            return str(value)

    return f"feature_{index}"
