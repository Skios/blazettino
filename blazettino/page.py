"""Single-file responsive HTML report card: inline CSS/JS, no external requests, all text escaped."""
import re
from html import escape

from blazettino import kpi, report
from blazettino.comment import Comment

# Official WoW class colours, keyed by the WarcraftLogs class name.
CLASS_COLORS = {
    "DeathKnight": "#C41E3A", "DemonHunter": "#A330C9", "Druid": "#FF7C0A", "Evoker": "#33937F",
    "Hunter": "#AAD372", "Mage": "#3FC7EB", "Monk": "#00FF98", "Paladin": "#F48CBA",
    "Priest": "#FFFFFF", "Rogue": "#FFF468", "Shaman": "#0070DD", "Warlock": "#8788EE",
    "Warrior": "#C69B6D",
}
FALLBACK_COLOR = "#888888"
FILTERS = (("all", "Tutti"), ("tank", "Tank"), ("healer", "Healer"), ("dps", "DPS"))

CSS = """
:root{color-scheme:dark light;--bg:#14161c;--card:#1d2029;--fg:#e8e9ee;--muted:#9aa0b0;--line:#2c3040;--accent:#f0b429}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f8;--card:#fff;--fg:#1c1f27;--muted:#5d6475;--line:#dfe2ea;--accent:#b7791f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{margin:.2em 0 0;font-size:clamp(1.4rem,4vw,2rem)}
.sub{color:var(--muted);margin:.2em 0 1em}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 1em}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:.8rem;color:var(--muted)}
.podium{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:1.2em}
.step{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center}
.step .medal{font-size:1.8rem}.step .who{font-weight:700}.step .what{color:var(--muted);font-size:.8rem}
.step.lvp{border-color:#b33}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.controls button,.controls select{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer}
.controls button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
.spacer{flex:1}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--cc);border-radius:12px;padding:12px 14px}
.card[hidden]{display:none}
.top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.card .who{display:flex;gap:10px;align-items:center}
.spec{flex:none;border-radius:8px;border:2px solid var(--cc)}
.name{font-weight:700}.meta{color:var(--muted);font-size:.8rem}
.grade{flex:none;min-width:2.6rem;text-align:center;font-weight:800;font-size:1.2rem;border-radius:8px;padding:2px 8px;
  color:#111;background:hsl(calc(var(--g)*12) 70% 55%)}
.title{margin:.5em 0 .1em;font-weight:700;color:var(--accent);font-size:.9rem;letter-spacing:.02em}
.text{margin:0 0 .5em}
.flag{color:var(--muted);font-size:.75rem}
details{font-size:.82rem;color:var(--muted)}summary{cursor:pointer}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:.4em 0}dt{color:var(--muted)}dd{margin:0;color:var(--fg)}
ul{margin:.3em 0 0;padding-left:1.1em}
footer{color:var(--muted);font-size:.75rem;text-align:center;margin:2em 0 1em}
"""

JS = """
const grid=document.getElementById('grid'),cards=[...grid.children],sort=document.getElementById('sort');
let role='all';
function apply(){
  cards.forEach(c=>c.hidden=!(role==='all'||c.dataset.role===role));
  const key=sort.value;
  [...cards].sort((a,b)=>key==='name'?a.dataset.name.localeCompare(b.dataset.name)
    :b.dataset.grade-a.dataset.grade||a.dataset.name.localeCompare(b.dataset.name)).forEach(c=>grid.append(c));
}
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{
  role=b.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',x===b));
  apply();
});
sort.onchange=apply;
"""


def _pretty(camel: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", camel)  # DemonHunter -> Demon Hunter


def _podium(top: list[kpi.Player]) -> str:
    steps = [("🥇", "MVP", top[0])] + [(m, "", p) for m, p in zip(report.MEDALS[1:], top[1:3])]
    steps.append(("💀", "LVP", top[-1]))
    return "".join(
        f'<div class="step{" lvp" if tag == "LVP" else ""}"><div class="medal">{medal}</div>'
        f'<div class="who">{escape(p.name)}</div>'
        f'<div class="what">{tag + " · " if tag else ""}voto {kpi.grade(p):g}</div></div>'
        for medal, tag, p in steps
    )


def _card(p: kpi.Player, c: Comment | None, benched: bool, icons: dict[str, str]) -> str:
    color = CLASS_COLORS.get(p.cls, FALLBACK_COLOR)
    deaths = "".join(f"<li>{escape(report.death_text(d))}</li>" for d in p.deaths) or "<li>nessuna</li>"
    words = (
        f'<div class="title">{escape(c.title)}</div><p class="text">{escape(c.text)}</p>' if c else ""
    )
    flag = '<div class="flag">poche presenze: fuori dal podio</div>' if benched else ""
    label = escape(f"{_pretty(p.spec)} {_pretty(p.cls)}")
    icon = f'<img class="spec" src="{icons[p.icon]}" alt="{label}" width="36" height="36">' if p.icon in icons else ""
    return (
        f'<article class="card" style="--cc:{color};--g:{kpi.grade(p):g}" data-role="{p.role}" '
        f'data-grade="{kpi.grade(p):g}" data-name="{escape(p.name)}">'
        f'<div class="top"><div class="who">{icon}<div><div class="name">{escape(p.name)}</div>'
        f'<div class="meta">{label} · iLvl {p.ilvl}</div></div></div>'
        f'<div class="grade">{kpi.grade(p):g}</div></div>{flag}{words}'
        "<details><summary>Numeri e morti</summary><dl>"
        f"<dt>Danni</dt><dd>{p.damage / 1e6:.2f}M · {p.dps / 1e3:.1f}k DPS · parse {p.dps_parse}</dd>"
        f"<dt>Cure</dt><dd>{p.healing / 1e6:.2f}M · {p.hps / 1e3:.1f}k HPS · parse {p.hps_parse}</dd>"
        f"<dt>Subiti</dt><dd>{p.taken / 1e6:.2f}M</dd>"
        f"<dt>Boss</dt><dd>{p.fights}</dd></dl><b>Morti</b><ul>{deaths}</ul></details></article>"
    )


def render_html(
    title: str,
    date: str,
    bosses: list[str],
    players: list[kpi.Player],
    comments: dict[str, Comment],
    max_missed: int = 1,
    icons: dict[str, str] | None = None,
) -> str:
    icons = icons or {}
    ranked, pool, top = report.standings(players, len(bosses), max_missed)
    chips = "".join(f'<span class="chip">{escape(b)}</span>' for b in bosses)
    buttons = "".join(
        f'<button data-filter="{key}" aria-pressed="{str(key == "all").lower()}">{label}</button>'
        for key, label in FILTERS
    )
    cards = "".join(_card(p, comments.get(p.name), p not in pool, icons) for p in ranked)
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Il Blazettino · {escape(title)} {escape(date)}</title><style>{CSS}</style></head><body><main>"
        f"<h1>📰 Il Blazettino</h1><p class='sub'>Pagella — {escape(title)} · {escape(date)}</p>"
        f'<div class="chips">{chips}</div><section class="podium">{_podium(top)}</section>'
        f'<div class="controls">{buttons}<span class="spacer"></span>'
        '<label>Ordina <select id="sort"><option value="grade">Voto</option><option value="name">Nome</option></select></label></div>'
        f'<section id="grid">{cards}</section>'
        "<footer>Voti calcolati dai dati di WarcraftLogs, battute dell'IA. Si fa per ridere.</footer>"
        f"</main><script>{JS}</script></body></html>"
    )
