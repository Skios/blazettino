"""One attempt per boss: the kill if there is one, otherwise the wipe that got the boss lowest."""
import re
from dataclasses import dataclass

WORST_PCT = 100.0


@dataclass(frozen=True)
class Attempt:
    id: int
    name: str
    kill: bool
    pct: float  # boss health left (0 on a kill)
    seconds: int

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower().replace("'", "")).strip("-")


def best_tries(fights: list[dict]) -> list[Attempt]:
    """Boss attempts from a WCL `fights` list (encounterID 0 = trash, ignored), in order of first pull."""
    by_boss: dict[str, list[dict]] = {}
    for f in fights:
        if f["encounterID"]:
            by_boss.setdefault(f["name"], []).append(f)
    out = []
    for name, tries in by_boss.items():
        kills = [f for f in tries if f["kill"]]
        best = kills[0] if kills else min(tries, key=lambda f: f["fightPercentage"] or WORST_PCT)
        out.append(Attempt(
            id=best["id"], name=name, kill=bool(best["kill"]),
            pct=0.0 if best["kill"] else float(best["fightPercentage"] or WORST_PCT),
            seconds=(best["endTime"] - best["startTime"]) // 1000,
        ))
    return out
