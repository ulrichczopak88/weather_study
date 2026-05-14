from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re


_DURATION_RE = re.compile(r"^\s*(\d+)\s*(min|m|h|d|w)\s*$", re.IGNORECASE)


def parse_duration(value: str | timedelta) -> timedelta:
    if isinstance(value, timedelta):
        return value

    match = _DURATION_RE.match(value)
    if not match:
        raise ValueError("time must look like '12h', '3d', '90min' or be a timedelta")

    amount = int(match.group(1))
    unit = match.group(2).lower()

    if unit in {"min", "m"}:
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    if unit == "w":
        return timedelta(weeks=amount)

    raise ValueError(f"Unsupported duration unit: {unit}")


def api_datetime(value: datetime | str) -> str:
    if isinstance(value, str):
        return value

    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)

    return value.strftime("%Y-%m-%dT%H:%M")


def time_window(time: str | timedelta, end: datetime | str | None = None) -> tuple[str, str]:
    end_dt = datetime.now(timezone.utc) if end is None else _as_datetime(end)
    start_dt = end_dt - parse_duration(time)
    return api_datetime(start_dt), api_datetime(end_dt)


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value

    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
