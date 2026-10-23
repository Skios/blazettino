"""One attempt per boss: the kill if there is one, otherwise the wipe that got the boss lowest."""
import re
from dataclasses import dataclass

WORST_PCT = 100.0


@dataclass(frozen=True)
class Pull:
    pct: float  # boss health left (0 on a kill)
    seconds: int
    kill: bool


@dataclass(frozen=True)
class Attempt:
    id: int
    name: str
    kill: bool
    pct: float  # boss health left (0 on a kill)
    seconds: int
    encounter: int = 0  # WarcraftLogs encounterID (0 = unknown)
    difficulty: int = 0
    code: str = ""  # report code, filled in by the caller
    pulls: tuple[Pull, ...] = ()  # every pull of this boss and difficulty in the log, in order

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower().replace("'", "")).strip("-")


DIFFICULTIES = {1: "LFR", 3: "Normal", 4: "HC", 5: "Mythic"}


def best_tries(fights: list[dict]) -> list[Attempt]:
    """Boss attempts from a WCL `fights` list (encounterID 0 = trash, ignored), in order of first pull.
    One attempt per boss and difficulty; the difficulty goes in the name only when a boss was done on several."""
    by_boss: dict[tuple[str, int | None], list[dict]] = {}
    for f in fights:
        if f["encounterID"]:
            by_boss.setdefault((f["name"], f.get("difficulty")), []).append(f)
    levels: dict[str, int] = {}
    for name, _ in by_boss:
        levels[name] = levels.get(name, 0) + 1
    out = []
    for (name, diff), tries in by_boss.items():
        kills = [f for f in tries if f["kill"]]
        best = kills[0] if kills else min(tries, key=lambda f: f["fightPercentage"] or WORST_PCT)
        label = f"{name} ({DIFFICULTIES.get(diff, diff)})" if levels[name] > 1 else name
        out.append(Attempt(
            id=best["id"], name=label, kill=bool(best["kill"]),
            pct=0.0 if best["kill"] else float(best["fightPercentage"] or WORST_PCT),
            seconds=(best["endTime"] - best["startTime"]) // 1000,
            encounter=best["encounterID"], difficulty=diff or 0,
            pulls=tuple(Pull(0.0 if f["kill"] else float(f["fightPercentage"] or WORST_PCT),
                             (f["endTime"] - f["startTime"]) // 1000, bool(f["kill"])) for f in tries),
        ))
    return out
