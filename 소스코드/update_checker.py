"""GitHub 안정 릴리스 조회."""
import json
import re
from urllib.request import Request, urlopen

from config import APP_VERSION, RELEASES_URL


def fetch_update():
    request = Request(
        "https://api.github.com/repos/serotonin-1207/serotonin-baro-capture/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Serotonin-BaroCapture"},
    )
    with urlopen(request, timeout=4) as response:
        release = json.load(response)
    tag = release["tag_name"]
    if not isinstance(tag, str) or not re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Invalid release version")
    version = tag.removeprefix("v")
    if tuple(map(int, version.split("."))) <= tuple(map(int, APP_VERSION.split("."))):
        return None
    return version, RELEASES_URL + "/tag/" + tag, str(release.get("body") or "")
