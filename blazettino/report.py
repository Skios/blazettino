"""Markdown report cards: one file per boss attempt (kill/wipe) plus the global night."""
from blazettino import kpi, tips
from blazettino.comment import Comment
from blazettino.night import BossReport, Night

SECTIONS = (("tank", "Tank"), ("healer", "Healer"), ("dps", "DPS"))
MEDALS = ("🥇", "🥈", "🥉")


def death_text(d: kpi.Death) -> str:
    where = f"{d.boss} " if d.boss else ""
    return f"{where}{kpi.mmss(d.time_s)} {d.ability}" + (" (strage)" if d.mass else "")


def parse_text(p: kpi.Player, value: int) -> str:
    """'parse 56' on ranked fights, 'pos. 56/100' (inside-raid position) when WarcraftLogs has no ranking."""
    return f"parse {value}" if p.ranked else f"pos. {value}/100"


def _numbers(p: kpi.Player) -> str:
    deaths = "; ".join(death_text(d) for d in p.deaths) or "nessuna"
    return (
        f"{p.damage / 1e6:.2f}M danni ({p.dps / 1e3:.1f}k DPS, {parse_text(p, p.dps_parse)}) · "
        f"{p.healing / 1e6:.2f}M cure ({p.hps / 1e3:.1f}k HPS, {parse_text(p, p.hps_parse)}) · "
        f"{p.taken / 1e6:.2f}M subiti · morti: {deaths}"
    )


def _entry(p: kpi.Player, c: Comment | None, benched: bool) -> str:
    head = f"**{p.name}** ({p.spec} {p.cls}, iLvl {p.ilvl}) — Voto {kpi.grade(p):g}"
    if benched:
        head += " (poche presenze: fuori dal podio)"
    if c:
        return f"{head} — *{c.title}*\n{c.text}\n_{_numbers(p)}_"
    return f"{head}\n_{_numbers(p)}_"


def standings(
    players: list[kpi.Player], n_bosses: int, max_missed: int
) -> tuple[list[kpi.Player], list[kpi.Player], list[kpi.Player]]:
    """(everyone ranked, podium-eligible pool, pool ranked). Podium counts only raiders who missed
    at most max_missed of the night's boss fights; if nobody qualifies everyone does."""
    ranked = kpi.ranking(players)
    pool = kpi.eligible(ranked, n_bosses, max_missed) or ranked
    return ranked, pool, kpi.ranking(pool)


def podium_players(top: list[kpi.Player]) -> list[tuple[str, str, kpi.Player]]:
    """(medal, tag, player): MVP, the next two, then the LVP."""
    steps = [(MEDALS[0], "MVP", top[0])] + [(m, "", p) for m, p in zip(MEDALS[1:], top[1:3])]
    return steps + [("💀", "LVP", top[-1])]


def _podium(top: list[kpi.Player]) -> str:
    return "\n".join(
        f"{medal} {tag + ' — ' if tag else ''}{p.name} ({kpi.grade(p):g})" for medal, tag, p in podium_players(top)
    )


def _sections(ranked: list[kpi.Player], comments: dict[str, Comment], pool: list[kpi.Player]) -> list[str]:
    out = []
    for role, label in SECTIONS:
        group = [p for p in ranked if p.role == role]
        if group:
            out += [f"## {label}", "\n\n".join(_entry(p, comments.get(p.name), p not in pool) for p in group)]
    return out


def boss_label(a) -> str:
    return "KILL" if a.kill else f"WIPE a {a.pct:g}%"


def tip_for(night: Night, boss: BossReport) -> str:
    return tips.wipe_tip(f"{night.date}-{boss.attempt.id}-{boss.attempt.name}")


def render_boss(night: Night, boss: BossReport) -> str:
    a = boss.attempt
    ranked = kpi.ranking(boss.players)
    out = [f"# {a.name} — {boss_label(a)} ({kpi.mmss(a.seconds)})", f"{night.title} · {night.date}"]
    if not a.kill:
        out.append(f"**{tips.NO_KILL}** Miglior tentativo: boss a {a.pct:g}% di vita.\n> {tip_for(night, boss)}")
    out += ["## Podio", _podium(ranked), *_sections(ranked, boss.comments, ranked)]
    return "\n\n".join(out) + "\n"


def _grades_table(night: Night, ranked: list[kpi.Player]) -> str:
    heads = [b.attempt.name + ("" if b.attempt.kill else " (WIPE)") for b in night.bosses]
    lookup = [{p.name: kpi.grade(p) for p in b.players} for b in night.bosses]
    rows = ["| Giocatore | " + " | ".join(heads) + " | Serata |", "|---" * (len(heads) + 2) + "|"]
    for p in ranked:
        cells = [f"{lk[p.name]:g}" if p.name in lk else "–" for lk in lookup]
        rows.append(f"| {p.name} | " + " | ".join(cells) + f" | **{kpi.grade(p):g}** |")
    return "\n".join(rows)


def render_global(night: Night) -> str:
    ranked, pool, top = standings(night.players, len(night.bosses), night.max_missed)
    bosses = ", ".join(f"{b.attempt.name} ({boss_label(b.attempt)})" for b in night.bosses)
    out = [
        f"# Pagella GLOBAL — {night.title} ({night.date})",
        f"Boss: {bosses}",
        "## Podio", _podium(top),
        "## Voti per boss", _grades_table(night, ranked),
        *_sections(ranked, night.comments, pool),
    ]
    return "\n\n".join(out) + "\n"


def files(night: Night) -> dict[str, str]:
    """filename -> markdown: global.md plus <boss>_kill.md / <boss>_wipe.md for every boss."""
    out = {} if night.kind == "Boss" else {"global.md": render_global(night)}
    for b in night.bosses:
        out[f"{b.attempt.slug}_{'kill' if b.attempt.kill else 'wipe'}.md"] = render_boss(night, b)
    return out
