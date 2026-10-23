"""WarcraftLogs v2 client: OAuth client-credentials, GraphQL, JSON cache on disk."""
import base64
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request

from blazettino.config import ROOT, env

CACHE = ROOT / "cache"
API = "https://www.warcraftlogs.com"
log = logging.getLogger(__name__)

MAX_WAITS = 24  # hourly resets to wait through before giving up (a whole day)
RESET_GUESS_S = 600  # when even the rate-limit query is refused
RESET_MARGIN_S = 5


_token = None


def _auth() -> str:
    global _token
    if _token is None:
        c = env("clientId", "secret")
        basic = base64.b64encode(f"{c['clientId']}:{c['secret']}".encode()).decode()
        req = urllib.request.Request(
            f"{API}/oauth/token",
            data=b"grant_type=client_credentials",
            headers={"Authorization": f"Basic {basic}"},
        )
        _token = json.load(urllib.request.urlopen(req))["access_token"]
    return _token


def _post(query: str) -> dict:
    req = urllib.request.Request(
        f"{API}/api/v2/client",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {_auth()}", "Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req))


def _is_rate_limit(out: dict) -> bool:
    return "rate limit" in json.dumps(out.get("errors", "")).lower()


def _wait_for_reset(attempt: int) -> None:
    """The hourly points are used up: sleep until they come back (collecting data is not urgent, the cache keeps progress)."""
    try:
        secs = _post("{rateLimitData{pointsResetIn}}")["data"]["rateLimitData"]["pointsResetIn"]
    except (OSError, KeyError, TypeError, ValueError):
        secs = RESET_GUESS_S
    log.warning("punti WarcraftLogs esauriti: aspetto %d minuti (attesa %d/%d), i dati gia' scaricati restano in cache",
                secs // 60 + 1, attempt, MAX_WAITS)
    time.sleep(secs + RESET_MARGIN_S)


def gql(query: str) -> dict:
    """Run a GraphQL query, cached on disk by query hash (cache never expires: logs are immutable).
    When the hourly points run out it waits for the reset and retries instead of failing."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha1(query.encode()).hexdigest()[:16] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(1, MAX_WAITS + 1):
        try:
            out = _post(query)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            out = {"errors": "rate limit"}
        if not _is_rate_limit(out):
            break
        _wait_for_reset(attempt)
    else:
        raise RuntimeError("WarcraftLogs: limite di punti ancora esaurito dopo un giorno di attesa")
    if "errors" in out:
        raise RuntimeError(out["errors"])
    path.write_text(json.dumps(out))
    return out


def report(code: str, body: str) -> dict:
    """Query inside reportData.report(code) and return that sub-object."""
    return gql('{reportData{report(code:"%s"){%s}}}' % (code, body))["data"]["reportData"]["report"]


def fight_tables(code: str, fight_id: int) -> tuple[dict, dict, dict, dict]:
    """(Summary, DamageTaken, Rankings by dps, Rankings by hps) for one fight, shaped like tests/fixtures."""
    table = lambda kind: report(code, f"table(dataType:{kind},fightIDs:[{fight_id}])")["table"]
    ranks = lambda metric: report(code, f"rankings(fightIDs:[{fight_id}],playerMetric:{metric})")["rankings"]
    return table("Summary"), table("DamageTaken"), ranks("dps"), ranks("hps")
