"""Spec icons from the WarcraftLogs CDN, cached on disk and returned as inline data URIs."""
import base64
import logging
import re
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

from blazettino.config import ROOT

log = logging.getLogger(__name__)

CACHE_DIR = ROOT / "cache" / "icons"
URL = "https://assets.rpglogs.com/img/warcraft/icons/{name}.jpg"
TIMEOUT_S = 15
SAFE_NAME = re.compile(r"^[A-Za-z]+-[A-Za-z]+$")  # e.g. Priest-Holy: also keeps names out of file paths


def _download(name: str) -> bytes:
    req = urllib.request.Request(URL.format(name=name), headers={"User-Agent": "Blazettino/1.0"})
    return urllib.request.urlopen(req, timeout=TIMEOUT_S).read()


def fetch(
    names: Iterable[str],
    cache_dir: Path = CACHE_DIR,
    download: Callable[[str], bytes] = _download,
) -> dict[str, str]:
    """name -> 'data:image/jpeg;base64,...'; icons that cannot be fetched are skipped (the page works without)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in names:
        if not SAFE_NAME.match(name):
            log.warning("nome icona non valido: %r", name)
            continue
        path = cache_dir / f"{name}.jpg"
        try:
            if not path.exists():
                path.write_bytes(download(name))
            out[name] = "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()
        except OSError as e:
            log.warning("icona %s non disponibile (%s)", name, e)
    return out
