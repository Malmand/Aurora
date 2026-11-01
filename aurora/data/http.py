"""Small download helper with retries and an explicit 'blocked' error.

CLAUDE.md: if a download is blocked, stop and report. Never substitute data.
"""
from __future__ import annotations

import time
from pathlib import Path

import requests


class DownloadBlocked(RuntimeError):
    """Raised when a source cannot be reached (network policy, quota, outage)."""


def get(url: str, params: dict | None = None, timeout: float = 120,
        retries: int = 4, backoff: float = 4.0) -> requests.Response:
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:  # DNS, proxy refusal, reset
            last = f"{type(exc).__name__}: {exc}"
        else:
            if r.status_code == 200:
                # Open-Meteo reports quota errors as JSON with "error": true
                if r.headers.get("content-type", "").startswith("application/json"):
                    try:
                        js = r.json()
                    except ValueError:
                        js = None
                    if isinstance(js, dict) and js.get("error"):
                        last = f"API error: {js.get('reason')}"
                        if "limit" in str(js.get("reason", "")).lower():
                            break  # quota: retrying now will not help
                        time.sleep(backoff * 2 ** attempt)
                        continue
                return r
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 401, 403, 404):
                break
            if r.status_code == 429 and "limit" in r.text.lower():
                break  # daily quota: retrying now will not help
        time.sleep(backoff * 2 ** attempt)
    raise DownloadBlocked(f"{url} -> {last}")


def download(url: str, dest: Path, force: bool = False) -> Path:
    """Download url to dest once (cached)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest
    r = get(url, timeout=600)
    dest.write_bytes(r.content)
    return dest
