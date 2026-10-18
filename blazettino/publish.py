"""Publish the night page to a static site repo (GitHub Pages): copy, regenerate the index, commit, push."""
import re
import shutil
import subprocess
from html import escape, unescape
from pathlib import Path
from typing import Callable

Runner = Callable[[list[str], Path], str]
DATED = re.compile(r"\d{4}-\d{2}-\d{2}")
SECTION = "settimana"
REMOVABLE = re.compile(rf"({SECTION}/)?\d{{4}}-\d{{2}}-\d{{2}}")


def _git(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
          "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")

SITE_CSS = """
:root{color-scheme:dark light;--bg:#14161c;--card:#1d2029;--fg:#e8e9ee;--muted:#9aa0b0;--line:#2c3040;--accent:#f0b429}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f8;--card:#fff;--fg:#1c1f27;--muted:#5d6475;--line:#dfe2ea;--accent:#b7791f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding:24px 16px}
h1{margin:.2em 0 0;font-size:clamp(1.4rem,4vw,2rem)}
.sub{color:var(--muted);margin:.2em 0 1.2em}
a{color:var(--accent)}
.btn{display:inline-block;background:var(--card);border:1px solid var(--accent);border-radius:10px;padding:10px 16px;text-decoration:none;font-weight:700}
h2{font-size:1.05rem;margin:1.6em 0 .5em;color:var(--muted)}
.btn{margin-bottom:.4em}
ul{list-style:none;margin:0;padding:0;display:grid;gap:10px}
li a{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;color:var(--fg);text-decoration:none}
li a:hover{border-color:var(--accent)}
.d{font-weight:700}.t{display:block;color:var(--accent);font-size:.9rem}.s{display:block;color:var(--muted);font-size:.8rem}
.tag{font-size:.65rem;font-weight:700;border-radius:4px;padding:1px 6px;margin-left:8px;color:#111;background:var(--accent)}
"""


def _head(title: str, extra: str = "") -> str:
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="robots" content="noindex">{extra}<title>{escape(title)}</title><style>{SITE_CSS}</style></head>'
    )


def _nights(site_dir: Path) -> list[str]:
    """Published nights, newest first."""
    return sorted((d.name for d in site_dir.iterdir() if d.is_dir() and DATED.fullmatch(d.name)), reverse=True)


def _human(date: str) -> str:
    return f"{int(date[8:])} {MONTHS[int(date[5:7]) - 1]} {date[:4]}"


def _summary(night_dir: Path) -> tuple[str, str]:
    """(title, description) read back from the generated page; empty when the page lacks them."""
    try:
        html = (night_dir / "index.html").read_text()
    except OSError:
        return "", ""
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    desc = re.search(r'property="og:description" content="(.*?)"', html)
    clean = lambda m: unescape(m.group(1)) if m else ""
    name = re.sub(r"\s*\d{4}-\d{2}-\d{2}$", "", re.sub(r"^Il Blazettino · ", "", clean(title)))
    return name, clean(desc)


def _weeks(site_dir: Path) -> list[str]:
    """Published weekly pages (settimana/<first night>/), newest first."""
    base = site_dir / SECTION
    return sorted((d.name for d in base.iterdir() if DATED.fullmatch(d.name)), reverse=True) if base.is_dir() else []


def _item(site_dir: Path, folder: str, head: str | None, latest: bool) -> str:
    """One card of the home: `head` is the line above the title (None: the page title is the head)."""
    title, desc = _summary(site_dir / folder)
    tag = '<span class="tag">Ultima</span>' if latest else ""
    top = head or title or folder
    return (
        f'<li><a href="{folder}/"><span class="d">{escape(top)}</span>{tag}'
        + (f'<span class="t">{escape(title)}</span>' if head and title else "")
        + (f'<span class="s">{escape(desc)}</span>' if desc else "")
        + "</a></li>"
    )


def _home(site_dir: Path) -> str:
    """The site root: a page to pick the night or the week (the latest night is one tap away)."""
    nights, weeks = _nights(site_dir), _weeks(site_dir)
    body = "<h1>📰 Il Blazettino</h1><p class='sub'>Le pagelle della Blaze of Glory</p>"
    if not nights and not weeks:
        return _head("Il Blazettino") + f"<body><main>{body}<p>Nessuna pagella pubblicata, per ora.</p></main></body></html>"
    if nights:
        body += f'<p><a class="btn" href="{nights[0]}/">Apri l\'ultima serata ({_human(nights[0])})</a></p>'
    if weeks:
        items = "".join(_item(site_dir, f"{SECTION}/{w}", None, i == 0) for i, w in enumerate(weeks))
        body += f"<h2>Settimanali</h2><ul>{items}</ul>"
    if nights:
        items = "".join(_item(site_dir, n, _human(n), i == 0) for i, n in enumerate(nights))
        body += f"<h2>Serate</h2><ul>{items}</ul>"
    return _head("Il Blazettino") + f"<body><main>{body}</main></body></html>"


def _write_site_pages(site_dir: Path) -> None:
    (site_dir / "index.html").write_text(_home(site_dir))
    (site_dir / "archivio").mkdir(exist_ok=True)  # the old archive address keeps working
    (site_dir / "archivio" / "index.html").write_text(_head("Il Blazettino", '<meta http-equiv="refresh" content="0; url=../">') + '<body><a href="../">Home</a></body></html>')


def _commit_and_push(site_dir: Path, message: str, run: Runner) -> None:
    run(["git", "add", "-A"], site_dir)
    if run(["git", "status", "--porcelain"], site_dir).strip():
        run(["git", "commit", "-m", message], site_dir)
        run(["git", "push"], site_dir)


def publish(folder: Path, date: str, site_dir: Path, site_url: str, run: Runner = _git, section: str = "") -> str:
    """Copy folder/pagella.html to site_dir/[section/]<date>/index.html, commit and push; return the public URL."""
    dest = site_dir / section / date
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(folder / "pagella.html", dest / "index.html")
    (site_dir / ".nojekyll").touch()
    (site_dir / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, f"pagella {date}", run)
    return "/".join(p for p in (site_url.rstrip("/"), section, date) if p) + "/"


def remove(date: str, site_dir: Path, run: Runner = _git) -> None:
    """Take a night (or a week: settimana/<date>) off the site (the link stops working; it stays in the branch history)."""
    if not REMOVABLE.fullmatch(date):
        raise ValueError(f"data non valida: {date!r} (serve YYYY-MM-DD o settimana/YYYY-MM-DD)")
    shutil.rmtree(site_dir / date)  # FileNotFoundError if that night was never published
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, f"rimossa pagella {date}", run)


def refresh(site_dir: Path, run: Runner = _git) -> None:
    """Rewrite the site root and the archive from the nights already published (no regeneration, no LLM)."""
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, "aggiorna indice e archivio", run)
