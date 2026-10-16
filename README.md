# Il Blazettino

Pagelle sarcastiche (e, in futuro, notiziario video) dei raid della gilda *Blaze of Glory*, con voti calcolati da KPI reali di WarcraftLogs. Si fa per ridere e fare gruppo, non per bullizzare.

## Uso

```
python -m blazettino <codice_report_WCL>     # es. RaZCT7cxPbwQ4VNA
```

Per ogni boss usa il **miglior tentativo**: la kill se c'è, altrimenti il wipe che ha lasciato il boss più basso di vita. Calcola i voti per boss e per l'intera serata (media dei voti per boss), chiede i commenti all'LLM (una chiamata per boss più una per la serata, circa 5 minuti in tutto) e salva in `out/<data>/`:

- `global.md`: podio, tabella dei voti per boss e commenti dell'intera serata
- `<boss>_kill.md` / `<boss>_wipe.md`: una pagella per boss, marcata kill o wipe
- `pagella.html`: file unico e autonomo che raccoglie tutto (schede Serata e una per boss, filtri per ruolo, ordinamento, icone di spec incorporate); si può aprire, inviare o ospitare così com'è

Sui wipe WarcraftLogs non calcola i parse ("No kill no ranking!"): il voto usa la posizione del giocatore nel raid per ruolo, indicata come `pos.`. Le risposte WCL sono in cache in `cache/` (rilanciare non spende punti, ma i commenti vengono rigenerati). Le icone di spec vengono scaricate una volta dal CDN di WarcraftLogs e messe in cache; se mancano, la pagina esce senza. Se l'LLM non risponde, le pagelle escono comunque senza commenti.

## Setup

Solo libreria standard di Python 3.11+ (testato su 3.14), nessuna dipendenza.

`.env` (non versionato), una riga per chiave:

```
clientId: <WarcraftLogs v2 client id>
secret: <WarcraftLogs v2 client secret>
geminiKey: <Google AI Studio API key>
```

`config.json` (opzionale, non versionato):

```json
{"backend": "gemini", "model": "gemini-3.8-flash", "exclude": ["NomePG"], "max_missed_fights": 1}
```

- `exclude`: PG che non compaiono in pagella, podio e commenti (nemmeno negli esempi di stile).
- `max_missed_fights` (default 1): chi salta più boss della serata resta in pagella ma non entra nel podio.
- `backend`: `gemini` (default) oppure `ollama` (locale, qualità inferiore: vedi `docs/backlog.md`).

## Test

```
python -m unittest
```

## Documenti

- Requisiti: [`.claude/prds/blazettino.prd.md`](.claude/prds/blazettino.prd.md)
- Esempi di stile (la pagella scritta a mano): [`blazettino/style_examples.txt`](blazettino/style_examples.txt)
- Idee non ancora in scope: [`docs/backlog.md`](docs/backlog.md)
