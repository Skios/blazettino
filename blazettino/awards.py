"""Special prizes of a boss fight, each with a twin on the other side of the medal. A prize is given only to
someone who really stands out from the median; the text of the winner goes to the LLM, the numbers stay ours."""
from dataclasses import dataclass
import math
from statistics import median

from blazettino import kpi

MIN_FIGHT_S = 90  # shorter pulls say nothing about activity or speed
MIN_ALIVE_SHARE = 0.3  # a raider dead before this share of the fight is left out
MIN_CANDIDATES = 3  # fewer players with data and a prize says nothing
MIN_TTD_S = 20  # DPS and healers: a death is 'slow' from this many seconds after the last time at full health (19.1 counts as 20)
TANK_RATIO = 2.0  # tanks: damage at least this many times the healing received, and the healing mostly from heals over time
HOT_SHARE = 0.5
SCILLA_MAX_PARSE = 30  # only players under this parse among their item level compete for Scillata


@dataclass(frozen=True)
class Award:
    key: str
    title: str
    winner: str
    value: str  # "99% di tempo attivo (mediana del raid 80%)"


def _alive_s(p: kpi.Player, duration_s: int) -> float:
    return min(duration_s, p.deaths[0].time_s) if p.deaths else duration_s


def _extremes(rows: dict[str, float], alive: dict[str, float], top: tuple, bottom: tuple, fmt) -> list[Award]:
    """The highest value takes `top`, the lowest its twin `bottom`; a tie goes to who was alive longer (more fight behind the number)."""
    if len(rows) < MIN_CANDIDATES:
        return []
    mid = median(rows.values())
    hi = max(sorted(rows), key=lambda n: (round(rows[n], 6), alive[n]))
    lo = min(sorted(rows), key=lambda n: (round(rows[n], 6), -alive[n]))
    out = [Award(top[0], top[1], hi, fmt(rows[hi], mid))]
    if lo != hi:
        out.append(Award(bottom[0], bottom[1], lo, fmt(rows[lo], mid)))
    return out


def _slow_enough(p: kpi.Player) -> bool:
    d = p.slowest_death
    if not d:
        return False
    if p.role == "tank":  # tanks take big hits and heavy dots: time says nothing, what counts is healing that could not keep up
        return d.damage >= TANK_RATIO * d.healing and d.hot_share >= HOT_SHARE
    return math.ceil(d.ttd_s) >= MIN_TTD_S


def _forgotten(players: list[kpi.Player]) -> list[Award]:
    slow = [p for p in players if _slow_enough(p)]
    if not slow:
        return []
    p = max(sorted(slow, key=lambda p: p.name), key=lambda p: p.slowest_death.ttd_s)
    d = p.slowest_death
    value = f"{d.ttd_s:.0f} secondi dall'ultima volta a vita piena alla morte, {d.hits} colpi, il più grosso il {d.biggest_pct:g}% della vita, ucciso da {d.spell}"
    if p.role == "tank":
        value += (f"; in quel tempo {d.damage / 1e6:.1f}M di danni subiti contro {d.healing / 1e6:.1f}M di cure ricevute, "
                  f"per il {d.hot_share * 100:.0f}% heal nel tempo" + (f", con {d.busters} tank buster da assorbire" if d.busters else ""))
    return [Award("dimenticato", "Premio Il Dimenticato", p.name, value)]


def _scilla_parse(p: kpi.Player) -> float | None:
    """Parse among the same item level: the role's, averaged with the damage one for healers (who can also play DPS)."""
    if p.bracket_parse is None:
        return None
    return (p.hps_bracket + p.dps_bracket) / 2 if p.role == "healer" and p.dps_bracket is not None and p.hps_bracket is not None else p.bracket_parse


def _scilla_detail(p: kpi.Player) -> str:
    return f" (cure {p.hps_bracket}, danni {p.dps_bracket})" if p.role == "healer" else ""


def _scilla(players: list[kpi.Player]) -> list[Award]:
    """The best-geared player who plays worst for that gear: item level divided by the parse among the same item level."""
    low = [p for p in players if p.ranked and _scilla_parse(p) is not None and _scilla_parse(p) < SCILLA_MAX_PARSE]
    if not low:
        return []
    ratio = lambda p: p.ilvl / max(_scilla_parse(p), 1)
    p = max(sorted(low, key=lambda p: p.name), key=ratio)
    return [Award("scillata", "Premio Scillata", p.name, f"item level {p.ilvl} ma parse {_scilla_parse(p):g} tra chi ha il suo item level{_scilla_detail(p)} (rapporto {ratio(p):.0f})")]


def compute(players: list[kpi.Player], duration_s: int) -> list[Award]:
    if duration_s < MIN_FIGHT_S:
        return []
    alive = {p.name: _alive_s(p, duration_s) for p in players}
    # whoever died before the wipe (a death that is not part of the final mass death) has an activity that says nothing
    seen = [p for p in players if alive[p.name] >= MIN_ALIVE_SHARE * duration_s and all(d.mass for d in p.deaths)]
    # damage is only possible while the boss can be targeted: healers heal through those phases, so they are not "idle" in them
    active = {p.name: min(100.0, p.active_s / (p.targetable_s or alive[p.name]) * 100) for p in seen if p.active_s is not None}
    apm = {p.name: p.casts / (alive[p.name] / 60) for p in seen if p.casts is not None}
    return [
        *_forgotten(players),
        *_scilla(players),
        *_extremes(active, alive, ("anfetamina", "Premio Fatto di Anfetamina"), ("bradipo", "Premio Bradipo"),
                   lambda v, m: f"{v:.0f}% del tempo con il boss targettabile a infliggere danni (mediana del raid {m:.0f}%)"),
        *_extremes(apm, alive, ("spaccatastiere", "Premio Spaccatastiere"), ("tastiera", "Premio Tastiera Arrugginita"),
                   lambda v, m: f"{v:.0f} azioni al minuto (mediana del raid {m:.0f})"),
    ]
