"""Per-boss data kept on the site (data/bosses/<encounterID>.json), so the published pages can read it.

One entry per log code and difficulty, written again with the same content if the log is seen twice.
Labels ("NEW RECORD", "+0:13") are derived from all the kills every time, never stored by hand.
"""
import json
import os
from pathlib import Path

from blazettino.attempts import Attempt
from blazettino.kpi import mmss

NEW_RECORD, TIED_RECORD = "NEW RECORD", "pari record"


def labels(reports: dict, diff: str) -> dict[str, str]:
    """code -> label for the kills of one difficulty, oldest first: the first kill shows only its time ('');
    a kill that beats every earlier one and is the fastest overall is NEW RECORD; the others show the gap."""
    kills = sorted((r["date"], code, r["difficulties"][diff]["kill_s"]) for code, r in reports.items()
                   if (r["difficulties"].get(diff) or {}).get("kill_s"))
    best = min((s for *_, s in kills), default=0)
    out = {}
    for i, (_, code, s) in enumerate(kills):
        if i == 0:
            out[code] = ""
        elif s == best:
            out[code] = NEW_RECORD if s < min(k for *_, k in kills[:i]) else TIED_RECORD
        else:
            out[code] = f"+{mmss(s - best)}"
    return out


def _derive(data: dict) -> dict:
    diffs = {d for r in data["reports"].values() for d in r["difficulties"]}
    per = {d: labels(data["reports"], d) for d in diffs}
    data["labels"] = {c: {d: per[d][c] for d in diffs if c in per[d]} for c in data["reports"]}
    data["records"] = {}
    for d in diffs:
        kills = [(r["difficulties"][d]["kill_s"], c) for c, r in data["reports"].items()
                 if (r["difficulties"].get(d) or {}).get("kill_s")]
        if kills:
            data["records"][d] = dict(zip(("kill_s", "code"), min(kills)))
    return data


def add_report(site_dir: Path, date: str, tries: list[Attempt]) -> None:
    """Record the boss attempts of one log (those without encounter id or log code are skipped)."""
    folder = site_dir / "data" / "bosses"
    for a in (a for a in tries if a.encounter and a.code):
        path = folder / f"{a.encounter}.json"
        try:
            data = json.loads(path.read_text()) if path.exists() else {"name": a.name.split(" (")[0], "reports": {}}
        except ValueError as e:
            raise SystemExit(f"{path} non è un JSON valido ({e}): ripristinalo da git prima di riprovare")
        report = data["reports"].setdefault(a.code, {"date": date, "difficulties": {}})
        report["difficulties"][str(a.difficulty)] = {
            "kill_s": a.seconds if a.kill else None,
            "pulls": [{"pct": p.pct, "s": p.seconds, "kill": p.kill} for p in a.pulls],
        }
        folder.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")  # replace is atomic: a crash never leaves a half-written boss file
        tmp.write_text(json.dumps(_derive(data), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, path)
