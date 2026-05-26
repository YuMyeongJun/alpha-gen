from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SEC = 15.0


def base_url() -> str:
    return os.environ.get("ALPHA_GEN_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def api_get(path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url()}{path}"
    if params:
        query = urlencode({k: v for k, v in params.items() if v is not None})
        if query:
            url = f"{url}?{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT_SEC) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Failed to reach {url}: {exc.reason}") from exc
    return json.loads(body)


def format_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
