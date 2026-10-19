"""Shared builders: a night made of two kills (fight 21 data) and one wipe (fight 20 data)."""
import json
from pathlib import Path

from blazettino import kpi, night
from blazettino.attempts import Attempt
from blazettino.comment import Comment

FIX = Path(__file__).parent / "fixtures"

KILL_A = Attempt(1, "Boss Uno", True, 0.0, 400)
KILL_B = Attempt(2, "Boss Due", True, 0.0, 600)
WIPE_C = Attempt(3, "Boss Tre", False, 16.54, 553)


def _load(name: str, fight: int) -> dict:
    return json.loads((FIX / f"{name}_{fight}.json").read_text())


def players(fight: int) -> list[kpi.Player]:
    """fight 21 = kill with rankings, fight 20 = wipe without."""
    return kpi.load_fight(_load("summary", fight), _load("taken", fight), _load("rank_dps", fight), _load("rank_hps", fight))


def fake_comments(players, cfg, context=""):
    skip = set(cfg.get("exclude", ()))
    return {p.name: Comment(f"TITOLO {p.name.upper()}", f"Commento per {p.name}.") for p in players if p.name not in skip}


def build_night(cfg=None, tries=None, comments_fn=fake_comments, date="2026-10-15") -> night.Night:
    tries = tries or [(KILL_A, players(21)), (KILL_B, players(21)), (WIPE_C, players(20))]
    return night.assemble("The Venomous Abyss", date, tries, cfg or {}, comments_fn)


def build_boss(attempt=KILL_A, comments_fn=fake_comments, date="2026-10-15") -> night.Night:
    return night.assemble_boss("The Venomous Abyss", date, attempt, players(20 if not attempt.kill else 21), {}, comments_fn)
