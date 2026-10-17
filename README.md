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

La pagina si apre direttamente nel browser da un link, ospitata su GitHub Pages (gratis). Il link è non listato (`noindex` + `robots.txt`). Su Discord e Telegram mostra un'anteprima con titolo, MVP e LVP.

Si usa lo **stesso repo** del progetto: il codice sta su `master`, le pagine in un branch separato `gh-pages` (senza cronologia in comune) che tieni in una cartella a parte. Attenzione: Pages gratis richiede un repo **pubblico**, quindi diventa pubblico anche il codice (nessun segreto: `.env` e `config.json` sono ignorati da git).

Setup, una volta sola:

```
git remote add origin https://github.com/<utente>/blazettino.git && git push -u origin master
git worktree add --orphan -b gh-pages ../blazettino-site
cd ../blazettino-site && git commit --allow-empty -m "pagine" && git push -u origin gh-pages
```

Poi su GitHub: Settings → Pages → Deploy from a branch → `gh-pages` / root, e in `config.json` (vedi sotto) `site_dir` = percorso assoluto di `../blazettino-site` e `site_url` = `https://<utente>.github.io/blazettino`.

```
python -m blazettino <codice_report> --publish    # genera, copia in site_dir/<data>/, commit e push
python -m blazettino --remove <YYYY-MM-DD>         # toglie una serata dal sito
python -m blazettino --refresh-site                # riscrive radice e archivio dalle serate già pubblicate (senza rigenerare nulla)
```

La radice del sito (`<site_url>/`) apre direttamente l'ultima serata; `<site_url>/archivio/` elenca tutte le serate (data, titolo, MVP/LVP, tag "Ultima"). Ogni pagella pubblicata ha in fondo il link "Tutte le serate".

Dopo circa un minuto il link in `messaggio.txt` è attivo. Senza `--publish` non viene toccato nessun repo e non parte nessun push. `--remove` fa smettere di funzionare il link, ma la pagina resta nella cronologia del branch `gh-pages` (che è pubblica): per cancellarla davvero serve riscrivere la cronologia con un force-push.

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
 "site_dir": "/mnt/c/projects/blazettino-site", "site_url": "https://<utente>.github.io/blazettino"}
```

- `exclude`: PG che non compaiono in pagella, podio e commenti (nemmeno negli esempi di stile).
- `site_dir`, `site_url`: cartella locale del branch `gh-pages` e suo indirizzo pubblico (servono solo per `--publish` e per il link nel messaggio).
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
