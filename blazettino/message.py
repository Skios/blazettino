"""The short plain-text comment to post next to the page link (Discord/Telegram: no markdown, well under 2000 chars)."""
from blazettino import kpi, report
from blazettino.night import Night


def _boss(b) -> str:
    a = b.attempt
    return f"{a.name} ✅" if a.kill else f"{a.name} ❌ {a.pct:g}%"


def render(night: Night, url: str | None = None) -> str:
    _, _, top = report.standings(night.players, len(night.bosses), night.max_missed)
    mvp, lvp = top[0], top[-1]
    day = f"{night.date[8:]}/{night.date[5:7]}"
    lines = [
        f"📰 Il Blazettino — {night.title} ({day})",
        f"🥇 {mvp.name} ({kpi.grade(mvp):g}) · 🥈 {top[1].name} · 🥉 {top[2].name} · 💀 LVP {lvp.name} ({kpi.grade(lvp):g})",
        "Boss: " + " · ".join(_boss(b) for b in night.bosses),
    ]
    for label, p in (("MVP", mvp), ("LVP", lvp)):
        c = night.comments.get(p.name)
        if c:
            lines.append(f"{label} {p.name}: «{c.title}»")
    if url:
        lines.append(f"👉 {url}")
    return "\n".join(lines)
