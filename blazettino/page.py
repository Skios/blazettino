"""Single-file responsive HTML report: tabs (night + one per boss), inline CSS/JS, no external requests."""
import re
from html import escape

from blazettino import kpi, report, tips
from blazettino.comment import Comment
from blazettino.night import BossReport, Night

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
:root{color-scheme:dark light;--bg:#14161c;--card:#1d2029;--fg:#e8e9ee;--muted:#9aa0b0;--line:#2c3040;--accent:#f0b429;--ok:#3fb950;--bad:#e5534b}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f8;--card:#fff;--fg:#1c1f27;--muted:#5d6475;--line:#dfe2ea;--accent:#b7791f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{margin:.2em 0 0;font-size:clamp(1.4rem,4vw,2rem)}
.sub{color:var(--muted);margin:.2em 0 1em}
.tabs{display:flex;gap:6px;overflow-x:auto;margin:0 0 1em;padding-bottom:4px}
.tab,.controls button,.controls select{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer;white-space:nowrap}
.tab[aria-pressed=true],.controls button[aria-pressed=true]{border-color:var(--accent);color:var(--accent)}
.tag{font-size:.65rem;font-weight:700;border-radius:4px;padding:1px 5px;margin-left:4px;color:#111}
.tag.kill{background:var(--ok)}.tag.wipe{background:var(--bad)}
.panel[hidden]{display:none}
.banner{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:1em}
.banner.kill{border-left:5px solid var(--ok)}.banner.wipe{border-left:5px solid var(--bad)}
.banner em{display:block;color:var(--muted);margin-top:.2em}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 1em}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:2px 10px;font-size:.8rem;color:var(--muted)}
.podium{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:1.2em}
.step{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center}
.step .medal{font-size:1.8rem}.step .who{font-weight:700}.step .what{color:var(--muted);font-size:.8rem}
.step.lvp{border-color:#b33}
.heatwrap{overflow-x:auto;margin-bottom:1.2em}
.heat{border-collapse:collapse;width:100%;font-size:.85rem}
.heat th,.heat td{border-bottom:1px solid var(--line);padding:4px 8px;text-align:center;white-space:nowrap}
.heat th:first-child,.heat td:first-child{text-align:left}
.heat td.g{background:hsl(calc(var(--g)*12) 60% 45% / .35);font-weight:600}
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.spacer{flex:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--cc);border-radius:12px;padding:12px 14px}
.card[hidden]{display:none}
.top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.card .who{display:flex;gap:10px;align-items:center}
.spec{flex:none;width:36px;height:36px;background-size:cover;border-radius:8px;border:2px solid var(--cc)}
.name{font-weight:700}.meta{color:var(--muted);font-size:.8rem}
.grade{flex:none;min-width:2.6rem;text-align:center;font-weight:800;font-size:1.2rem;border-radius:8px;padding:2px 8px;
  color:#111;background:hsl(calc(var(--g)*12) 70% 55%)}
.say{margin:.5em 0}.say summary{cursor:pointer;font-weight:700;color:var(--accent);font-size:.9rem;letter-spacing:.02em}
.text{margin:.3em 0 0}
.flag{color:var(--muted);font-size:.75rem}
details.nums{font-size:.82rem;color:var(--muted)}details.nums summary{cursor:pointer}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:.4em 0}dt{color:var(--muted)}dd{margin:0;color:var(--fg)}
ul{margin:.3em 0 0;padding-left:1.1em}
footer{color:var(--muted);font-size:.75rem;text-align:center;margin:2em 0 1em}
"""

JS = """
const tabs=[...document.querySelectorAll('.tab')],panels=[...document.querySelectorAll('.panel')];
function show(id,remember){
  panels.forEach(p=>p.hidden=p.id!==id);
  tabs.forEach(t=>t.setAttribute('aria-pressed',t.dataset.tab===id));
  if(remember)history.replaceState(null,'','#'+id);
}
tabs.forEach(t=>t.onclick=()=>show(t.dataset.tab,true));
show(panels.some(p=>p.id===location.hash.slice(1))?location.hash.slice(1):panels[0].id);
panels.forEach(panel=>{
  const grid=panel.querySelector('.grid'),cards=[...grid.children],sort=panel.querySelector('.sort');
  let role='all';
  const apply=()=>{
    cards.forEach(c=>c.hidden=!(role==='all'||c.dataset.role===role));
    [...cards].sort((a,b)=>sort.value==='name'?a.dataset.name.localeCompare(b.dataset.name)
      :b.dataset.grade-a.dataset.grade||a.dataset.name.localeCompare(b.dataset.name)).forEach(c=>grid.append(c));
  };
  panel.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{
    role=b.dataset.filter;
    panel.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',x===b));
    apply();
  });
  sort.onchange=apply;
});
"""


def _pretty(camel: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", camel)  # DemonHunter -> Demon Hunter


def _podium(top: list[kpi.Player]) -> str:
    return "".join(
        f'<div class="step{" lvp" if tag == "LVP" else ""}"><div class="medal">{medal}</div>'
        f'<div class="who">{escape(p.name)}</div>'
        f'<div class="what">{tag + " · " if tag else ""}voto {kpi.grade(p):g}</div></div>'
        for medal, tag, p in report.podium_players(top)
    )


def _card(p: kpi.Player, c: Comment | None, benched: bool, opened: bool, icons: dict[str, str], show_fights: bool) -> str:
    label = escape(f"{_pretty(p.spec)} {_pretty(p.cls)}")
    icon = f'<span class="spec i-{p.icon}" role="img" aria-label="{label}" title="{label}"></span>' if p.icon in icons else ""
    flag = '<div class="flag">poche presenze: fuori dal podio</div>' if benched else ""
    say = (
        f'<details class="say"{" open" if opened else ""}><summary>{escape(c.title)}</summary>'
        f'<p class="text">{escape(c.text)}</p></details>' if c else ""
    )
    deaths = "".join(f"<li>{escape(report.death_text(d))}</li>" for d in p.deaths) or "<li>nessuna</li>"
    fights = f"<dt>Boss</dt><dd>{p.fights}</dd>" if show_fights else ""
    return (
        f'<article class="card" style="--cc:{CLASS_COLORS.get(p.cls, FALLBACK_COLOR)};--g:{kpi.grade(p):g}" '
        f'data-role="{p.role}" data-grade="{kpi.grade(p):g}" data-name="{escape(p.name)}">'
        f'<div class="top"><div class="who">{icon}<div><div class="name">{escape(p.name)}</div>'
        f'<div class="meta">{label} · iLvl {p.ilvl}</div></div></div>'
        f'<div class="grade">{kpi.grade(p):g}</div></div>{flag}{say}'
        '<details class="nums"><summary>Numeri e morti</summary><dl>'
        f"<dt>Danni</dt><dd>{p.damage / 1e6:.2f}M · {p.dps / 1e3:.1f}k DPS · {report.parse_text(p, p.dps_parse)}</dd>"
        f"<dt>Cure</dt><dd>{p.healing / 1e6:.2f}M · {p.hps / 1e3:.1f}k HPS · {report.parse_text(p, p.hps_parse)}</dd>"
        f"<dt>Subiti</dt><dd>{p.taken / 1e6:.2f}M</dd>{fights}</dl><b>Morti</b><ul>{deaths}</ul></details></article>"
    )


def _controls() -> str:
    buttons = "".join(
        f'<button data-filter="{key}" aria-pressed="{str(key == "all").lower()}">{label}</button>' for key, label in FILTERS
    )
    return (
        f'<div class="controls">{buttons}<span class="spacer"></span>'
        '<label>Ordina <select class="sort"><option value="grade">Voto</option><option value="name">Nome</option></select></label></div>'
    )


def _panel(pid: str, hidden: bool, head: str, ranked, top, pool, comments, icons, show_fights: bool) -> str:
    opened = {p.name for _, _, p in report.podium_players(top)}
    cards = "".join(
        _card(p, comments.get(p.name), p not in pool, p.name in opened, icons, show_fights) for p in ranked
    )
    return (
        f'<div class="panel" id="{pid}"{" hidden" if hidden else ""}>{head}'
        f'<section class="podium">{_podium(top)}</section>{_controls()}<section class="grid">{cards}</section></div>'
    )


def _heat(night: Night, ranked: list[kpi.Player]) -> str:
    heads = "".join(
        f"<th>{escape(b.attempt.name)}<br><small>{'KILL' if b.attempt.kill else 'WIPE'}</small></th>" for b in night.bosses
    )
    lookup = [{p.name: kpi.grade(p) for p in b.players} for b in night.bosses]
    rows = "".join(
        f"<tr><td>{escape(p.name)}</td>"
        + "".join(f'<td class="g" style="--g:{lk[p.name]:g}">{lk[p.name]:g}</td>' if p.name in lk else "<td>–</td>" for lk in lookup)
        + f'<td class="g" style="--g:{kpi.grade(p):g}"><b>{kpi.grade(p):g}</b></td></tr>'
        for p in ranked
    )
    return f'<div class="heatwrap"><table class="heat"><thead><tr><th>Giocatore</th>{heads}<th>Serata</th></tr></thead><tbody>{rows}</tbody></table></div>'


def _banner(night: Night, boss: BossReport) -> str:
    a = boss.attempt
    if a.kill:
        return f'<div class="banner kill"><strong>KILL</strong> in {kpi.mmss(a.seconds)}</div>'
    return (
        f'<div class="banner wipe"><strong>{escape(tips.NO_KILL)}</strong> Miglior tentativo: boss a {a.pct:g}% '
        f"di vita dopo {kpi.mmss(a.seconds)}.<em>{escape(report.tip_for(night, boss))}</em></div>"
    )


def _icon_css(icons: dict[str, str]) -> str:
    return "".join(f".i-{name}{{background-image:url({uri})}}" for name, uri in icons.items())


def _share_head(night: Night, top: list[kpi.Player], url: str | None) -> str:
    """Unlisted page + Open Graph tags, so Discord/Telegram unfurl the link as a card."""
    mvp, lvp = top[0], top[-1]
    kills = sum(b.attempt.kill for b in night.bosses)
    desc = (
        f"MVP {mvp.name} ({kpi.grade(mvp):g}) · LVP {lvp.name} ({kpi.grade(lvp):g}) · "
        f"{len(night.bosses)} boss, {kills} kill"
    )
    tags = [
        '<meta name="robots" content="noindex">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="Il Blazettino · {escape(night.title)} {escape(night.date)}">',
        f'<meta property="og:description" content="{escape(desc)}">',
        '<meta name="twitter:card" content="summary">',
    ]
    if url:
        tags.append(f'<meta property="og:url" content="{escape(url)}">')
    return "".join(tags)


def render_html(night: Night, icons: dict[str, str] | None = None, url: str | None = None) -> str:
    icons = icons or {}
    ranked, pool, top = report.standings(night.players, len(night.bosses), night.max_missed)
    chips = "".join(f'<span class="chip">{escape(b.attempt.name)}</span>' for b in night.bosses)
    panels = [_panel("global", False, f'<div class="chips">{chips}</div>{_heat(night, ranked)}',
                     ranked, top, pool, night.comments, icons, True)]
    tabs = ['<button class="tab" data-tab="global" aria-pressed="true">Serata</button>']
    for i, b in enumerate(night.bosses, 1):
        pid = f"b{i}-{b.attempt.slug}"
        ranked_b = kpi.ranking(b.players)
        panels.append(_panel(pid, True, _banner(night, b), ranked_b, ranked_b, ranked_b, b.comments, icons, False))
        kind = "kill" if b.attempt.kill else "wipe"
        tabs.append(
            f'<button class="tab" data-tab="{pid}" aria-pressed="false">{escape(b.attempt.name)} '
            f'<span class="tag {kind}">{kind.upper()}</span></button>'
        )
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{_share_head(night, top, url)}"
        f"<title>Il Blazettino · {escape(night.title)} {escape(night.date)}</title>"
        f"<style>{CSS}{_icon_css(icons)}</style></head><body><main>"
        f"<h1>📰 Il Blazettino</h1><p class='sub'>Pagella — {escape(night.title)} · {escape(night.date)}</p>"
        f'<nav class="tabs">{"".join(tabs)}</nav>{"".join(panels)}'
        "<footer>Voti calcolati dai dati di WarcraftLogs, battute dell'IA. Si fa per ridere.</footer>"
        f"</main><script>{JS}</script></body></html>"
    )
