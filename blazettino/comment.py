"""LLM commentary. The prompt carries only facts already computed by kpi.py; the model never sets grades.

Backend comes from config.json ({"backend": "gemini"|"ollama", "model": ..., "exclude": [...]}).
Any backend failure degrades to "no comments" instead of crashing the report.
"""
import json
import logging
import urllib.request
from dataclasses import dataclass
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
    "mai cattivo, mai offese personali). Per ogni giocatore scrivi un titolo in MAIUSCOLO con una battuta e 2-3 frasi di commento "
    "basate SOLO sui numeri forniti. Non inventare numeri ne' eventi. Le morti 'strage generale' sono colpa di tutti, non del singolo. "
    "Il voto e' gia' deciso: non cambiarlo ne' discuterlo. "
    "Il genere dei giocatori e' ignoto: evita participi e aggettivi di genere riferiti a loro (usa il nome, forme impersonali o neutre)."
)
EXAMPLES = (
    "Esempi di stile (titolo - commento):\n"
    "PAPA FRANCESCO IN TRANCE - Top healer indiscusso con 203.73M di cure (338.1k HPS, parse 77). Si carica sulle spalle le barre "
    "della vita di 20 persone con la forza della fede e non muore MAI (0 morti).\n"
    "TURISTA PER CASO - 118.97M di cure (197.4k HPS, parse 9) e appena 1.41M di danni. In compenso incassa 48.37M di schiaffi, "
    "il piu' picchiato tra gli healer. E' entrato in raid a fare il picnic tra gli alberi con una sola mano sulla tastiera."
)
FORMAT = (
    'Rispondi SOLO con un oggetto JSON: {"Nome": {"titolo": "TITOLO", "commento": "testo"}}, '
    "una chiave per ogni giocatore elencato, con il nome identico a quello dei dati."
)


@dataclass(frozen=True)
class Comment:
    title: str
    text: str


def _mmss(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def facts(p: kpi.Player) -> str:
    deaths = "nessuna" if not p.deaths else "; ".join(
        f"{_mmss(d.time_s)} {d.ability} ({'strage generale' if d.mass else 'evitabile'})" for d in p.deaths
    )
    return (
        f"{p.name} ({p.spec} {p.cls}, ruolo {p.role}, iLvl {p.ilvl}) - Voto {kpi.grade(p)}. "
        f"Danni {p.damage / 1e6:.2f}M ({p.dps / 1e3:.1f}k DPS, parse {p.dps_parse}), "
        f"cure {p.healing / 1e6:.2f}M ({p.hps / 1e3:.1f}k HPS, parse cure {p.hps_parse}), "
        f"danni subiti {p.taken / 1e6:.2f}M. Morti: {deaths}."
    )


def build_prompt(players: Iterable[kpi.Player], exclude: Iterable[str] = ()) -> str:
    skip = set(exclude)
    lines = [facts(p) for p in players if p.name not in skip]
    return "\n\n".join([SYSTEM, EXAMPLES, "Dati:\n" + "\n".join(lines), FORMAT])


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
