"""Dress a published page for the site: top bar with the logo and the way home, dark theme only, animated picker.

Applied to the files already on the site (new and old pages alike, no regeneration) and idempotent:
everything it adds sits between <!--nav--> and <!--/nav--> and is replaced on the next run.
"""
import re

BLOCK = re.compile(r"<!--nav-->.*?<!--/nav-->", re.S)
OLD_FOOTER_LINK = re.compile(r'<br><a href="[^"]*">Home</a>(?=</footer>)')
LIGHT_THEME = re.compile(r"@media \(prefers-color-scheme:light\)\{:root\{[^}]*\}\}")

CSS = """
.bar{position:sticky;top:0;z-index:5;display:flex;gap:18px;align-items:center;padding:8px 16px;background:var(--card);border-bottom:1px solid var(--line)}
.bar a{color:var(--accent);text-decoration:none;font-weight:700}
.bar .brand{display:flex;gap:8px;align-items:center;font:700 1.05rem Georgia,'Times New Roman',serif}
.bar img{height:30px;width:auto}
.pick .panel{display:none}
.pick .tabs{flex-wrap:wrap;justify-content:center;gap:14px;overflow:visible;margin-top:12vh}
.pick .tab{font-size:1.15rem;padding:16px 26px}
.pick .tab[aria-pressed=true]{border-color:var(--line);color:var(--fg)}
@media (prefers-reduced-motion:reduce){::view-transition-group(*){animation-duration:.01s}}
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
    head = f'<!--nav--><link rel="icon" href="{home}logo.png"><style>{CSS}</style><!--/nav-->'
    bar = f'<!--nav--><nav class="bar"><a class="brand" href="{home}"><img src="{home}logo.png" alt="">Il Blazettino</a>{back}</nav><!--/nav-->'
    html = html.replace("</head>", head + "</head>", 1)
    html = re.sub(r"<body[^>]*>", lambda m: m.group(0) + bar, html, count=1)
    return html.replace("</body>", f"<!--nav--><script>{JS}</script><!--/nav--></body>", 1)
