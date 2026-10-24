"""LLM commentary. The prompt carries only facts already computed by kpi.py; the model never sets grades.

Backend comes from config.json ({"backend": "gemini"|"ollama", "model": ..., "exclude": [...]}).
Any backend failure degrades to "no comments" instead of crashing the report.
"""
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from blazettino import kpi
from blazettino.attempts import Attempt
from blazettino.config import env_prefix

log = logging.getLogger(__name__)

DEFAULTS = {"backend": "gemini", "model": "gemini-3.8-flash"}
TIMEOUT_S = 600  # nobody is waiting for the report cards: let a slow backend take its time
RETRY_WAIT_S = (10, 30, 60)  # free tiers answer 429/503 when busy: wait and retry before giving up
TRANSIENT = (429, 503)
OLLAMA_URL = "http://localhost:11434/api/generate"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM = (
    "Sei il cronista sarcastico di una gilda di World of Warcraft (italiano, tono affettuoso: ci si prende in giro tra amici, "
    "mai cattivo, mai offese personali). Per ogni giocatore scrivi un TITOLO in MAIUSCOLO che e' gia' una battuta, e un commento di "
    "2-3 frasi basato SOLO sui numeri forniti. Il commento deve contenere almeno un paragone assurdo o un'iperbole e chiudersi con una "
    "frase secca. Gli 'Spunti' di ogni giocatore sono i fatti piu' divertenti: usali quando ci sono. I 'Fatti del fight' sono verificati (meccaniche sbagliate o evitate, interruzioni, dispel) e comprendono le tendenze rispetto alle serate scorse: quando ci sono, il commento DEVE raccontarne almeno uno con i numeri o le serate (es. 'da 6 a 11 colpi', 'per la terza serata di fila'). Chi ha smesso di sbagliare una meccanica merita un riconoscimento (anche ironico), chi la ripete va preso in giro per la ripetizione. Il TITOLO e' un nomignolo assurdo o una metafora, mai la descrizione letterale del fatto: il fatto va nel commento. Per ogni giocatore segui il 'Tono' "
    "indicato (dipende dal voto). Non inventare numeri ne' eventi. Le morti 'strage generale' "
    "sono colpa di tutti, non del singolo. Il voto e' gia' deciso: non cambiarlo ne' discuterlo. "
    "Il genere dei giocatori e' ignoto salvo dove i dati dicono 'genere m' o 'genere f': in quel caso usa il genere giusto; "
    "altrimenti evita participi, aggettivi e pronomi di genere (usa il nome o forme impersonali). "
    "Negli esempi il genere e' usato ma per i giocatori senza 'genere' NON devi copiarlo."
)
STYLE_HEADER = (
    "Esempi di stile (pagella scritta a mano dalla gilda, da imitare nel tono e nella struttura; "
    "per ogni giocatore guarda l'esempio con il voto piu' vicino al suo):"
)
# (minimum grade, tone) from the top band down; override with "tones": [[8.5, "..."], ...] in config.json
TONES = (
    (8.5, "esalta con enfasi comica, eroe del raid"),
    (6.5, "complimento con una punzecchiatura affettuosa"),
    (4.5, "ironia affettuosa, prestazione da comparsa"),
    (0.0, "presa in giro caustica ma affettuosa, sfottò pesante"),
)
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
    if p.ranked and p.other_parse >= kpi.CROSS_ROLE_THRESHOLD:
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


def _rank(p: kpi.Player, value: int, what: str) -> str:
    """'parse 56' when WarcraftLogs ranks the fight, else the inside-raid position (wipes have no ranking)."""
    return f"{what} {value}" if p.ranked else f"posizione {value}/100 nel ruolo"


def attempt_context(a: Attempt) -> str:
    if a.kill:
        return f"Boss: {a.name} - KILL in {kpi.mmss(a.seconds)}."
    return (
        f"Boss: {a.name} - WIPE (miglior tentativo: boss a {a.pct:g}% di vita dopo {kpi.mmss(a.seconds)}). "
        "Nessuna kill: niente ranking WarcraftLogs, le posizioni sono interne al raid. "
        "Su un wipe non c'e' vittoria: tono da 'quasi ce l'avevamo' o 'tanto rumore per nulla', sempre con affetto."
    )


def night_context(attempts: list[Attempt]) -> str:
    bosses = "; ".join(
        f"{a.name} ({'KILL' if a.kill else f'WIPE a {a.pct:g}%'})" for a in attempts
    )
    return (
        f"Serata completa: {bosses}. I dati sono aggregati sui boss (somme e medie) e il voto e' la media dei voti per boss: "
        "commenta l'andamento dell'intera serata, non un singolo boss."
    )


