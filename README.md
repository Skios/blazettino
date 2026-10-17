# Il Blazettino

Pagelle sarcastiche (e, in futuro, notiziario video) dei raid della gilda *Blaze of Glory*, con voti calcolati da KPI reali di WarcraftLogs. Si fa per ridere e fare gruppo, non per bullizzare.

## Uso

```
python -m blazettino <codice_report_WCL>     # es. RaZCT7cxPbwQ4VNA
```

Per ogni boss usa il **miglior tentativo**: la kill se c'è, altrimenti il wipe che ha lasciato il boss più basso di vita. Calcola i voti per boss e per l'intera serata (media dei voti per boss), chiede i commenti all'LLM (una chiamata per boss più una per la serata, circa 5 minuti in tutto) e salva in `out/<data>/`:

- `global.md`: podio, tabella dei voti per boss e commenti dell'intera serata
- `<boss>_kill.md` / `<boss>_wipe.md`: una pagella per boss, marcata kill o wipe
- `messaggio.txt`: il commento breve da incollare in chat (podio, battute di MVP e LVP, boss, link)
- `pagella.html`: file unico e autonomo che raccoglie tutto (schede Serata e una per boss, filtri per ruolo, ordinamento, icone di spec incorporate); si può aprire, inviare o ospitare così com'è

Sui wipe WarcraftLogs non calcola i parse ("No kill no ranking!"): il voto usa la posizione del giocatore nel raid per ruolo, indicata come `pos.`. Le risposte WCL sono in cache in `cache/` (rilanciare non spende punti, ma i commenti vengono rigenerati). Le icone di spec vengono scaricate una volta dal CDN di WarcraftLogs e messe in cache; se mancano, la pagina esce senza. Se l'LLM non risponde, le pagelle escono comunque senza commenti.

## Pubblicare (link cliccabile con anteprima)

La pagina si apre direttamente nel browser da un link, ospitata su GitHub Pages (gratis, link non listato: `noindex` + `robots.txt`, nessuna indicizzazione). Su Discord e Telegram il link mostra un'anteprima con titolo, MVP e LVP.

Setup, una volta sola:

1. Crea un repo **pubblico** vuoto, es. `blazettino-site`, solo per le pagine generate (nessun segreto vi finisce: la pagina contiene nomi dei PG e statistiche).
2. Su GitHub: Settings → Pages → Deploy from a branch → `main` / `(root)`.
3. Clonalo in locale e aggiungi in `config.json` (vedi sotto) `site_dir` (percorso del clone) e `site_url` (es. `https://<utente>.github.io/blazettino-site`).

```
python -m blazettino <codice_report> --publish
```

Genera tutto, copia la pagina in `<site_dir>/<data>/index.html`, aggiorna l'indice delle serate, fa commit e push. Dopo circa un minuto il link in `messaggio.txt` è attivo. Senza `--publish` non viene toccato nessun repo e non parte nessun push.

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
{"backend": "gemini", "model": "gemini-3.8-flash", "exclude": ["NomePG"], "max_missed_fights": 1,
 "site_dir": "~/blazettino-site", "site_url": "https://<utente>.github.io/blazettino-site"}
```

- `exclude`: PG che non compaiono in pagella, podio e commenti (nemmeno negli esempi di stile).
- `site_dir`, `site_url`: repo GitHub Pages locale e suo indirizzo pubblico (servono solo per `--publish` e per il link nel messaggio).
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
