"""LLM commentary. The prompt carries only facts already computed by kpi.py; the model never sets grades.

Backend comes from config.json ({"backend": "gemini"|"ollama", "model": ..., "exclude": [...]}).
Any backend failure degrades to "no comments" instead of crashing the report.
"""
import json
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from blazettino import kpi
from blazettino.config import env

log = logging.getLogger(__name__)

DEFAULTS = {"backend": "gemini", "model": "gemini-3.8-flash"}
TIMEOUT_S = 300
OLLAMA_URL = "http://localhost:11434/api/generate"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "Sei il cronista sarcastico di una gilda di World of Warcraft (italiano, tono affettuoso: ci si prende in giro tra amici, "
    "mai cattivo, mai offese personali). Per ogni giocatore scrivi un TITOLO in MAIUSCOLO che e' gia' una battuta, e un commento di "
    "2-3 frasi basato SOLO sui numeri forniti. Il commento deve contenere almeno un paragone assurdo o un'iperbole e chiudersi con una "
    "frase secca. Gli 'Spunti' di ogni giocatore sono i fatti piu' divertenti: usali quando ci sono. Piu' il voto e' basso, piu' sei "
    "caustico (sempre con affetto); con voti alti esalta con enfasi comica. Non inventare numeri ne' eventi. Le morti 'strage generale' "
    "sono colpa di tutti, non del singolo. Il voto e' gia' deciso: non cambiarlo ne' discuterlo. "
    "Il genere dei giocatori e' ignoto: evita participi, aggettivi e pronomi di genere riferiti a loro (usa il nome o forme impersonali); "
    "negli esempi il genere e' usato ma tu NON devi copiarlo."
)
STYLE_HEADER = "Esempi di stile (pagella scritta a mano dalla gilda, da imitare nel tono e nella struttura):"
STYLE_ENTRIES = Path(__file__).with_name("style_examples.txt").read_text().strip().split("\n\n")
FORMAT = (
    'Rispondi SOLO con un oggetto JSON: {"Nome": {"titolo": "TITOLO", "commento": "testo"}}, '
    "una chiave per ogni giocatore elencato, con il nome identico a quello dei dati."
)


@dataclass(frozen=True)
class Comment:
    title: str
    text: str


ROLE_LABEL = {"tank": "tank", "healer": "healer", "dps": "DPS"}
FEW_SURVIVORS_SHARE = 0.2  # "one of the only N who never died" when at most this share of the raid


def highlights(p: kpi.Player, players: list[kpi.Player]) -> list[str]:
    """Funniest verifiable facts about p relative to the raid (the 'spunti' the model builds jokes on)."""
    out = []
    label = ROLE_LABEL[p.role]
    mates = [q for q in players if q.role == p.role]
    alive = [q for q in players if not q.deaths]
    if not p.deaths and len(alive) <= max(3, int(len(players) * FEW_SURVIVORS_SHARE)):
        out.append(f"uno dei soli {len(alive)} giocatori a non morire mai")
    if p.other_parse >= kpi.CROSS_ROLE_THRESHOLD:
        side = "danni" if p.role == "healer" else "cure"
        out.append(f"parse {p.other_parse} nei {side} pur essendo {label} (non e' il suo ruolo)" if side == "danni"
                   else f"parse {p.other_parse} nelle {side} pur essendo {label} (non e' il suo ruolo)")
    if p.role != "tank" and len(mates) > 1 and max(mates, key=lambda q: q.taken) is p:
        out.append(f"il piu' colpito tra i {label}")
    metric, what = (lambda q: q.healing, "cure") if p.role == "healer" else (lambda q: q.damage, "danni")
    if p.role != "tank" and len(mates) > 1:
        if max(mates, key=metric) is p:
            out.append(f"primo per {what} tra i {label}")
        if min(mates, key=metric) is p:
            out.append(f"ultimo per {what} tra i {label}")
    repeated = {d.ability for d in p.deaths if not d.mass and sum(x.ability == d.ability and not x.mass for x in p.deaths) > 1}
    out += [f"morto piu' volte sulla stessa abilita' evitabile ({a})" for a in sorted(repeated)]
    return out


def facts(p: kpi.Player, players: list[kpi.Player]) -> str:
    deaths = "nessuna" if not p.deaths else "; ".join(
        f"{d.boss + ' ' if d.boss else ''}{kpi.mmss(d.time_s)} {d.ability} ({'strage generale' if d.mass else 'evitabile'})" for d in p.deaths
    )
    hints = highlights(p, players)
    return (
        f"{p.name} ({p.spec} {p.cls}, ruolo {p.role}, iLvl {p.ilvl}) - Voto {kpi.grade(p)}. "
        f"Danni {p.damage / 1e6:.2f}M ({p.dps / 1e3:.1f}k DPS, parse {p.dps_parse}), "
        f"cure {p.healing / 1e6:.2f}M ({p.hps / 1e3:.1f}k HPS, parse cure {p.hps_parse}), "
        f"danni subiti {p.taken / 1e6:.2f}M. Morti: {deaths}."
        + (f" Spunti: {'; '.join(hints)}." if hints else "")
    )


def build_prompt(players: list[kpi.Player], exclude: Iterable[str] = ()) -> str:
    skip = set(exclude)
    lines = [facts(p, players) for p in players if p.name not in skip]
    style = [e for e in STYLE_ENTRIES if e.split(" ", 1)[0] not in skip]  # opt-out also covers the examples
    return "\n\n".join([SYSTEM, STYLE_HEADER, *style, "Dati:\n" + "\n".join(lines), FORMAT])


def _post(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    return json.load(urllib.request.urlopen(req, timeout=TIMEOUT_S))


def call_backend(prompt: str, cfg: dict) -> str:
    if cfg["backend"] == "gemini":
        out = _post(
            GEMINI_URL.format(model=cfg["model"]),
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}},
            {"x-goog-api-key": env("geminiKey")["geminiKey"]},
        )
        return out["candidates"][0]["content"]["parts"][-1]["text"]
    if cfg["backend"] == "ollama":
        out = _post(OLLAMA_URL, {"model": cfg["model"], "prompt": prompt, "stream": False, "think": False, "format": "json"}, {})
        return out["response"]
    raise RuntimeError(f"backend sconosciuto: {cfg['backend']}")


def comments(
    players: list[kpi.Player], cfg: dict, generate: Callable[[str, dict], str] = call_backend
) -> dict[str, Comment]:
    """Name -> Comment for every non-excluded player the model answered for; {} if the backend fails."""
    cfg = {**DEFAULTS, **cfg}
    targets = [p.name for p in players if p.name not in set(cfg.get("exclude", ()))]
    try:
        data = json.loads(generate(build_prompt(players, cfg.get("exclude", ())), cfg))
        if not isinstance(data, dict):
            raise ValueError("risposta JSON non è un oggetto")
    except (OSError, ValueError, KeyError, RuntimeError) as e:
        log.warning("commenti non disponibili (%s): la pagella esce senza", e)
        return {}
    return {
        n: Comment(str(v["titolo"]), str(v["commento"]))
        for n, v in data.items()
        if n in targets and isinstance(v, dict) and "titolo" in v and "commento" in v
    }
