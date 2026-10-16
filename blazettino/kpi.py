"""Pure functions: WarcraftLogs tables for one fight -> per-player KPIs -> 0-10 grade -> podium."""
from dataclasses import dataclass

ROLE_KEYS = {"tanks": "tank", "healers": "healer", "dps": "dps"}

# Grade formula (calibrated on the hand-written example, tweak after real use).
BASE = 3.0
PARSE_WEIGHT = 7.0  # grade points for a 100 role parse
DEATH_PENALTY = 1.2  # per avoidable death
SURVIVOR_BONUS = 1.0  # zero deaths
CROSS_ROLE_BONUS = 1.0  # parse in the "other" role at or above the threshold
CROSS_ROLE_THRESHOLD = 90
MIN_GRADE, MAX_GRADE = 1.0, 10.0

# A death is "mass" (not penalised) when this many raiders die within the window.
MASS_DEATHS = 5
MASS_WINDOW_S = 2


@dataclass(frozen=True)
class Death:
    time_s: int
    ability: str
    mass: bool


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
        d = Death(e["deathTime"] // 1000, e["ability"]["name"], near >= MASS_DEATHS)
        out.setdefault(e["name"], []).append(d)
    return {n: tuple(d) for n, d in out.items()}


def load_fight(summary: dict, taken: dict, rank_dps: dict, rank_hps: dict) -> list[Player]:
    """Build one Player per raider from the Summary, DamageTaken and the two Rankings (dps/hps metric) tables."""
    s = summary["data"]
    secs = s["totalTime"] / 1000
    damage = {e["name"]: e["total"] for e in s["damageDone"]}
    healing = {e["name"]: e["total"] for e in s["healingDone"]}
    tk = {e["name"]: e for e in taken["data"]["entries"]}
    dps_p, hps_p = _parses(rank_dps), _parses(rank_hps)
    deaths = _deaths(s["deathEvents"])
    players = []
    for key, role in ROLE_KEYS.items():
        for d in s["playerDetails"][key]:
            n = d["name"]
            t = tk[n]
            players.append(Player(
                name=n, spec=d["specs"][0], cls=d["type"], role=role, ilvl=d["maxItemLevel"],
                damage=damage[n], healing=healing[n], dps=damage[n] / secs, hps=healing[n] / secs,
                taken=t["total"], mitigation=1 - t["totalReduced"] / t["total"],
                dps_parse=dps_p[n], hps_parse=hps_p[n], deaths=deaths.get(n, ()),
            ))
    return players


def grade(p: Player) -> float:
    avoidable = sum(not d.mass for d in p.deaths)
    g = BASE + PARSE_WEIGHT * p.role_parse / 100 - DEATH_PENALTY * avoidable
    g += SURVIVOR_BONUS * (not p.deaths)
    g += CROSS_ROLE_BONUS * (p.other_parse >= CROSS_ROLE_THRESHOLD)
    return min(MAX_GRADE, max(MIN_GRADE, round(g * 2) / 2))


def podium(players: list[Player]) -> tuple[Player, Player]:
    """(MVP, LVP): best and worst grade; ties broken by role parse."""
    ranked = sorted(players, key=lambda p: (grade(p), p.role_parse))
    return ranked[-1], ranked[0]