def week_context(attempts: list[Attempt], nights: int) -> str:
    kills = sum(a.kill for a in attempts)
    return (
        f"Settimana di raid: {nights} serate, {len(attempts)} boss affrontati ({kills} kill, {len(attempts) - kills} wipe). "
        "I dati sono aggregati su tutta la settimana (somme e medie) e il voto e' la media dei voti per boss: "
        "commenta l'andamento della settimana intera, non una singola serata."
    )


def tone(g: float, tones=TONES) -> str:
    """Tone of the first band whose minimum grade the grade reaches."""
    try:
        bands = sorted(((float(floor), str(t)) for floor, t in tones), reverse=True)
    except (TypeError, ValueError):
        bands = []
    if not bands:  # empty or malformed "tones" in config.json: use the built-in ones
        bands = list(TONES)
    return next((t for floor, t in bands if g >= floor), bands[-1][1])


def facts(p: kpi.Player, players: list[kpi.Player], tones=TONES) -> str:
    deaths = "nessuna" if not p.deaths else "; ".join(
        f"{d.boss + ' ' if d.boss else ''}{kpi.mmss(d.time_s)} {d.ability}{f' [{d.label}]' if d.label else ''} ({'strage generale' if d.mass else 'evitabile'})" for d in p.deaths
    )
    hints = highlights(p, players)
    return (
        f"{p.name} ({p.spec} {p.cls}, ruolo {p.role}, iLvl {p.ilvl}{f', genere {p.gender}' if p.gender else ''}) - Voto {kpi.grade(p)}. Tono: {tone(kpi.grade(p), tones)}. "
        f"Danni {p.damage / 1e6:.2f}M ({p.dps / 1e3:.1f}k DPS, {_rank(p, p.dps_parse, 'parse')}), "
        f"cure {p.healing / 1e6:.2f}M ({p.hps / 1e3:.1f}k HPS, {_rank(p, p.hps_parse, 'parse cure')}), "
        f"danni subiti {p.taken / 1e6:.2f}M. Morti: {deaths}."
        + (f" Fatti del fight da raccontare con i numeri: {'; '.join(p.notes)}." if p.notes else "")
        + (f" Spunti: {'; '.join(hints)}." if hints else "")
    )


def build_prompt(
    players: list[kpi.Player], exclude: Iterable[str] = (), context: str = "", tones=TONES, system: str = SYSTEM
) -> str:
    skip = set(exclude)
    lines = [facts(p, players, tones) for p in players if p.name not in skip]
    style = [e for e in STYLE_ENTRIES if e.split(" ", 1)[0] not in skip]  # opt-out also covers the examples
    parts = [system, STYLE_HEADER, *style, *([context] if context else []), "Dati:\n" + "\n".join(lines), FORMAT]
    return "\n\n".join(parts)


def _post(url: str, body: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    return json.load(urllib.request.urlopen(req, timeout=TIMEOUT_S))


def call_backend(prompt: str, cfg: dict) -> str:
    if cfg["backend"] == "gemini":
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json"}}
        keys = env_prefix("geminiKey")
        for i, key in enumerate(keys):
            try:
                out = _post(GEMINI_URL.format(model=cfg["model"]), body, {"x-goog-api-key": key})
                return out["candidates"][0]["content"]["parts"][-1]["text"]
            except urllib.error.HTTPError as e:
                if e.code != 429 or i == len(keys) - 1:  # only an exhausted quota moves on to the next key
                    raise
                log.warning("chiave Gemini %d esaurita (429): passo alla successiva", i + 1)
    if cfg["backend"] == "ollama":
        out = _post(OLLAMA_URL, {"model": cfg["model"], "prompt": prompt, "stream": False, "think": False, "format": "json"}, {})
        return out["response"]
    raise RuntimeError(f"backend sconosciuto: {cfg['backend']}")


def _generate_with_retry(generate: Callable[[str, dict], str], prompt: str, cfg: dict) -> str:
    for wait in RETRY_WAIT_S:
        try:
            return generate(prompt, cfg)
        except TimeoutError:
            log.warning("backend lento (nessuna risposta in %ss): riprovo tra %ss", TIMEOUT_S, wait)
            time.sleep(wait)
        except urllib.error.HTTPError as e:
            if e.code not in TRANSIENT:
                raise
            log.warning("backend occupato (HTTP %s): riprovo tra %ss", e.code, wait)
            time.sleep(wait)
    return generate(prompt, cfg)


def comments(
    players: list[kpi.Player],
    cfg: dict,
    generate: Callable[[str, dict], str] = call_backend,
    context: str = "",
) -> dict[str, Comment]:
    """Name -> Comment for every non-excluded player the model answered for; {} if the backend fails."""
    cfg = {**DEFAULTS, **cfg}
    targets = [p.name for p in players if p.name not in set(cfg.get("exclude", ()))]
    prompt = build_prompt(players, cfg.get("exclude", ()), context, cfg.get("tones", TONES), cfg.get("system", SYSTEM))
    try:
        data = json.loads(_generate_with_retry(generate, prompt, cfg))
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
