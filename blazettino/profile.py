"""Profile of one fight from its raw WarcraftLogs events: what each player took from each ability and when,
deaths, interrupts and dispels. Pure functions: events in, plain dict out (JSON-friendly)."""
import bisect
from collections import defaultdict


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
            out[key][_name(names, e["sourceID"])].append({"s": secs(e), "spell": _name(spells, e["extraAbilityGameID"])})
        out[key] = dict(out[key])
    return out
