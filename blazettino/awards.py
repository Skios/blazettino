"""Special prizes of a boss fight, each with a twin on the other side of the medal. A prize is given only to
someone who really stands out from the median; the text of the winner goes to the LLM, the numbers stay ours."""
from dataclasses import dataclass
from statistics import median

from blazettino import kpi

MIN_FIGHT_S = 90  # shorter pulls say nothing about activity or speed
MIN_ALIVE_SHARE = 0.3  # a raider dead before this share of the fight is left out
ACTIVE_GAP = 5.0  # percentage points from the median to win the activity prizes
APM_GAP = 0.25  # share of the median to win the actions-per-minute prizes


@dataclass(frozen=True)
class Award:
    key: str
    title: str
    winner: str
    value: str  # "99% di tempo attivo (mediana del raid 80%)"


def _alive_s(p: kpi.Player, duration_s: int) -> float:
    return min(duration_s, p.deaths[0].time_s) if p.deaths else duration_s


def _pair(rows: dict[str, float], gap: float, relative: bool, top: tuple, bottom: tuple, fmt) -> list[Award]:
    """(key, title) of the prize for the highest value and of its twin for the lowest, if they stand out."""
    if len(rows) < 3:
        return []
    mid = median(rows.values())
    out = []
    for (key, title), pick, sign in ((top, max, 1), (bottom, min, -1)):
        name = pick(sorted(rows), key=lambda n: rows[n])
        distance = sign * (rows[name] - mid)
        if distance >= (gap * mid if relative else gap):
            out.append(Award(key, title, name, fmt(rows[name], mid)))
    return out


def compute(players: list[kpi.Player], duration_s: int) -> list[Award]:
    if duration_s < MIN_FIGHT_S:
        return []
    alive = {p.name: _alive_s(p, duration_s) for p in players}
    seen = [p for p in players if alive[p.name] >= MIN_ALIVE_SHARE * duration_s]
    active = {p.name: min(100.0, p.active_s / alive[p.name] * 100) for p in seen if p.active_s is not None}
    apm = {p.name: p.casts / (alive[p.name] / 60) for p in seen if p.casts is not None}
    return [
        *_pair(active, ACTIVE_GAP, False, ("anfetamina", "Premio Fatto di Anfetamina"), ("bradipo", "Premio Bradipo"),
               lambda v, m: f"{v:.0f}% di tempo attivo (mediana del raid {m:.0f}%)"),
        *_pair(apm, APM_GAP, True, ("spaccatastiere", "Premio Spaccatastiere"), ("tastiera", "Premio Tastiera Arrugginita"),
               lambda v, m: f"{v:.0f} azioni al minuto (mediana del raid {m:.0f})"),
    ]
