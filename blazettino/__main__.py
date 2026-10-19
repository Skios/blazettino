"""python -m blazettino <report_code> [--publish]
python -m blazettino --week <report_code>... [--publish]   one page per night plus the weekly one (settimana/<first date>/)
python -m blazettino --remove <YYYY-MM-DD>     take a published night off the site
python -m blazettino --refresh-site            rewrite site root + archive from the published nights

Writes out/<date>/{global.md, <boss>_kill|wipe.md, pagella.html, messaggio.txt}. With --publish the page is also
copied to the Pages repo (config: site_dir, site_url), committed and pushed, so the message link works.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

from blazettino import attempts, icons, kpi, message, night, page, publish, report, wcl
from blazettino.config import ROOT, load_config

FIGHTS = "fights{id name encounterID difficulty kill fightPercentage startTime endTime}"
USAGE = "uso: python -m blazettino <codice_report> [--publish] | --week <codice>... [--publish] | --remove <YYYY-MM-DD|settimana/YYYY-MM-DD> | --refresh-site"


def _remove(date: str, cfg: dict) -> None:
    if not cfg.get("site_dir"):
        raise SystemExit("--remove richiede site_dir in config.json (vedi README)")
    publish.remove(date, Path(cfg["site_dir"]).expanduser())
    sys.stdout.write(f"rimossa la pagella {date} dal sito\n")


def _refresh(cfg: dict) -> None:
    if not cfg.get("site_dir"):
        raise SystemExit("--refresh-site richiede site_dir in config.json (vedi README)")
    publish.refresh(Path(cfg["site_dir"]).expanduser())
    sys.stdout.write("indice e archivio del sito aggiornati\n")


def _build(code: str, cfg: dict) -> night.Night:
    info = wcl.report(code, f"title startTime {FIGHTS}")
    tries = attempts.best_tries(info["fights"])
    if not tries:
        raise SystemExit(f"nessun boss nel report {code}")
    loaded = [(a, kpi.load_fight(*wcl.fight_tables(code, a.id))) for a in tries]
    date = datetime.fromtimestamp(info["startTime"] / 1000).strftime("%Y-%m-%d")
    return night.assemble(info["title"], date, loaded, cfg)


def _save(n: night.Night, name: str, url: str | None) -> tuple[Path, str]:
    """Write the markdown files, the page and the chat message into out/<name>/; return (folder, message)."""
    folder = ROOT / "out" / name
    folder.mkdir(parents=True, exist_ok=True)
    for fname, text in report.files(n).items():
        (folder / fname).write_text(text)
    (folder / "pagella.html").write_text(page.render_html(n, icons.fetch(sorted({p.icon for p in n.players})), url))
    text = message.render(n, url)
    (folder / "messaggio.txt").write_text(text + "\n")
    return folder, text


def main(argv: list[str]) -> None:
    if argv[1:] == ["--refresh-site"]:
        return _refresh(load_config())
    if argv[1:2] == ["--remove"]:
        if len(argv) != 3:
            raise SystemExit(USAGE)
        return _remove(argv[2], load_config())
    flags = {"--publish", "--week"} & set(argv[1:])
    codes = [a for a in argv[1:] if not a.startswith("--")]
    if not codes or len(codes) > 1 and "--week" not in flags or len(argv[1:]) != len(codes) + len(flags):
        raise SystemExit(USAGE)
    do_publish, weekly = "--publish" in flags, "--week" in flags
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    cfg = load_config()
    site_dir, site_url = cfg.get("site_dir"), cfg.get("site_url")
    if do_publish and not (site_dir and site_url):
        raise SystemExit("--publish richiede site_dir e site_url in config.json (vedi README)")
    base = site_url.rstrip("/") if site_url else None
    out = Path(site_dir).expanduser() if site_dir else None

    nights = []
    for code in codes:
        n = _build(code, cfg)
        folder, text = _save(n, n.date, f"{base}/{n.date}/" if base else None)
        if do_publish:
            publish.publish(folder, n.date, out, site_url)
        sys.stdout.write(text + "\n\n")
        nights.append(n)
    if weekly:
        wk = night.assemble_week(nights, cfg)
        folder, text = _save(wk, f"settimana_{wk.date}", f"{base}/settimana/{wk.date}/" if base else None)
        if do_publish:
            publish.publish(folder, wk.date, out, site_url, section=publish.SECTION)
        sys.stdout.write(text + "\n")
    logging.getLogger(__name__).warning("salvati in %s%s", ROOT / "out", " e pubblicati" if do_publish else "")


if __name__ == "__main__":
    main(sys.argv)
