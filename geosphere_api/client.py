from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from requests import HTTPError


API_BASE = "https://dataset.api.hub.geosphere.at/v1"


def get_json(url: str, params: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=timeout)
    try:
        response.raise_for_status()
    except HTTPError as exc:
        detail = _response_detail(response)
        raise HTTPError(f"{exc}\nAPI response: {detail}", response=response) from exc
    return response.json()


@lru_cache(maxsize=32)
def metadata(endpoint: str) -> dict[str, Any]:
    return get_json(f"{endpoint}/metadata")


def _response_detail(response: requests.Response) -> str:
    try:
        return str(response.json())
    except ValueError:
        return response.text[:1000]
