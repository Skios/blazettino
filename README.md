# Il Blazettino

Pagelle sarcastiche (e, in futuro, notiziario video) dei raid della gilda *Blaze of Glory*, con voti calcolati da KPI reali di WarcraftLogs. Si fa per ridere e fare gruppo, non per bullizzare.

## Uso

```
python -m blazettino <codice_report_WCL>     # es. RaZCT7cxPbwQ4VNA
```

Legge i boss uccisi del report (i parse esistono solo per le kill), calcola i voti, chiede i commenti all'LLM e salva `out/pagella_<data>.md` e `out/pagella_<data>.html`. L'HTML è un file unico e autonomo (responsive, filtri per ruolo, ordinamento, icone di spec incorporate): si può aprire, inviare o ospitare così com'è. Le icone vengono scaricate una volta dal CDN di WarcraftLogs e messe in cache; se mancano, la pagina esce senza. Le risposte WCL sono in cache in `cache/` (rilanciare non spende punti).
Se l'LLM non risponde la pagella esce comunque, senza commenti.

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
