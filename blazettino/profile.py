"""Profile of one fight from its raw WarcraftLogs events: what each player took from each ability and when,
deaths, interrupts and dispels. Pure functions: events in, plain dict out (JSON-friendly)."""
import bisect
import dataclasses
import json
from collections import Counter, defaultdict
from statistics import mean

from blazettino import kpi, wcl
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


TARGET_GAP_S = 5  # the boss takes no damage for longer than this = it could not be targeted


def targetable_windows(times_s: list[float], end_s: float, gap: float = TARGET_GAP_S) -> list[tuple[float, float]]:
    """(start, end) seconds in which the boss was being hit: hits closer than `gap` belong to the same window."""
    out = []
    for t in sorted(times_s):
        if out and t - out[-1][1] <= gap:
            out[-1] = (out[-1][0], t)
        else:
            out.append((0 if not out and t <= gap else t, t))
    if out and end_s - out[-1][1] <= gap:
        out[-1] = (out[-1][0], end_s)
    return out


def seconds_in(windows: list[tuple[float, float]], until: float) -> float:
    return sum(max(0.0, min(b, until) - a) for a, b in windows)


def boss_windows(code: str, fight_id: int) -> tuple[list[tuple[float, float]], float] | None:
    """When the boss of a fight could be hit (guessed from the damage it takes: WarcraftLogs has no targetable events) and the fight length."""
    f = wcl.report(code, "fights(fightIDs:[%d]){name startTime endTime}" % fight_id)["fights"][0]
    actors = wcl.report(code, "masterData{actors{id name}}")["masterData"]["actors"]
    ids = {a["id"] for a in actors if a["name"] == f["name"]}
    secs = [(e["timestamp"] - f["startTime"]) / 1000 for e in wcl.events(code, fight_id, f["startTime"], f["endTime"], "DamageTaken", "Enemies")
            if e["targetID"] in ids]
    length = (f["endTime"] - f["startTime"]) / 1000
    return (targetable_windows(secs, length), length) if secs else None


def performance(code: str, fight_id: int) -> dict[str, dict]:
    """Per player of one fight: seconds spent damaging and healing (WarcraftLogs active time) and spells cast."""
    f = wcl.report(code, "fights(fightIDs:[%d]){startTime endTime}" % fight_id)["fights"][0]
    actors = wcl.report(code, "masterData{actors{id name type}}")["masterData"]["actors"]
    names = {a["id"]: a["name"] for a in actors if a["type"] == "Player"}
    active = {kind: {e["name"]: e["activeTime"] / 1000 for e in
                     wcl.report(code, "table(dataType:%s,fightIDs:[%d])" % (kind, fight_id))["table"]["data"]["entries"]}
              for kind in ("DamageDone", "Healing")}
    casts = Counter(names[e["sourceID"]] for e in wcl.events(code, fight_id, f["startTime"], f["endTime"], "Casts")
                    if e["type"] == "cast" and e["sourceID"] in names)
    return {n: {"damage_s": active["DamageDone"].get(n, 0.0), "healing_s": active["Healing"].get(n, 0.0), "casts": casts[n]}
            for n in names.values()}


def with_performance(players: list, code: str, fight_id: int) -> list:
    """Players with active seconds (time spent dealing damage, for everyone: a healer healing is always busy), and the time the boss could be targeted and casts attached."""
    perf, boss = performance(code, fight_id), boss_windows(code, fight_id)
    out = []
    for p in players:
        d = perf.get(p.name)
        if not d:
            out.append(p)
            continue
        tgt = None
        if boss:
            windows, length = boss
            tgt = seconds_in(windows, min(length, p.deaths[0].time_s) if p.deaths else length)
        out.append(dataclasses.replace(p, active_s=d["damage_s"], casts=d["casts"], targetable_s=tgt))
    return out


FULL_HEALTH = 0.99  # a hit that finds the player at or above this share of max health marks "full health"


def slow_deaths(damage: list[dict], deaths: list[dict], names: dict[int, str], spells: dict[int, str],
                heals: list[dict] = (), busters: frozenset = frozenset()) -> dict[str, kpi.SlowDeath]:
    """Per player, the slowest death: seconds from the last hit that found them at full health to the death, the hits in
    between and the biggest one, plus the damage taken and the healing received in that time (heal events given in `heals`).
    Needs damage events with resources. Deaths in a crowd or after too many deaths are left out."""
    stamps = sorted(d["timestamp"] for d in deaths)
    hits: dict[int, list[tuple[int, float, float, int]]] = defaultdict(list)  # target -> (time, health before the hit, hit size as share, amount)
    for e in damage:
        if e.get("maxHitPoints") and "hitPoints" in e and e["targetID"] in names:
            hits[e["targetID"]].append((e["timestamp"], (e["hitPoints"] + e["amount"]) / e["maxHitPoints"],
                                        (e["amount"] + e.get("absorbed", 0)) / e["maxHitPoints"], e["amount"]))
    out: dict[str, kpi.SlowDeath] = {}
    previous: dict[int, int] = {}
    for i, d in enumerate(sorted(deaths, key=lambda d: d["timestamp"])):
        t, who = d["timestamp"], d["targetID"]
        since = previous.get(who, 0)
        previous[who] = t
        crowd = sum(abs(s - t) <= kpi.MASS_WINDOW_S * 1000 for s in stamps)
        if who not in names or i > DEAD_CUTOFF or crowd >= kpi.MASS_DEATHS:
            continue
        mine = [h for h in sorted(hits[who]) if since < h[0] <= t]
        full = [j for j, h in enumerate(mine) if h[1] >= FULL_HEALTH]
        if not full:
            continue
        run = mine[full[-1]:]
        mine_heals = [h for h in heals if h.get("targetID") == who and run[0][0] <= h["timestamp"] <= t]
        healed = sum(h.get("amount", 0) for h in mine_heals)
        ticks = sum(h.get("amount", 0) for h in mine_heals if h.get("tick"))
        hit_busters = sum(_name(spells, e["abilityGameID"]).lower() in busters for e in damage
                          if e["targetID"] == who and run[0][0] <= e["timestamp"] <= t)
        slow = kpi.SlowDeath((t - run[0][0]) / 1000, len(run), round(max(h[2] for h in run) * 100, 1), _name(spells, d.get("killingAbilityGameID", 0)),
                             sum(h[3] for h in run), healed, ticks / healed if healed else 0.0, hit_busters)
        if who in names and (names[who] not in out or out[names[who]].ttd_s < slow.ttd_s):
            out[names[who]] = slow
    return out


def with_slow_deaths(players: list, code: str, fight_id: int, table: dict = {}) -> list:
    """Players with their slowest death attached (for the prize 'Il Dimenticato')."""
    f = wcl.report(code, "fights(fightIDs:[%d]){startTime endTime}" % fight_id)["fights"][0]
    md = wcl.report(code, "masterData{actors{id name type}abilities{gameID name}}")["masterData"]
    names = {a["id"]: a["name"] for a in md["actors"] if a["type"] == "Player"}
    spells = {a["gameID"]: a["name"] for a in md["abilities"]}
    get = lambda kind, resources=False: wcl.events(code, fight_id, f["startTime"], f["endTime"], kind, resources=resources)
    busters = frozenset(k for k, v in table.items() if isinstance(k, str) and v.get("metric") == "tankbuster")
    found = slow_deaths(get("DamageTaken", True), get("Deaths"), names, spells, get("Healing"), busters)
    return [dataclasses.replace(p, slowest_death=found.get(p.name)) for p in players]
