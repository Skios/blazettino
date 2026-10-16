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
