"""Boss structure per raid read from MythicTrap: spell id, name, action label and phase of every ability (facts only).

The guide texts are not copied. Spell ids are the same as WarcraftLogs' ability ids, so a death is joined
to its label in code (the comments can say "morto su una cosa da schivare"); grades do not use it.
Saved in data/raids/<raid>.json, one file per raid; the raids to read are config.json "raids".
"""
import json
import re
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Callable

from blazettino import kpi
from blazettino.config import ROOT

BASE = "https://www.mythictrap.com/en"
DATA = ROOT / "data" / "raids"
DEFAULT_RAIDS = ("venomous-abyss",)
USER_AGENT = "Blazettino/1.0 (guild report cards, reads the public guide pages once)"
PAUSE_S = 1.0  # between page requests
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def get(url: str) -> str:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=30).read().decode()


def boss_slugs(raid_html: str, raid: str) -> list[str]:
    return list(dict.fromkeys(re.findall(rf'href="/en/{re.escape(raid)}/([a-z0-9-]+)"', raid_html)))


def parse_boss(html: str) -> dict:
    """{"name", "abilities": [{"spell", "name", "label", "phases"}]}; ValueError if the page format changed."""
    m = NEXT_DATA.search(html)
    try:
        boss = json.loads(m[1])["props"]["pageProps"]["boss"]
        phases = boss["bossPhases"]
        found: dict[int, dict] = {}
        for ph in phases:
            for a in ph.get("bossAbilities", []) + ph.get("bossAbilitiesWithVideos", []):
                if not a.get("spellID"):
                    continue
                item = found.setdefault(int(a["spellID"]), {"spell": int(a["spellID"]), "name": a["name"], "label": a.get("category") or "", "phases": []})
                if ph["phaseName"] not in item["phases"]:
                    item["phases"].append(ph["phaseName"])
        return {"name": boss["name"], "abilities": list(found.values())}
    except (TypeError, KeyError, ValueError) as e:
        raise ValueError(f"MythicTrap: il formato della pagina e' cambiato ({e!r})") from e


def build_raid(raid: str, fetch: Callable[[str], str] = get, pause: float = PAUSE_S) -> dict:
    """Read every boss of a raid; a boss whose page changed format stops the run with a clear error."""
    slugs = boss_slugs(fetch(f"{BASE}/{raid}"), raid)
    if not slugs:
        raise ValueError(f"MythicTrap: nessun boss trovato per il raid {raid!r}")
    bosses = {}
    for slug in slugs:
        time.sleep(pause)
        bosses[slug] = parse_boss(fetch(f"{BASE}/{raid}/{slug}"))
    return {"raid": raid, "source": "mythictrap.com", "bosses": bosses}


def save(raid: dict, folder: Path = DATA) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{raid['raid']}.json"
    path.write_text(json.dumps(raid, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def labels(folder: Path = DATA) -> dict[int | str, str]:
    """Action label ("Dodge waves", "Move out"...) by spell id and by lowercase ability name, over every saved raid.
    The id alone matched 3 deaths out of 35 on a real night (the guide lists the cast, the log the damage spell), the name 15."""
    out: dict[int | str, str] = {}
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        for boss in json.loads(path.read_text())["bosses"].values():
            for a in boss["abilities"]:
                if a["label"]:
                    out.setdefault(a["spell"], a["label"])
                    out.setdefault(a["name"].lower(), a["label"])
    return out


def tag_deaths(players: list[kpi.Player], spell_labels: dict[int | str, str]) -> list[kpi.Player]:
    """Attach the label of the killing ability to each death that has one."""
    return [
        replace(p, deaths=tuple(replace(d, label=spell_labels.get(d.spell) or spell_labels.get(d.ability.lower(), "")) for d in p.deaths)) if spell_labels else p
        for p in players
    ]
