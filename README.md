# Il Blazettino

Pagelle sarcastiche (e, in futuro, notiziario video) dei raid della gilda *Blaze of Glory*, con voti calcolati da KPI reali di WarcraftLogs. Si fa per ridere e fare gruppo, non per bullizzare.

## Uso

```
python -m blazettino <codice_report_WCL>     # es. RaZCT7cxPbwQ4VNA: la pagella di una serata
python -m blazettino --week <codice>...       # più serate della stessa settimana: una pagella ciascuna + la settimanale
```

Il codice è la parte finale dell'indirizzo del report (`warcraftlogs.com/reports/<codice>`); non c'è autodiscover.

Per ogni boss usa il **miglior tentativo**: la kill se c'è, altrimenti il wipe che ha lasciato il boss più basso di vita. Calcola i voti per boss e per l'intera serata (media dei voti per boss), chiede i commenti all'LLM (una chiamata per boss più una per la serata, circa 5 minuti in tutto) e salva in `out/<data>/`:

- `global.md`: podio, tabella dei voti per boss e commenti dell'intera serata
- `<boss>_kill.md` / `<boss>_wipe.md`: una pagella per boss, marcata kill o wipe
- `messaggio.txt`: il commento breve da incollare in chat (podio, battute di MVP e LVP, boss, link)
- `pagella.html`: file unico e autonomo che raccoglie tutto (schede Serata e una per boss, filtri per ruolo, ordinamento, icone di spec incorporate); si può aprire, inviare o ospitare così com'è

