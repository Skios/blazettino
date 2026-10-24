# Difetti noti e da rivedere

Elenco tenuto durante lo sviluppo, da rivedere alla fine (Fase 6). Ogni voce: cosa, dove, effetto, cosa servirebbe.
Aggiungere in fondo, spuntare quando risolto o scartato (con il motivo).

- [ ] **D1 · Kill dello stesso giorno ordinate per codice.** `bosses.labels` ordina per (data, codice del log): due kill dello stesso boss nella stessa data danno un NEW RECORD arbitrario. Serve l'orario di inizio del log nei file dei boss.
- [ ] **D2 · Esempi di stile non filtrati per fascia.** Il codice manda tutti gli esempi; è il prompt a chiedere di imitare quello con il voto più vicino. Per filtrarli servono i voti letti da `style_examples.txt`.
- [ ] **D3 · "Ultimo try" non riduce le chiamate a Gemini.** Resta una chiamata per boss più una per la serata. Se l'obiettivo è risparmiare token serve un'altra scelta (per esempio solo la chiamata della serata).
- [ ] **D4 · Etichette MythicTrap su 15 morti su 35.** Gli id delle abilità coincidono solo in 3 casi su 35 (la guida elenca il lancio, il log il danno); per nome 15 su 35. Mancano i danni con nome diverso (per esempio "Voidweave", "Digestive Juices" di Kith'ix). Serve una tabella di sinonimi o l'id dell'effetto.
- [ ] **D5 · Le etichette non cambiano i voti.** Le morti "evitabili" restano quelle non di massa; usare le etichette per decidere cosa è evitabile cambia la formula (versione KPI 2, pagine vecchie OLD).
- [ ] **D6 · Permesso per MythicTrap/Warcraft Logs non chiesto.** Il repo pubblico contiene `data/raids/*.json` con nome, id, etichetta di azione e fase di ogni abilità (nessun testo della guida). Va chiesto il permesso o tolto il file dal repo.
- [ ] **D7 · Il codice del log cambia i file dei boss, non ci sono migrazioni.** Se cambia lo schema di `data/bosses/*.json` i file già pubblicati vanno riscritti a mano (`--records` li rigenera dai log).
- [ ] **D8 · `out/` locale viene ancora sovrascritto.** Solo le pagine pubblicate si conservano come `-vN`; la cartella `out/<data>` si riscrive a ogni generazione.
- [ ] **D9 · Le versioni vecchie non sono raggiungibili dalla home.** Una pagina sostituita resta a `<data>-v1/` (e `<data>/<boss>-v1/`), senza link: serve l'indirizzo.
- [ ] **D10 · Titolo "Zona Sconosciuta" nella serata del 22/10.** Viene dal titolo WarcraftLogs; la pagina pubblicata non è stata ritoccata.
- [ ] **D11 · Il record in pagina si vede solo online.** Il segnaposto viene riempito da uno script che legge `data/bosses/` dal sito: aprendo il file locale non compare. Non ancora visto su una serata vera.
- [ ] **D12 · Fasce di tono e prompt mai provati con Gemini dopo la modifica.** I test controllano il testo del prompt, non la qualità dei commenti.
- [ ] **D13 · Pagine vecchie senza segnaposto del record e senza grafico dei pull.** Solo le pagine generate da ora in poi li hanno.
- [x] **D14 · Attesa del limite di punti.** Verificato dal vivo il 2026-10-24: oltre i 1000 punti WarcraftLogs risponde HTTP 429 (`Too many requests from this IP address.`) con l'header `retry-after` in secondi; anche la query `rateLimitData` viene rifiutata, quindi `wcl.gql` ora usa quell'header. Resta non visto un ciclo completo di attesa e ripresa.
