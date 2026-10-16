"""python -m blazettino <report_code>  ->  out/pagella_<date>.md (also printed)."""
import dataclasses
import logging
import sys
from datetime import datetime

from blazettino import comment, icons, kpi, page, report, wcl
from blazettino.config import ROOT, load_config


def _tag_boss(players: list[kpi.Player], boss: str) -> list[kpi.Player]:
    return [
        dataclasses.replace(p, deaths=tuple(dataclasses.replace(d, boss=boss) for d in p.deaths))
        for p in players
    ]


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("uso: python -m blazettino <codice_report>")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    code, cfg = argv[1], load_config()
    exclude = set(cfg.get("exclude", ()))

    info = wcl.report(code, "title startTime fights(killType:Kills){id name encounterID}")
    kills = [f for f in info["fights"] if f["encounterID"]]  # parses exist only for kills
    if not kills:
        raise SystemExit("nessun boss ucciso in questo report")

    fights = [_tag_boss(kpi.load_fight(*wcl.fight_tables(code, f["id"])), f["name"]) for f in kills]
    players = [p for p in kpi.merge(fights) if p.name not in exclude]
    date = datetime.fromtimestamp(info["startTime"] / 1000).strftime("%Y-%m-%d")
    names = [f["name"] for f in kills]
    notes, max_missed = comment.comments(players, cfg), cfg.get("max_missed_fights", 1)
    text = report.render(info["title"], date, names, players, notes, max_missed)
    html = page.render_html(
        info["title"], date, names, players, notes, max_missed, icons.fetch(sorted({p.icon for p in players}))
    )

    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / f"pagella_{date}.md").write_text(text)
    (out / f"pagella_{date}.html").write_text(html)
    sys.stdout.write(text)
    logging.getLogger(__name__).warning("salvate in %s (.md e .html)", out / f"pagella_{date}")


if __name__ == "__main__":
    main(sys.argv)
