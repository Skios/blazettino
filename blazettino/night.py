"""The night as the reports see it: one BossReport per boss (best try) plus the merged night."""
import dataclasses
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from blazettino import abilities, awards, comment, kpi, roster
from blazettino.attempts import Attempt
from blazettino.comment import Comment

LLM_WORKERS = 1  # one call at a time: with two in flight the free tier answered 429/503 too often (success rate ~60%)


@dataclass(frozen=True)
class BossReport:
    attempt: Attempt
    players: list[kpi.Player]
    comments: dict[str, Comment]  # also the prize comments, under "premio:<key>"
    awards: tuple[awards.Award, ...] = ()


@dataclass(frozen=True)
class Night:
    title: str
    date: str
    bosses: list[BossReport]
    players: list[kpi.Player]  # merged across bosses
    comments: dict[str, Comment]  # night-wide, from the aggregated data
    max_missed: int
    kind: str = "Serata"  # "Settimana" for the weekly aggregate


def clean_title(title: str) -> str:
    """WarcraftLogs titles sometimes arrive with date and boss glued on ('Raid2026-10-1926Boss'): keep what precedes the date."""
    head = re.split(r"\d{4}-\d{2}-\d{2}", title, maxsplit=1)[0].strip()
    return head or title


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
    book = cfg.get("players", {})
    exclude = {roster.canon(n, book) for n in cfg.get("exclude", ())}
    spells = cfg.get("spells", {})
    per_boss = [(a, abilities.tag_deaths([p for p in roster.apply(ps, book) if roster.canon(p.name, book) not in exclude], spells)) for a, ps in tries]
    merged = kpi.merge([_tag_boss(ps, a.name) for a, ps in per_boss])
    prizes = [tuple(awards.compute(ps, a.seconds)) for a, ps in per_boss]
    jobs = [(ps, "\n\n".join(filter(None, [comment.attempt_context(a), comment.awards_context(w)]))) for (a, ps), w in zip(per_boss, prizes)]
    jobs.append((merged, comment.night_context([a for a, _ in per_boss])))
    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as pool:
        notes = list(pool.map(lambda job: comments_fn(job[0], cfg, context=job[1]), jobs))
    bosses = [BossReport(a, ps, n, w) for (a, ps), n, w in zip(per_boss, notes, prizes)]
    return Night(clean_title(title), date, bosses, merged, notes[-1], cfg.get("max_missed_fights", 1))


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


def assemble_boss(
    title: str, date: str, attempt: Attempt, players: list[kpi.Player], cfg: dict,
    comments_fn: Callable[..., dict[str, Comment]] = comment.comments,
) -> Night:
    """A page for one boss of a night: one LLM call, its comments are the page comments."""
    book = cfg.get("players", {})
    exclude = {roster.canon(n, book) for n in cfg.get("exclude", ())}
    ps = abilities.tag_deaths([p for p in roster.apply(players, book) if roster.canon(p.name, book) not in exclude], cfg.get("spells", {}))
    prizes = tuple(awards.compute(ps, attempt.seconds))
    notes = comments_fn(ps, cfg, context="\n\n".join(filter(None, [comment.attempt_context(attempt), comment.awards_context(prizes)])))
    return Night(
        f"{attempt.name} ({_day(date)}) · {clean_title(title)}", date, [BossReport(attempt, ps, notes, prizes)], ps, notes,
        cfg.get("max_missed_fights", 1), "Boss",
    )
