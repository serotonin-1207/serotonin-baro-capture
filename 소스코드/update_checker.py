from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    notes: str
    page_url: str
    is_newer: bool


def semantic_version(value: str) -> tuple[int, int, int]:
    match = re.search(r"(?i)(?:^|[^0-9])v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", value.strip())
    if not match:
        raise ValueError(f"버전 형식을 읽을 수 없습니다: {value}")
    return tuple(int(part or 0) for part in match.groups())


def fetch_latest_release(repository: str, current_version: str, timeout: float = 4.0) -> ReleaseInfo:
    url = f"https://api.github.com/repos/{repository}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Serotonin-BaroCapture-Updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
        latest = str(payload["tag_name"])
        return ReleaseInfo(
            version=latest,
            notes=str(payload.get("body") or ""),
            page_url=str(payload.get("html_url") or ""),
            is_newer=semantic_version(latest) > semantic_version(current_version),
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError) as error:
        raise UpdateCheckError("인터넷 연결 또는 GitHub 릴리스 정보를 확인해 주세요.") from error
