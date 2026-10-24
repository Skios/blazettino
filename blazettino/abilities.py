"""One file per boss (data/abilities/<encounterID>.json) listing every ability of the boss and its adds,
by phase, learned from WarcraftLogs run after run. The machine fields (name, sources, counts) are refreshed
by each log; the hand fields (it, metric, note, anything you add) are never touched. Same fight twice = no change."""
import bisect
import json
import os
from collections import defaultdict
from pathlib import Path

from blazettino import wcl
from blazettino.config import ROOT

DATA = ROOT / "data" / "abilities"
HAND = {"it": "", "metric": "", "note": ""}  # filled in by people: Italian name, how to measure it, text for the LLM


def _enemy(actors: dict, source_id: int) -> str | None:
    a = actors.get(source_id)
    return a["name"] if a and a.get("type") == "NPC" and not a.get("petOwner") else None


def collect(transitions: list[dict], casts: list[dict], damage: list[dict], actors: dict, spells: dict) -> dict[int, dict]:
    """{spell id: {"sources": [...], "phases": {phase id: {"casts", "hits"}}}} for what enemy NPCs cast or hit raiders with."""
    starts = [t["startTime"] for t in transitions]
    ids = [t["id"] for t in transitions]
    phase = lambda ts: ids[max(bisect.bisect_right(starts, ts) - 1, 0)]
    found: dict[int, dict] = {}
    for events, kind in ((casts, "casts"), (damage, "hits")):
        for e in events:
            who = _enemy(actors, e["sourceID"])
            if who is None or (kind == "casts" and e["type"] != "cast"):
                continue
            a = found.setdefault(e["abilityGameID"], {"sources": set(), "phases": defaultdict(lambda: {"casts": 0, "hits": 0})})
            a["sources"].add(who)
            a["phases"][phase(e["timestamp"])][kind] += 1
    return {s: {"sources": sorted(a["sources"]), "phases": dict(a["phases"])} for s, a in found.items()}


def merge(data: dict, encounter: int, name: str, phase_names: dict[int, str], fight_key: str, found: dict[int, dict], spells: dict) -> dict:
    """A new file content with this fight added; a fight already in "logs" leaves everything as it was."""
    if fight_key in data.get("logs", ()):
        return data
    out = {**data, "name": name, "encounter": encounter, "phases": {str(k): v for k, v in phase_names.items()},
           "logs": [*data.get("logs", ()), fight_key]}
    table = {k: dict(v) for k, v in data.get("abilities", {}).items()}
    for spell, f in found.items():
        a = table.setdefault(str(spell), {"en": "", **HAND, "sources": [], "phases": {}})
        a["en"] = spells.get(spell, a["en"] or str(spell))
        a["sources"] = sorted({*a["sources"], *f["sources"]})
        phases = {k: dict(v) for k, v in a["phases"].items()}
        for pid, n in f["phases"].items():
            cur = phases.setdefault(str(pid), {"casts": 0, "hits": 0, "fights": 0})
            phases[str(pid)] = {"casts": cur["casts"] + n["casts"], "hits": cur["hits"] + n["hits"], "fights": cur["fights"] + 1}
        a["phases"] = phases
    out["abilities"] = dict(sorted(table.items(), key=lambda kv: int(kv[0])))
    return out


def load(folder: Path, encounter: int) -> dict:
    path = folder / f"{encounter}.json"
    try:
        return json.loads(path.read_text()) if path.exists() else {}
    except ValueError as e:
        raise SystemExit(f"{path} non è un JSON valido ({e}): sistemalo a mano o ripristinalo da git prima di riprovare")


def save(folder: Path, encounter: int, data: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{encounter}.json"
    tmp = path.with_suffix(".tmp")  # replace is atomic: a crash never leaves a half-written file
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def learn(code: str, fight_id: int, folder: Path = DATA) -> str:
    """Download (cached) one boss fight and add its abilities to that boss's file; returns the boss name."""
    f = wcl.report(code, "fights(fightIDs:[%d]){encounterID name startTime endTime phaseTransitions{id startTime}}" % fight_id)["fights"][0]
    info = wcl.report(code, "phases{encounterID phases{id name}} masterData{actors{id name type petOwner}abilities{gameID name}}")
    phase_names = {p["id"]: p["name"] for e in info["phases"] if e["encounterID"] == f["encounterID"] for p in e["phases"]}
    actors = {a["id"]: a for a in info["masterData"]["actors"]}
    spells = {a["gameID"]: a["name"] for a in info["masterData"]["abilities"]}
    get = lambda kind, host: wcl.events(code, fight_id, f["startTime"], f["endTime"], kind, host)
    found = collect(f["phaseTransitions"] or [{"id": 1, "startTime": f["startTime"]}], get("Casts", "Enemies"), get("DamageTaken", "Friendlies"), actors, spells)
    data = merge(load(folder, f["encounterID"]), f["encounterID"], f["name"], phase_names, f"{code}#{fight_id}", found, spells)
    save(folder, f["encounterID"], data)
    return f["name"]
