"""Project root, secrets from .env and optional config.json."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(*keys: str) -> dict[str, str]:
    """Return the requested keys from .env (`key: value`, `key=value` or `key value` lines)."""
    found = {}
    for line in (ROOT / ".env").read_text().splitlines():
        m = re.match(r"\s*(\w+)\s*[:=\s]\s*(\S+)", line)
        if m and m[1] in keys:
            found[m[1]] = m[2].strip("\"'")
    missing = [k for k in keys if k not in found]
    if missing:
        raise RuntimeError(f".env: mancano {', '.join(missing)}")
    return found


def load_config() -> dict:
    path = ROOT / "config.json"
    return json.loads(path.read_text()) if path.exists() else {}
