"""Memory of the raid in SQLite (data/memoria.db): who was in which boss pull and what each person took.

Collecting (--collect) fills it from every boss pull of a log, wipes included, and never calls the LLM.
The report cards only read it, to tell which mechanics a person stopped failing and which they still fail.
People are the keys of players.json: all the characters of one person count together.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from statistics import mean

from blazettino import abilities, profile, roster, wcl
from blazettino.config import ROOT

DB = ROOT / "data" / "memoria.db"
TREND_NIGHTS = 4  # nights looked at (config "trend_nights")
BETTER, WORSE = 0.5, 1.5  # tonight's hits per fight against the earlier average: below half = better, above 1.5x = worse
MAX_TREND = 3  # trend lines per person
MIN_RATE = 0.5  # hits per fight under which a mechanic counts as not taken (a stray hit is not a trend)
SCHEMA = """
create table if not exists fight(codice text, id integer, boss text, encounter integer, data text, kill integer, diff integer, primary key(codice, id));
create table if not exists presenza(codice text, id integer, persona text, personaggio text, primary key(codice, id, personaggio));
create table if not exists evento(codice text, id integer, persona text, abilita text, colpi integer, danno integer, primary key(codice, id, persona, abilita));
create table if not exists morte(codice text, id integer, persona text, secondo integer, abilita text, prima integer);
"""
ORDER = ("peggiora", "nuova", "risolta", "invariata", "migliora")
TEXT = {
    "risolta": "non la prende più (prima {prev:.1f} colpi a fight, ora {cur:.1f})",
    "migliora": "la prende meno (da {prev:.1f} a {cur:.1f} colpi a fight)",
    "peggiora": "la prende di più (da {prev:.1f} a {cur:.1f} colpi a fight)",
    "invariata": "la prende ancora come nelle serate scorse ({cur:.1f} colpi a fight)",
    "nuova": "prima non la prendeva, stasera sì ({cur:.1f} colpi a fight)",
}


def connect(path: Path = DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def classify(prev: float, cur: float) -> str:
    """Tonight against the earlier nights: '' (never taken), nuova, risolta, migliora, peggiora or invariata (the grey zone)."""
    prev, cur = (x if x >= MIN_RATE else 0 for x in (prev, cur))
    if not prev and not cur:
        return ""
    if not prev:
        return "nuova"
    if not cur:
        return "risolta"
    return "migliora" if cur <= prev * BETTER else "peggiora" if cur >= prev * WORSE else "invariata"


def record(db: sqlite3.Connection, code: str, fight: dict, date: str, present: list[str], prof: dict, book: dict) -> None:
    """One boss pull: replaces whatever was stored for it (recording twice changes nothing)."""
    who = lambda char: roster.canon(char, book)
    key = (code, fight["id"])
    taken: dict[tuple[str, str], list[int]] = {}
    for ability, a in prof["damage"].items():
        for char, v in a["players"].items():
            hits = [h for h in v["list"] if h[2] <= profile.DEAD_CUTOFF]
            if hits:
                n = taken.setdefault((who(char), ability), [0, 0])
                n[0] += len(hits)
                n[1] += sum(h[1] for h in hits)
    with db:
        for table in ("fight", "presenza", "evento", "morte"):
            db.execute(f"delete from {table} where codice=? and id=?", key)
        db.execute("insert into fight values (?,?,?,?,?,?,?)",
                   (*key, fight["name"], fight["encounter"], date, int(bool(fight["kill"])), fight["difficulty"]))
        db.executemany("insert or ignore into presenza values (?,?,?,?)", [(*key, who(c), c) for c in present])
        db.executemany("insert into evento values (?,?,?,?,?,?)", [(*key, p, a, n, d) for (p, a), (n, d) in taken.items()])
        db.executemany("insert into morte values (?,?,?,?,?,?)", [(*key, who(d["player"]), d["s"], d["spell"], i) for i, d in enumerate(prof["deaths"])])


def present(code: str, fight_id: int) -> list[str]:
    """Names of the raiders who took part in a fight."""
    ids = wcl.report(code, "fights(fightIDs:[%d]){friendlyPlayers}" % fight_id)["fights"][0]["friendlyPlayers"] or []
    actors = wcl.report(code, "masterData{actors{id name}}")["masterData"]["actors"]
    names = {a["id"]: a["name"] for a in actors}
    return [names[i] for i in ids if i in names]


def collect(code: str, cfg: dict, db: sqlite3.Connection) -> int:
    """Learn the abilities and store the memory of every boss pull of a log; returns how many pulls."""
    info = wcl.report(code, "startTime fights{id name encounterID difficulty kill}")
    date = wcl.report_date(info)
    pulls = [f for f in info["fights"] if f["encounterID"]]
    for f in pulls:
        abilities.learn(code, f["id"])
        record(db, code, {**f, "encounter": f["encounterID"]}, date, present(code, f["id"]), profile.fight_profile(code, f["id"]), cfg.get("players", {}))
    return len(pulls)


def _display(spells: dict, ability: str) -> str:
    return spells.get(ability.lower(), {}).get("it") or ability


def trend_notes(db: sqlite3.Connection, person: str, encounter: int, spells: dict, date: str, nights: int = TREND_NIGHTS) -> list[str]:
    """What changed for a person on a boss over the last `nights` nights (tonight included): mechanics they stopped
    failing, still fail, fail more or less, and the same death night after night. Empty without history or if absent tonight."""
    dates = [r[0] for r in db.execute(
        "select distinct f.data from fight f join presenza p on p.codice=f.codice and p.id=f.id "
        "where f.encounter=? and p.persona=? and f.data<=? order by f.data desc limit ?", (encounter, person, date, nights))][::-1]
    if len(dates) < 2 or dates[-1] != date:
        return []
    marks = ",".join("?" * len(dates))
    args = (encounter, person, *dates)
    fights = dict(db.execute(
        f"select f.data, count(distinct f.codice || '#' || f.id) from fight f join presenza p on p.codice=f.codice and p.id=f.id "
        f"where f.encounter=? and p.persona=? and f.data in ({marks}) group by f.data", args))
    hits: dict[tuple[str, str], int] = {}
    for d, ability, n in db.execute(
            f"select f.data, e.abilita, sum(e.colpi) from evento e join fight f on f.codice=e.codice and f.id=e.id "
            f"where f.encounter=? and e.persona=? and f.data in ({marks}) group by f.data, e.abilita", args):
        hits[d, ability] = n
    found = []
    for entry in {v["en"]: v for v in spells.values() if v.get("metric") == "avoid"}.values():
        rate = lambda d: hits.get((d, entry["en"]), 0) / fights[d]
        prev, cur = mean(rate(d) for d in dates[:-1]), rate(date)
        kind = classify(prev, cur)
        if kind:
            found.append((ORDER.index(kind), f"{entry['it'] or entry['en']}: " + TEXT[kind].format(prev=prev, cur=cur)))
    died: dict[str, set[str]] = {}
    for d, ability in db.execute(
            f"select f.data, m.abilita from morte m join fight f on f.codice=m.codice and f.id=m.id "
            f"where f.encounter=? and m.persona=? and m.prima<=? and f.data in ({marks})", (encounter, person, profile.DEAD_CUTOFF, *dates)):
        died.setdefault(ability, set()).add(d)
    for ability, days in died.items():
        streak = next((i for i, d in enumerate(reversed(dates)) if d not in days), len(dates))
        if streak >= 2:
            found.append((0, f"muore sulla stessa abilità ({_display(spells, ability)}) da {streak} serate di fila"))
    return [line for _, line in sorted(found)[:MAX_TREND]]
