"""Render the night report card as markdown (readable as plain text on Discord/Telegram too)."""
from blazettino import kpi
from blazettino.comment import Comment

SECTIONS = (("tank", "Tank"), ("healer", "Healer"), ("dps", "DPS"))
MEDALS = ("🥇", "🥈", "🥉")


def _death(d: kpi.Death) -> str:
    where = f"{d.boss} " if d.boss else ""
    return f"{where}{kpi.mmss(d.time_s)} {d.ability}" + (" (strage)" if d.mass else "")


def _numbers(p: kpi.Player) -> str:
    deaths = "; ".join(_death(d) for d in p.deaths) or "nessuna"
    return (
        f"{p.damage / 1e6:.2f}M danni ({p.dps / 1e3:.1f}k DPS, parse {p.dps_parse}) · "
        f"{p.healing / 1e6:.2f}M cure ({p.hps / 1e3:.1f}k HPS, parse {p.hps_parse}) · "
        f"{p.taken / 1e6:.2f}M subiti · morti: {deaths}"
    )


def _entry(p: kpi.Player, c: Comment | None) -> str:
    head = f"**{p.name}** ({p.spec} {p.cls}, iLvl {p.ilvl}) — Voto {kpi.grade(p):g}"
    if c:
        return f"{head} — *{c.title}*\n{c.text}\n_{_numbers(p)}_"
    return f"{head}\n_{_numbers(p)}_"


def render(
    title: str, date: str, bosses: list[str], players: list[kpi.Player], comments: dict[str, Comment]
) -> str:
    ranked = kpi.ranking(players)
    podium = [f"{MEDALS[0]} MVP — {ranked[0].name} ({kpi.grade(ranked[0]):g})"]
    podium += [f"{m} {p.name} ({kpi.grade(p):g})" for m, p in zip(MEDALS[1:], ranked[1:3])]
    podium.append(f"💀 LVP — {ranked[-1].name} ({kpi.grade(ranked[-1]):g})")
    out = [f"# Pagella — {title} ({date})", f"Boss: {', '.join(bosses)}", "## Podio", "\n".join(podium)]
    for role, label in SECTIONS:
        group = [p for p in ranked if p.role == role]
        if group:
            out += [f"## {label}", "\n\n".join(_entry(p, comments.get(p.name)) for p in group)]
    return "\n\n".join(out) + "\n"
