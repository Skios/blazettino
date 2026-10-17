"""python -m blazettino <report_code> [--publish]
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

FIGHTS = "fights{id name encounterID kill fightPercentage startTime endTime}"
USAGE = "uso: python -m blazettino <codice_report> [--publish] | --remove <YYYY-MM-DD> | --refresh-site"


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


def main(argv: list[str]) -> None:
    if argv[1:] == ["--refresh-site"]:
        return _refresh(load_config())
    if argv[1:2] == ["--remove"]:
        if len(argv) != 3:
            raise SystemExit(USAGE)
        return _remove(argv[2], load_config())
    args = [a for a in argv[1:] if a != "--publish"]
    do_publish = "--publish" in argv[1:]
    if len(args) != 1:
        raise SystemExit(USAGE)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    code, cfg = args[0], load_config()
    site_dir, site_url = cfg.get("site_dir"), cfg.get("site_url")
    if do_publish and not (site_dir and site_url):
        raise SystemExit("--publish richiede site_dir e site_url in config.json (vedi README)")

    info = wcl.report(code, f"title startTime {FIGHTS}")
    tries = attempts.best_tries(info["fights"])
    if not tries:
        raise SystemExit("nessun boss in questo report")
    loaded = [(a, kpi.load_fight(*wcl.fight_tables(code, a.id))) for a in tries]

    date = datetime.fromtimestamp(info["startTime"] / 1000).strftime("%Y-%m-%d")
    n = night.assemble(info["title"], date, loaded, cfg)
    url = f"{site_url.rstrip('/')}/{date}/" if site_url else None

    folder = ROOT / "out" / date
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in report.files(n).items():
        (folder / name).write_text(text)
    (folder / "pagella.html").write_text(page.render_html(n, icons.fetch(sorted({p.icon for p in n.players})), url))
    text = message.render(n, url)
    (folder / "messaggio.txt").write_text(text + "\n")

    if do_publish:
        publish.publish(folder, date, Path(site_dir).expanduser(), site_url)
    sys.stdout.write(text + "\n")
    logging.getLogger(__name__).warning("salvati in %s%s", folder, " e pubblicati" if do_publish else "")


if __name__ == "__main__":
    main(sys.argv)
