"""Pure functions: WarcraftLogs tables for one fight -> per-player KPIs -> 0-10 grade -> podium."""
from collections import defaultdict
from dataclasses import dataclass, replace
from itertools import chain

ROLE_KEYS = {"tanks": "tank", "healers": "healer", "dps": "dps"}

# Grade formula (calibrated on the hand-written example, tweak after real use).
BASE = 3.0
PARSE_WEIGHT = 7.0  # grade points for a 100 role parse
DEATH_PENALTY = 1.2  # per avoidable death
SURVIVOR_BONUS = 1.0  # zero deaths
CROSS_ROLE_BONUS = 1.0  # parse in the "other" role at or above the threshold
CROSS_ROLE_THRESHOLD = 90
MIN_GRADE, MAX_GRADE = 1.0, 10.0

UNKNOWN_ABILITY = "causa sconosciuta"  # WarcraftLogs gives no killing blow for some deaths

# A death is "mass" (not penalised) when this many raiders die within the window.
MASS_DEATHS = 5
MASS_WINDOW_S = 2


@dataclass(frozen=True)
class Death:
    time_s: int
    ability: str
    mass: bool
    boss: str = ""


@dataclass(frozen=True)
class Player:
    name: str
    spec: str
    cls: str
    role: str
    ilvl: int
    damage: int
    healing: int
    dps: float
    hps: float
    taken: int
    mitigation: float  # share of incoming damage reduced (0-1)
    dps_parse: int
    hps_parse: int
    deaths: tuple[Death, ...]
    score: float | None = None  # night grade set by merge(); None = compute from the fight
    fights: int = 1  # boss fights this raider took part in
    ranked: bool = True  # False: parses are inside-raid percentiles (no WarcraftLogs ranking on wipes)

    @property
    def icon(self) -> str:
        """WarcraftLogs icon id, e.g. Priest-Holy."""
        return f"{self.cls}-{self.spec}"

    @property
    def role_parse(self) -> int:
        return self.hps_parse if self.role == "healer" else self.dps_parse

    @property
    def other_parse(self) -> int:
        return self.dps_parse if self.role == "healer" else self.hps_parse


def _parses(rankings: dict) -> dict[str, int]:
    chars = rankings["data"][0]["roles"].values()
    return {c["name"]: c["rankPercent"] for r in chars for c in r["characters"]}


def _deaths(events: list[dict]) -> dict[str, tuple[Death, ...]]:
    times = sorted(e["deathTime"] for e in events)
    out: dict[str, list[Death]] = {}
    for e in sorted(events, key=lambda e: e["deathTime"]):
        near = sum(abs(t - e["deathTime"]) <= MASS_WINDOW_S * 1000 for t in times)
        d = Death(e["deathTime"] // 1000, e.get("ability", {}).get("name", UNKNOWN_ABILITY), near >= MASS_DEATHS)
        out.setdefault(e["name"], []).append(d)
    return {n: tuple(d) for n, d in out.items()}


def _percentiles(values: dict[str, tuple[str, float]]) -> dict[str, int]:
    """name -> 0..100 rank percentile among the raiders of the same role (best = 100)."""
    out = {}
    for role in {role for role, _ in values.values()}:
        group = sorted((v, n) for n, (r, v) in values.items() if r == role)
        for i, (_, name) in enumerate(group):
            out[name] = round(100 * i / (len(group) - 1)) if len(group) > 1 else 50
    return out


def load_fight(summary: dict, taken: dict, rank_dps: dict, rank_hps: dict) -> list[Player]:
    """Build one Player per raider from the Summary, DamageTaken and the two Rankings (dps/hps metric) tables.
    Wipes have empty rankings: parses then become percentiles inside the raid, per role, and ranked=False."""
    s = summary["data"]
    secs = s["totalTime"] / 1000
    damage = defaultdict(int, {e["name"]: e["total"] for e in s["damageDone"]})  # absent = did nothing
    healing = defaultdict(int, {e["name"]: e["total"] for e in s["healingDone"]})
    tk = {e["name"]: e for e in taken["data"]["entries"]}
    roster = [(role, d) for key, role in ROLE_KEYS.items() for d in s["playerDetails"][key]]
    ranked = bool(rank_dps["data"]) and bool(rank_hps["data"])
    if ranked:
        dps_p, hps_p = _parses(rank_dps), _parses(rank_hps)
    else:
        dps_p = _percentiles({d["name"]: (role, damage[d["name"]]) for role, d in roster})
        hps_p = _percentiles({d["name"]: (role, healing[d["name"]]) for role, d in roster})
    deaths = _deaths(s["deathEvents"])
    players = []
    for role, d in roster:
        n = d["name"]
        t = tk[n]
        players.append(Player(
            name=n, spec=d["specs"][0], cls=d["type"], role=role, ilvl=d["maxItemLevel"],
            damage=damage[n], healing=healing[n], dps=damage[n] / secs, hps=healing[n] / secs,
            taken=t["total"], mitigation=1 - t.get("totalReduced", t["total"]) / t["total"] if t["total"] else 0.0,
            dps_parse=dps_p[n], hps_parse=hps_p[n], deaths=deaths.get(n, ()), ranked=ranked,
        ))
    return players


def grade(p: Player) -> float:
    if p.score is not None:
        return p.score
    avoidable = sum(not d.mass for d in p.deaths)
    g = BASE + PARSE_WEIGHT * p.role_parse / 100 - DEATH_PENALTY * avoidable
    g += SURVIVOR_BONUS * (not p.deaths)
    g += CROSS_ROLE_BONUS * (p.ranked and p.other_parse >= CROSS_ROLE_THRESHOLD)
    return min(MAX_GRADE, max(MIN_GRADE, round(g * 2) / 2))


def ranking(players: list[Player]) -> list[Player]:
    """Best first; ties broken by role parse."""
    return sorted(players, key=lambda p: (grade(p), p.role_parse), reverse=True)


def eligible(players: list[Player], total_fights: int, max_missed: int) -> list[Player]:
    """Raiders who missed at most max_missed of the night's boss fights (podium candidates)."""
    return [p for p in players if p.fights >= total_fights - max_missed]


def podium(players: list[Player]) -> tuple[Player, Player]:
    """(MVP, LVP)."""
    ranked = ranking(players)
    return ranked[0], ranked[-1]


def mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def merge(fights: list[list[Player]]) -> list[Player]:
    """Collapse the same raider across fights: sum totals, average rates/parses, keep all deaths,
    night grade = mean of the per-fight grades (so more pulls do not multiply death penalties)."""
    by_name: dict[str, list[Player]] = {}
    for f in fights:
        for p in f:
            by_name.setdefault(p.name, []).append(p)

    def one(ps: list[Player]) -> Player:
        n = len(ps)
        mean = lambda xs: sum(xs) / n
        return replace(
            ps[-1],
            ilvl=max(p.ilvl for p in ps),
            damage=sum(p.damage for p in ps),
            healing=sum(p.healing for p in ps),
            taken=sum(p.taken for p in ps),
            dps=mean([p.dps for p in ps]),
            hps=mean([p.hps for p in ps]),
            mitigation=mean([p.mitigation for p in ps]),
            dps_parse=round(mean([p.dps_parse for p in ps])),
            hps_parse=round(mean([p.hps_parse for p in ps])),
            deaths=tuple(chain.from_iterable(p.deaths for p in ps)),
            score=round(mean([grade(p) for p in ps]) * 2) / 2,
            fights=n,
            ranked=all(p.ranked for p in ps),
        )

    return [one(ps) for ps in by_name.values()]
