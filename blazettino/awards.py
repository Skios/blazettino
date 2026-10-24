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
MIN_TANK_TTD_S = 10  # for a tank: this long, with the damage at least TANK_RATIO times the healing in that time
TANK_RATIO = 2.0
SCILLA_MAX_PARSE = 30  # only players under this parse among their item level compete for Scillata


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


def _slow_enough(p: kpi.Player) -> bool:
    d = p.slowest_death
    if not d:
        return False
    if p.role == "tank":  # tanks take big hits and heavy dots: what makes a death slow is healing that could not keep up
        return d.ttd_s >= MIN_TANK_TTD_S and d.damage >= TANK_RATIO * d.healing
    return d.ttd_s >= MIN_TTD_S


def _forgotten(players: list[kpi.Player]) -> list[Award]:
    slow = [p for p in players if _slow_enough(p)]
    if not slow:
        return []
    p = max(sorted(slow, key=lambda p: p.name), key=lambda p: p.slowest_death.ttd_s)
    d = p.slowest_death
    value = f"{d.ttd_s:.0f} secondi dall'ultima volta a vita piena alla morte, {d.hits} colpi, il più grosso il {d.biggest_pct:g}% della vita, ucciso da {d.spell}"
    if p.role == "tank":
        value += f"; in quel tempo {d.damage / 1e6:.1f}M di danni subiti contro {d.healing / 1e6:.1f}M di cure ricevute"
    return [Award("dimenticato", "Premio Il Dimenticato", p.name, value)]


def _scilla(players: list[kpi.Player]) -> list[Award]:
    """The best-geared player who plays worst for that gear: item level divided by the parse among the same item level."""
    low = [p for p in players if p.ranked and p.bracket_parse is not None and p.bracket_parse < SCILLA_MAX_PARSE]
    if not low:
        return []
    ratio = lambda p: p.ilvl / max(p.bracket_parse, 1)
    p = max(sorted(low, key=lambda p: p.name), key=ratio)
    return [Award("scillata", "Premio Scillata", p.name, f"item level {p.ilvl} ma parse {p.bracket_parse} tra chi ha il suo item level (rapporto {ratio(p):.0f})")]


def compute(players: list[kpi.Player], duration_s: int) -> list[Award]:
    if duration_s < MIN_FIGHT_S:
        return []
    alive = {p.name: _alive_s(p, duration_s) for p in players}
    # whoever died before the wipe (a death that is not part of the final mass death) has an activity that says nothing
    seen = [p for p in players if alive[p.name] >= MIN_ALIVE_SHARE * duration_s and all(d.mass for d in p.deaths)]
    active = {p.name: (min(100.0, p.active_s / alive[p.name] * 100), _pool(p)) for p in seen if p.active_s is not None}
    apm = {p.name: (p.casts / (alive[p.name] / 60), _pool(p)) for p in seen if p.casts is not None}
    return [
        *_forgotten(players),
        *_scilla(players),
        *_pair(active, alive, ACTIVE_GAP, False, ("anfetamina", "Premio Fatto di Anfetamina"), ("bradipo", "Premio Bradipo"),
               lambda v, m, who: f"{v:.0f}% di tempo attivo (mediana {who}: {m:.0f}%)"),
        *_pair(apm, alive, APM_GAP, True, ("spaccatastiere", "Premio Spaccatastiere"), ("tastiera", "Premio Tastiera Arrugginita"),
               lambda v, m, who: f"{v:.0f} azioni al minuto (mediana {who}: {m:.0f})"),
    ]
