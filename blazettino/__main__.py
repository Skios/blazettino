"""python -m blazettino <report_code>  ->  out/<date>/{global.md, <boss>_kill|wipe.md, pagella.html}."""
import logging
import sys
from datetime import datetime

from blazettino import attempts, icons, kpi, night, page, report, wcl
from blazettino.config import ROOT, load_config

FIGHTS = "fights{id name encounterID kill fightPercentage startTime endTime}"


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("uso: python -m blazettino <codice_report>")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    code, cfg = argv[1], load_config()

    info = wcl.report(code, f"title startTime {FIGHTS}")
    tries = attempts.best_tries(info["fights"])
    if not tries:
        raise SystemExit("nessun boss in questo report")
    loaded = [(a, kpi.load_fight(*wcl.fight_tables(code, a.id))) for a in tries]

    date = datetime.fromtimestamp(info["startTime"] / 1000).strftime("%Y-%m-%d")
    n = night.assemble(info["title"], date, loaded, cfg)

    folder = ROOT / "out" / date
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in report.files(n).items():
        (folder / name).write_text(text)
    spec_icons = icons.fetch(sorted({p.icon for p in n.players}))
    (folder / "pagella.html").write_text(page.render_html(n, spec_icons))
    sys.stdout.write(report.render_global(n))
    logging.getLogger(__name__).warning("salvati in %s", folder)


if __name__ == "__main__":
    main(sys.argv)
