"""Special prizes of a boss fight, each with a twin on the other side of the medal. A prize is given only to
someone who really stands out from the median; the text of the winner goes to the LLM, the numbers stay ours."""
from dataclasses import dataclass
from statistics import median

from blazettino import kpi

MIN_FIGHT_S = 90  # shorter pulls say nothing about activity or speed
MIN_ALIVE_SHARE = 0.3  # a raider dead before this share of the fight is left out
ACTIVE_GAP = 5.0  # percentage points from the median to win the activity prizes
APM_GAP = 0.25  # share of the median to win the actions-per-minute prizes
MIN_TTD_S = 20  # a death is 'slow' from this many seconds after the last time at full health


@dataclass(frozen=True)
class Award:
    key: str
    title: str
    winner: str
    value: str  # "99% di tempo attivo (mediana del raid 80%)"


def _alive_s(p: kpi.Player, duration_s: int) -> float:
    return min(duration_s, p.deaths[0].time_s) if p.deaths else duration_s


def _pool(p: kpi.Player) -> str:
    return "healer" if p.role == "healer" else "altri"  # healers heal almost all the time: they are compared with each other


POOL_NAME = {"healer": "degli healer", "altri": "di DPS e tank"}


def _pair(rows: dict[str, tuple[float, str]], alive: dict[str, float], gap: float, relative: bool, top: tuple, bottom: tuple, fmt) -> list[Award]:
    """(key, title) of the prize for who is highest above the median of their own pool and of its twin for who is lowest below it;
    a tie goes to who was alive longer (more fight behind the number)."""
    medians = {pool: median(v for v, p in rows.values() if p == pool) for pool in {p for _, p in rows.values()}}
    sizes = {pool: sum(p == pool for _, p in rows.values()) for pool in medians}
    dev = {n: (v - medians[p]) / medians[p] if relative else v - medians[p] for n, (v, p) in rows.items() if sizes[p] >= 3}
    out = []
    for (key, title), pick, sign in ((top, max, 1), (bottom, min, -1)):
        if not dev:
            break
        name = pick(sorted(dev), key=lambda n: (round(dev[n], 6), alive[n]))
        if sign * dev[name] >= gap:
            value, pool = rows[name]
            out.append(Award(key, title, name, fmt(value, medians[pool], POOL_NAME[pool])))
    return out


def _forgotten(players: list[kpi.Player]) -> list[Award]:
    slow = [p for p in players if p.slowest_death and p.slowest_death.ttd_s >= MIN_TTD_S]
    if not slow:
        return []
    p = max(sorted(slow, key=lambda p: p.name), key=lambda p: p.slowest_death.ttd_s)
    d = p.slowest_death
    return [Award("dimenticato", "Premio Il Dimenticato", p.name,
                  f"{d.ttd_s:.0f} secondi dall'ultima volta a vita piena alla morte, {d.hits} colpi, il più grosso il {d.biggest_pct:g}% della vita, ucciso da {d.spell}")]


def compute(players: list[kpi.Player], duration_s: int) -> list[Award]:
    if duration_s < MIN_FIGHT_S:
        return []
    alive = {p.name: _alive_s(p, duration_s) for p in players}
    seen = [p for p in players if alive[p.name] >= MIN_ALIVE_SHARE * duration_s]
    active = {p.name: (min(100.0, p.active_s / alive[p.name] * 100), _pool(p)) for p in seen if p.active_s is not None}
    apm = {p.name: (p.casts / (alive[p.name] / 60), _pool(p)) for p in seen if p.casts is not None}
    return [
        *_forgotten(players),
        *_pair(active, alive, ACTIVE_GAP, False, ("anfetamina", "Premio Fatto di Anfetamina"), ("bradipo", "Premio Bradipo"),
               lambda v, m, who: f"{v:.0f}% di tempo attivo (mediana {who}: {m:.0f}%)"),
        *_pair(apm, alive, APM_GAP, True, ("spaccatastiere", "Premio Spaccatastiere"), ("tastiera", "Premio Tastiera Arrugginita"),
               lambda v, m, who: f"{v:.0f} azioni al minuto (mediana {who}: {m:.0f})"),
    ]
