"""Publish the night page to a static site repo (GitHub Pages): copy, regenerate the index, commit, push."""
import re
import shutil
import subprocess
from html import escape
from pathlib import Path
from typing import Callable

Runner = Callable[[list[str], Path], str]
DATED = re.compile(r"\d{4}-\d{2}-\d{2}")


def _git(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _index(site_dir: Path) -> str:
    nights = sorted((d.name for d in site_dir.iterdir() if d.is_dir() and DATED.fullmatch(d.name)), reverse=True)
    links = "".join(f'<li><a href="{escape(n)}/">{escape(n)}</a></li>' for n in nights)
    return (
        '<!doctype html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex"><title>Il Blazettino</title></head>'
        f"<body style=\"font-family:system-ui;max-width:30em;margin:2em auto;padding:0 1em\">"
        f"<h1>📰 Il Blazettino</h1><ul>{links}</ul></body></html>"
    )


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
    (site_dir / "index.html").write_text(_index(site_dir))
    _commit_and_push(site_dir, f"pagella {date}", run)
    return f"{site_url.rstrip('/')}/{date}/"


def remove(date: str, site_dir: Path, run: Runner = _git) -> None:
    """Take a night off the site (the link stops working; it stays in the branch history)."""
    if not DATED.fullmatch(date):
        raise ValueError(f"data non valida: {date!r} (serve YYYY-MM-DD)")
    shutil.rmtree(site_dir / date)  # FileNotFoundError if that night was never published
    (site_dir / "index.html").write_text(_index(site_dir))
    _commit_and_push(site_dir, f"rimossa pagella {date}", run)