Sui wipe WarcraftLogs non calcola i parse ("No kill no ranking!"): il voto usa la posizione del giocatore nel raid per ruolo, indicata come `pos.`. Se i punti orari di WarcraftLogs finiscono (limite 1000 all'ora) il programma aspetta il reset (fino a un giorno) e riprende da dove era, perché ogni risposta è già in cache: la pagella può uscire anche ore dopo, nessun errore. Le risposte WCL sono in cache in `cache/` (rilanciare non spende punti, ma i commenti vengono rigenerati). Le icone di spec vengono scaricate una volta dal CDN di WarcraftLogs e messe in cache; se mancano, la pagina esce senza. Se l'LLM non risponde, le pagelle escono comunque senza commenti.

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
python -m blazettino <codice> --boss <slug> --publish  # pagina del solo boss (es. ulatek, kithix-hc), separata: site_dir/<data>/<slug>/
python -m blazettino --week <codice>... --publish  # una pagella per ogni report + la settimanale (site_dir/settimana/<prima data>/)
python -m blazettino --remove <YYYY-MM-DD>         # toglie una serata dal sito (o settimana/<YYYY-MM-DD>, o <YYYY-MM-DD>/<slug> per un boss singolo)
python -m blazettino --refresh-site                # riscrive radice e archivio dalle serate già pubblicate (senza rigenerare nulla)
```

La radice del sito (`<site_url>/`) è la home: pulsante per l'ultima serata, poi l'elenco delle settimanali e delle serate (data, titolo, MVP/LVP, tag "Ultima"). Ogni pagella pubblicata ha in fondo il link "Home". La settimanale è una pagella con tutti i boss della settimana (un tab per tentativo, col giorno), voto = media dei voti per boss, un solo commento in più per giocatore; `--week` con le pagelle delle serate (rigenerate: non usarlo su una serata modificata a mano) le pubblica tutte insieme.

La pagina di un boss singolo (`--boss`) ha un solo pannello con banner kill/wipe, podio e schede, costa una sola chiamata all'LLM e non tocca la pagina della serata; compare nella home sotto "Boss singoli". Lo slug è il nome del boss minuscolo senza apostrofi e spazi (`ulatek`, `the-coiled-altar`; con più difficoltà `kithix-normal`, `kithix-hc`); se sbagli, il comando elenca quelli disponibili.

Dopo circa un minuto il link in `messaggio.txt` è attivo. Senza `--publish` non viene toccato nessun repo e non parte nessun push. `--remove` fa smettere di funzionare il link, ma la pagina resta nella cronologia del branch `gh-pages` (che è pubblica): per cancellarla davvero serve riscrivere la cronologia con un force-push.

## Setup

Solo libreria standard di Python 3.11+ (testato su 3.14), nessuna dipendenza.

`.env` (non versionato; il modello è in `.env.example`), una riga per chiave:

```
clientId: <WarcraftLogs v2 client id>
secret: <WarcraftLogs v2 client secret>
geminiKey: <Google AI Studio API key>
geminiKey2: <altra chiave, facoltativa>
```

Le chiavi `geminiKey2`, `geminiKey3`... sono di riserva: si passa alla successiva solo quando la corrente risponde 429 (quota esaurita). Attenzione: usare più account per aggirare i limiti può violare i termini di Google.

`config.json` (opzionale, non versionato):

```json
{"backend": "gemini", "model": "gemini-3.8-flash", "exclude": ["NomePG"], "max_missed_fights": 1,
 "site_dir": "/mnt/c/projects/blazettino-site", "site_url": "https://<utente>.github.io/blazettino"}
```

- `exclude`: PG che non compaiono in pagella, podio e commenti (nemmeno negli esempi di stile).
- `site_dir`, `site_url`: cartella locale del branch `gh-pages` e suo indirizzo pubblico (servono solo per `--publish` e per il link nel messaggio).
- `max_missed_fights` (default 1): chi salta più boss della serata resta in pagella ma non entra nel podio.
- `backend`: `gemini` (default) oppure `ollama` (locale, qualità inferiore: vedi `docs/backlog.md`).

## Regolare formula, tono e prompt

- **Formula del voto**: costanti in cima a `blazettino/kpi.py` (`BASE`, `PARSE_WEIGHT`, `DEATH_PENALTY`, `SURVIVOR_BONUS`, `CROSS_ROLE_*`). Quando cambia la formula o un KPI, alza `KPI_VERSION` nello stesso file: le pagine già pubblicate (che portano la versione in `<meta name="blazettino-kpi">`) escono con la scritta **OLD** in alto e la card grigia nella home dopo `python -m blazettino --refresh-site`. Le pagine senza meta contano come versione 1.
- **Fasce di tono**: `TONES` in `blazettino/comment.py`, coppie (voto minimo, tono) dall'alto in basso; ogni giocatore riceve nel prompt il tono della sua fascia. Per cambiarle senza toccare il codice, in `config.json`: `"tones": [[8.5, "esalta..."], [6.5, "..."], [0, "..."]]`.
- **Prompt**: `SYSTEM` e `STYLE_HEADER` in `comment.py`; gli esempi di stile sono in `blazettino/style_examples.txt` (ognuno con il suo voto: il modello imita quello più vicino al voto del giocatore). `"system": "..."` in `config.json` sostituisce il testo di sistema.

## Giocatori, alt e ultimo try

- **`players.json`** (non versionato, modello in `players.example.json`): per ogni nickname il `gender` (`m`/`f`, facoltativo) e gli `alts`. Un alt conta come il suo main in voti, podio, record e `exclude` (escludere il main esclude anche gli alt). Se un main e un suo alt giocano lo stesso boss restano due giocatori. Con il genere indicato i commenti usano il genere giusto; senza, restano neutri.
- **Ultimo try**: per ogni boss senza kill la pagella usa l'ultimo pull della serata (`"try": "last"`, default); con `"try": "best"` in `config.json` torna il wipe più vicino alla kill. Con una kill non cambia nulla. I dati di tutti i pull restano comunque raccolti nei file dei boss.

## Pagine sostituite e boss da MythicTrap

- **Mai sovrascrivere:** pubblicando di nuovo una pagina che esiste già (stessa serata, stesso boss, stessa settimana) quella precedente resta a `<data>-v1/` (poi `-v2`...), con la scritta OLD, e la nuova prende il suo posto. Ripubblicare la stessa identica pagina non crea copie. Le versioni vecchie non sono nella home: si aprono dall'indirizzo e si tolgono con `--remove <data>-v1`.
- **Boss per raid:** `python -m blazettino --mythictrap` legge da MythicTrap i raid indicati in `config.json` (`"raids": ["venomous-abyss"]`, default quello) e salva in `data/raids/<raid>.json` solo fatti: id, nome, etichetta di azione e fase di ogni abilità. Nei commenti le morti portano l'etichetta (per esempio `[Dodge waves]`) abbinata per id o per nome; i voti non cambiano. Se la pagina di MythicTrap cambia formato il comando si ferma con un errore chiaro.
- I difetti noti stanno in [`docs/difetti.md`](docs/difetti.md).

## Dati per boss e record

Con `--publish` ogni log scrive in `site_dir/data/bosses/<encounterID>.json` kill, tempo e tutti i tentativi (una voce per codice log e difficoltà, riscrivere lo stesso log non cambia nulla). Le etichette si ricalcolano ogni volta da tutte le kill: la prima kill mostra solo il tempo, la più veloce di sempre `NEW RECORD`, le altre il distacco (`+0:13`). Le pagine pubblicate leggono il file all'apertura, quindi un record battuto cambia anche le etichette delle serate passate. Il grafico della vita del boss tentativo per tentativo compare nel banner del boss quando ci sono almeno due pull.

```
python -m blazettino --records <codice>...   # aggiunge al file dei boss i log vecchi (nessuna pagina, nessuna chiamata all'LLM)
```

## Test

```
python -m unittest
```

## Come contribuire

Il codice è Python con sola libreria standard: niente da installare, serve solo `.env` per provare con dati veri (vedi Setup).

- **Prima i test.** Scrivi un test che fallisce (`tests/test_*.py`, `unittest`), poi il codice minimo che lo fa passare. Si parte da `python -m unittest` verde e si finisce verde. I dati reali di prova stanno in `tests/fixtures/`; `tests/helpers.py` costruisce una serata di esempio.
- **Dove mettere le cose.** `kpi.py` (dati WarcraftLogs → voti), `comment.py` (prompt e LLM), `night.py` (serata e settimana), `page.py`/`report.py`/`message.py` (output), `publish.py` (sito). I commenti vengono solo da fatti già calcolati: l'LLM non inventa numeri né decide i voti.
- **Voti e KPI.** La formula è in cima a `kpi.py` (costanti con nome). Un nuovo KPI parte da `docs/backlog.md`: va calcolato in `kpi.py`, coperto da un test sulla fixture e, se serve ai commenti, aggiunto agli "spunti" di `comment.py`.
- **Tono.** Sarcasmo affettuoso, scopo coesione di gruppo; chi non vuole comparire va in `exclude`. Lingua italiana, genere neutro nei commenti.
- **Commit** piccoli, formato `tipo: descrizione` (`feat`, `fix`, `docs`, `test`, `refactor`). Niente segreti: `.env`, `config.json`, `cache/` e `out/` sono ignorati; il repo è pubblico.
- **Dati incompleti.** Se WarcraftLogs omette un pezzo (danni, abilità della morte...), si gestisce in `kpi.py` con un test che riproduce il caso, come già fatto per giocatori senza danni o morti senza colpo letale.

## Documenti

- Requisiti: [`.claude/prds/blazettino.prd.md`](.claude/prds/blazettino.prd.md)
- Esempi di stile (la pagella scritta a mano): [`blazettino/style_examples.txt`](blazettino/style_examples.txt)
- Idee non ancora in scope: [`docs/backlog.md`](docs/backlog.md)
