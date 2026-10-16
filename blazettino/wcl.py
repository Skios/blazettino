"""WarcraftLogs v2 client: OAuth client-credentials, GraphQL, JSON cache on disk."""
import base64
import hashlib
import json
import urllib.request

from blazettino.config import ROOT, env

CACHE = ROOT / "cache"
API = "https://www.warcraftlogs.com"


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


def gql(query: str) -> dict:
    """Run a GraphQL query, cached on disk by query hash (cache never expires: logs are immutable)."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha1(query.encode()).hexdigest()[:16] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    req = urllib.request.Request(
        f"{API}/api/v2/client",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {_auth()}", "Content-Type": "application/json"},
    )
    out = json.load(urllib.request.urlopen(req))
    if "errors" in out:
        raise RuntimeError(out["errors"])
    path.write_text(json.dumps(out))
    return out


def report(code: str, body: str) -> dict:
    """Query inside reportData.report(code) and return that sub-object."""
    return gql('{reportData{report(code:"%s"){%s}}}' % (code, body))["data"]["reportData"]["report"]
