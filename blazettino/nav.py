"""Dress a published page for the site: top bar with the logo and the way home, dark theme only, animated picker.

Applied to the files already on the site (new and old pages alike, no regeneration) and idempotent:
everything it adds sits between <!--nav--> and <!--/nav--> and is replaced on the next run.
"""
import re

from blazettino import kpi

BLOCK = re.compile(r"<!--nav-->.*?<!--/nav-->", re.S)
OLD_FOOTER_LINK = re.compile(r'<br><a href="[^"]*">Home</a>(?=</footer>)')
LIGHT_THEME = re.compile(r"@media \(prefers-color-scheme:light\)\{:root\{[^}]*\}\}")

KPI_META = re.compile(r'<meta name="blazettino-kpi" content="(\d+)"')
FIRST_VERSION = 1  # pages published before the version existed used the first formula


OLD_META = '<meta name="blazettino-old" content="1">'


def mark_old(html: str) -> str:
    """Flag a page as replaced by a newer version of the same night (kept, never overwritten)."""
    return html if OLD_META in html else html.replace("</head>", OLD_META + "</head>", 1) if "</head>" in html else OLD_META + html


def is_old(html: str) -> bool:
    """True when the page was replaced by a newer one or made with an older KPI version than the current."""
    m = KPI_META.search(html)
    return OLD_META in html or int(m[1] if m else FIRST_VERSION) < kpi.KPI_VERSION


CSS = """
.bar{position:sticky;top:0;z-index:5;display:flex;gap:18px;align-items:center;padding:8px 16px;background:var(--card);border-bottom:1px solid var(--line)}
.bar a{color:var(--accent);text-decoration:none;font-weight:700}
.bar .brand{display:flex;gap:8px;align-items:center;font:700 1.05rem Georgia,'Times New Roman',serif}
.bar img{height:30px;width:auto}
h1 .logo{height:1.3em;width:auto;margin-right:.3em;vertical-align:-.25em}
.bar .old{margin-left:auto;background:var(--muted);color:#111;border-radius:4px;padding:1px 8px;font-size:.75rem}
body:has(.bar .old) main{filter:grayscale(1);opacity:.8}
.pick .panel{display:none}
.pick .tabs{flex-wrap:wrap;justify-content:center;gap:14px;overflow:visible;margin-top:12vh}
.pick .tab{font-size:1.15rem;padding:16px 26px}
.pick .tab[aria-pressed=true]{border-color:var(--line);color:var(--fg)}
@media (prefers-reduced-motion:reduce){::view-transition-group(*){animation-duration:.01s}}
"""

# Kill banners show "NEW RECORD" / "+0:13" read from the boss file the publisher keeps at <home>/data/bosses/.
REC_JS = """
document.querySelectorAll('.rec').forEach(el=>fetch('__HOME__data/bosses/'+el.dataset.boss+'.json').then(r=>r.json()).then(d=>{
const t=((d.labels||{})[el.dataset.code]||{})[el.dataset.diff]||'';el.textContent=t;el.classList.toggle('new',t==='NEW RECORD');}).catch(()=>{}));
"""

# Without a #panel in the address the night opens on the big buttons; a click morphs them into the normal tab bar.
JS = """
(()=>{const tabs=[...document.querySelectorAll('.tab')],panels=[...document.querySelectorAll('.panel')];
if(!tabs.length||panels.some(p=>p.id===location.hash.slice(1)))return;
document.body.classList.add('pick');
tabs.forEach((t,i)=>{t.style.viewTransitionName='t'+i;
t.addEventListener('click',()=>{const go=()=>document.body.classList.remove('pick');
document.startViewTransition?document.startViewTransition(go):go();});});})();
"""


def enhance(html: str, rel: str) -> str:
    """`rel` is the page folder inside the site (2026-10-19, settimana/2026-10-07, 2026-10-14/ulatek)."""
    html = BLOCK.sub("", html)
    html = LIGHT_THEME.sub("", OLD_FOOTER_LINK.sub("", html)).replace("color-scheme:dark light", "color-scheme:dark")
    home = "../" * (rel.count("/") + 1)
    back = '<a href="../">← Serata</a>' if re.fullmatch(r"\d{4}-\d{2}-\d{2}/[^/]+", rel) else ""
    html = html.replace("<h1>📰 Il Blazettino</h1>", f'<h1><img class="logo" src="{home}logo.png" alt="">Il Blazettino</h1>')
    head = f'<!--nav--><link rel="icon" href="{home}logo.png"><style>{CSS}</style><!--/nav-->'
    old = '<span class="old" title="Versione sostituita o calcolata con una formula precedente">OLD</span>' if is_old(html) else ""
    bar = f'<!--nav--><nav class="bar"><a class="brand" href="{home}"><img src="{home}logo.png" alt="">Il Blazettino</a>{back}{old}</nav><!--/nav-->'
    html = html.replace("</head>", head + "</head>", 1)
    html = re.sub(r"<body[^>]*>", lambda m: m.group(0) + bar, html, count=1)
    return html.replace("</body>", f"<!--nav--><script>{JS}{REC_JS.replace('__HOME__', home)}</script><!--/nav--></body>", 1)
