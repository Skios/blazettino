"""Profile of one fight from its raw WarcraftLogs events: what each player took from each ability and when,
deaths, interrupts and dispels. Pure functions: events in, plain dict out (JSON-friendly)."""
import bisect
import dataclasses
import json
from collections import defaultdict
from statistics import mean

from blazettino import wcl
from blazettino.abilities import METRIC_TEXT

DEAD_CUTOFF = 5  # hits taken when more raiders than this are already dead are ignored (Wipefest does the same)
MAX_NOTES = 3  # facts per player given to the LLM
OUTLIER_X = 3  # a player is notable when he took this many times the average of the others
MIN_REPEAT = 3  # interruptions or dispels needed to be worth a mention


def _name(table: dict, key: int) -> str:
    return table.get(key, str(key))


def build(start: int, damage: list[dict], deaths: list[dict], interrupts: list[dict], dispels: list[dict],
          names: dict[int, str], spells: dict[int, str]) -> dict:
    """Times are seconds from the pull. Damage uses `amount` (after mitigation and absorbs, what Wipefest counts);
    each hit also stores how many raiders were already dead, so damage taken by the doomed can be ignored later."""
    secs = lambda e: (e["timestamp"] - start) // 1000
    death_times = sorted(e["timestamp"] for e in deaths)
    out = {"damage": {}, "deaths": [], "interrupts": defaultdict(list), "dispels": defaultdict(list)}
    for e in damage:
        ability = out["damage"].setdefault(_name(spells, e["abilityGameID"]), {"total": 0, "players": {}})
        player = ability["players"].setdefault(_name(names, e["targetID"]), {"dmg": 0, "hits": 0, "list": []})
        amount = e.get("amount", 0)
        ability["total"] += amount
        player["dmg"] += amount
        player["hits"] += 1
        player["list"].append([secs(e), amount, bisect.bisect_left(death_times, e["timestamp"])])
    out["deaths"] = [{"player": _name(names, e["targetID"]), "s": secs(e), "spell": _name(spells, e.get("killingAbilityGameID", 0))}
                     for e in sorted(deaths, key=lambda e: e["timestamp"])]
    for key, events in (("interrupts", interrupts), ("dispels", dispels)):
        for e in events:
            out[key][_name(names, e["sourceID"])].append({"s": secs(e), "spell": _name(spells, e.get("extraAbilityGameID", 0))})
        out[key] = dict(out[key])
    return out


def avoidable(prof: dict, spells: dict, cutoff: int = DEAD_CUTOFF) -> dict[str, dict[str, dict]]:
    """{ability: {player: {dmg, hits}}} for the abilities whose metric (abilities table) is "avoid",
    without the hits taken when more than `cutoff` raiders were already dead."""
    out = {}
    for ability, a in prof["damage"].items():
        if spells.get(ability.lower(), {}).get("metric") != "avoid":
            continue
        per = {}
        for player, v in a["players"].items():
            hits = [h for h in v["list"] if h[2] <= cutoff]
            if hits:
                per[player] = {"dmg": sum(h[1] for h in hits), "hits": len(hits)}
        if per:
            out[ability] = per
    return out


def _repeats(prof: dict, key: str, text: str) -> dict[str, list[tuple[int, str]]]:
    out = {}
    for player, items in prof[key].items():
        if len(items) >= MIN_REPEAT:
            spell = max({i["spell"] for i in items}, key=lambda s: sum(i["spell"] == s for i in items))
            out[player] = [(len(items), f"{len(items)} {text} (soprattutto {spell})")]
    return out


def notes(prof: dict, spells: dict, cutoff: int = DEAD_CUTOFF) -> dict[str, list[str]]:
    """The few facts worth telling about each player, strongest first (damage taken from avoidable abilities
    far above the others, many interruptions or dispels); the ability's hand-written note is added when it shows up."""
    scored: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for ability, per in avoidable(prof, spells, cutoff).items():
        for player, v in per.items():
            others = [o["dmg"] for p, o in per.items() if p != player]
            base = mean(others) if others else 0
            if spells[ability.lower()].get("kind") != "oneshot" and (v["hits"] < 2 or (others and v["dmg"] < OUTLIER_X * base)):
                continue
            ratio = f", {v['dmg'] / base:.0f}x la media degli altri" if base else ""
            a = spells[ability.lower()]
            extra = f" ({a['note']})" if a["note"] else ""
            scored[player].append((v["dmg"], f"{a['it'] or ability} [{METRIC_TEXT['avoid']}]: {v['hits']} colpi, {v['dmg'] / 1e6:.1f}M{ratio}{extra}"))
    for key, text in (("interrupts", "interruzioni"), ("dispels", "dispel")):
        for player, [(n, line)] in _repeats(prof, key, text).items():
            scored[player].append((n * 1e3, line))
    return {p: [t for _, t in sorted(v, reverse=True)[:MAX_NOTES]] for p, v in scored.items()}


def fight_profile(code: str, fight_id: int) -> dict:
    """Download (cached) the events of one fight and profile them; pets and totems count for their owner."""
    f = wcl.report(code, "fights(fightIDs:[%d]){startTime endTime}" % fight_id)["fights"][0]
    md = wcl.report(code, "masterData{actors{id name type subType petOwner}abilities{gameID name type}}")["masterData"]
    actors = {a["id"]: a for a in md["actors"]}
    names = {i: actors.get(a.get("petOwner"), a)["name"] for i, a in actors.items()}
    spells = {a["gameID"]: a["name"] for a in md["abilities"]}
    get = lambda kind: wcl.events(code, fight_id, f["startTime"], f["endTime"], kind)
    return build(f["startTime"], get("DamageTaken"), get("Deaths"), get("Interrupts"), get("Dispels"), names, spells)


def annotate(players: list, code: str, fight_id: int, spells: dict) -> list:
    """Players with the notable events of the fight attached (read-only for the grade)."""
    found = notes(fight_profile(code, fight_id), spells)
    return [dataclasses.replace(p, notes=tuple(found.get(p.name, ()))) for p in players]
