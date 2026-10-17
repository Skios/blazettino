"""Publish the night page to a static site repo (GitHub Pages): copy, regenerate the index, commit, push."""
import re
import shutil
import subprocess
from html import escape, unescape
from pathlib import Path
from typing import Callable

Runner = Callable[[list[str], Path], str]
DATED = re.compile(r"\d{4}-\d{2}-\d{2}")


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


def _root(nights: list[str]) -> str:
    """The site root: opens straight on the latest night (instant redirect, plus a visible link)."""
    if not nights:
        return _head("Il Blazettino") + "<body><main><h1>📰 Il Blazettino</h1><p class='sub'>Nessuna pagella pubblicata, per ora.</p></main></body></html>"
    latest = nights[0]
    return (
        _head("Il Blazettino", f'<meta http-equiv="refresh" content="0; url={latest}/">')
        + f"<body><main><h1>📰 Il Blazettino</h1><p class='sub'>Ti porto all'ultima pagella…</p>"
        f'<p><a class="btn" href="{latest}/">Apri l\'ultima pagella ({_human(latest)})</a></p>'
        f'<p><a href="archivio/">Tutte le serate</a></p></main>'
        f'<script>location.replace("{latest}/")</script></body></html>'
    )


def _archive(site_dir: Path, nights: list[str]) -> str:
    items = []
    for i, n in enumerate(nights):
        title, desc = _summary(site_dir / n)
        tag = '<span class="tag">Ultima</span>' if i == 0 else ""
        items.append(
            f'<li><a href="../{n}/"><span class="d">{_human(n)}</span>{tag}'
            + (f'<span class="t">{escape(title)}</span>' if title else "")
            + (f'<span class="s">{escape(desc)}</span>' if desc else "")
            + "</a></li>"
        )
    return (
        _head("Il Blazettino · Tutte le serate")
        + f"<body><main><h1>📰 Il Blazettino</h1><p class='sub'>Tutte le serate</p><ul>{''.join(items)}</ul></main></body></html>"
    )


def _write_site_pages(site_dir: Path) -> None:
    nights = _nights(site_dir)
    (site_dir / "index.html").write_text(_root(nights))
    (site_dir / "archivio").mkdir(exist_ok=True)
    (site_dir / "archivio" / "index.html").write_text(_archive(site_dir, nights))


def _commit_and_push(site_dir: Path, message: str, run: Runner) -> None:
    run(["git", "add", "-A"], site_dir)
    if run(["git", "status", "--porcelain"], site_dir).strip():
        run(["git", "commit", "-m", message], site_dir)
        run(["git", "push"], site_dir)


def publish(folder: Path, date: str, site_dir: Path, site_url: str, run: Runner = _git) -> str:
    """Copy folder/pagella.html to site_dir/<date>/index.html, commit and push; return the public URL."""
    dest = site_dir / date
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(folder / "pagella.html", dest / "index.html")
    (site_dir / ".nojekyll").touch()
    (site_dir / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, f"pagella {date}", run)
    return f"{site_url.rstrip('/')}/{date}/"


def remove(date: str, site_dir: Path, run: Runner = _git) -> None:
    """Take a night off the site (the link stops working; it stays in the branch history)."""
    if not DATED.fullmatch(date):
        raise ValueError(f"data non valida: {date!r} (serve YYYY-MM-DD)")
    shutil.rmtree(site_dir / date)  # FileNotFoundError if that night was never published
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, f"rimossa pagella {date}", run)


def refresh(site_dir: Path, run: Runner = _git) -> None:
    """Rewrite the site root and the archive from the nights already published (no regeneration, no LLM)."""
    _write_site_pages(site_dir)
    _commit_and_push(site_dir, "aggiorna indice e archivio", run)
