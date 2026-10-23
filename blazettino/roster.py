"""Who is who: alts count as their main and the comments know the gender (players.json, not versioned).

players.json: {"Nickname": {"gender": "m"|"f", "alts": ["AltName", ...]}}  (both keys optional)
"""
from dataclasses import replace

from blazettino import kpi


def canon(name: str, book: dict) -> str:
    """The main's nickname for a character name (an alt maps to its main, anyone else to itself)."""
    return next((main for main, info in book.items() if name in info.get("alts", ())), name)


def apply(players: list[kpi.Player], book: dict) -> list[kpi.Player]:
    """Rename alts to their main and set the gender; a main and its alt in the same fight stay separate."""
    present = {p.name for p in players}
    out = []
    for p in players:
        main = canon(p.name, book)
        name = main if main == p.name or main not in present else p.name
        out.append(replace(p, name=name, gender=book.get(name, {}).get("gender", "")))
    return out
