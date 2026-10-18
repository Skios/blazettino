"""The night as the reports see it: one BossReport per boss (best try) plus the merged night."""
import dataclasses
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from blazettino import comment, kpi
from blazettino.attempts import Attempt
from blazettino.comment import Comment

LLM_WORKERS = 2  # free tiers rate-limit: two calls at a time is enough for ~4 per night


@dataclass(frozen=True)
class BossReport:
    attempt: Attempt
    players: list[kpi.Player]
    comments: dict[str, Comment]


@dataclass(frozen=True)
class Night:
    title: str
    date: str
    bosses: list[BossReport]
    players: list[kpi.Player]  # merged across bosses
    comments: dict[str, Comment]  # night-wide, from the aggregated data
    max_missed: int
    kind: str = "Serata"  # "Settimana" for the weekly aggregate


def _tag_boss(players: list[kpi.Player], boss: str) -> list[kpi.Player]:
    return [
        dataclasses.replace(p, deaths=tuple(dataclasses.replace(d, boss=boss) for d in p.deaths))
        for p in players
    ]


def assemble(
    title: str,
    date: str,
    tries: list[tuple[Attempt, list[kpi.Player]]],
    cfg: dict,
    comments_fn: Callable[..., dict[str, Comment]] = comment.comments,
) -> Night:
    """Drop excluded raiders, merge the night and ask the LLM once per boss plus once for the whole night."""
    exclude = set(cfg.get("exclude", ()))
    per_boss = [(a, [p for p in ps if p.name not in exclude]) for a, ps in tries]
    merged = kpi.merge([_tag_boss(ps, a.name) for a, ps in per_boss])
    jobs = [(ps, comment.attempt_context(a)) for a, ps in per_boss]
    jobs.append((merged, comment.night_context([a for a, _ in per_boss])))
    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as pool:
        notes = list(pool.map(lambda job: comments_fn(job[0], cfg, context=job[1]), jobs))
    bosses = [BossReport(a, ps, n) for (a, ps), n in zip(per_boss, notes)]
    return Night(title, date, bosses, merged, notes[-1], cfg.get("max_missed_fights", 1))


def _day(date: str) -> str:
    return f"{date[8:]}/{date[5:7]}"


def assemble_week(nights: list[Night], cfg: dict, comments_fn: Callable[..., dict[str, Comment]] = comment.comments) -> Night:
    """The week as one big night: every boss try of every night (named with its day), merged grades,
    one extra LLM call. Boss comments are reused from the nights, not regenerated."""
    nights = sorted(nights, key=lambda n: n.date)
    bosses = [
        dataclasses.replace(b, attempt=dataclasses.replace(b.attempt, name=f"{b.attempt.name} ({_day(n.date)})"))
        for n in nights for b in n.bosses
    ]
    merged = kpi.merge([_tag_boss(b.players, b.attempt.name) for b in bosses])
    notes = comments_fn(merged, cfg, context=comment.week_context([b.attempt for b in bosses], len(nights)))
    title = f"Settimana {_day(nights[0].date)}–{_day(nights[-1].date)} · {nights[0].title}"
    return Night(title, nights[0].date, bosses, merged, notes, cfg.get("max_missed_fights", 1) * len(nights), "Settimana")
