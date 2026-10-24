# Guida: descrivere le abilità di un boss

Per ogni boss c'è un file `data/abilities/<idIncontro>.json` (per Ula'tek `3492.json`). Lo riempie WarcraftLogs, run dopo run; voi aggiungete a mano cosa significa ogni abilità. Tutto quello che scrivete a mano viene conservato.

## 1. Far imparare le abilità al programma

```
python -m blazettino --abilities <codice_report> [<altro_codice> ...]
```

Per ogni pull da boss del log il programma scarica gli eventi (restano in cache, rilanciare non costa punti) e aggiunge al file del boss le abilità lanciate dal boss e dai suoi add o che colpiscono i raid. Se il limite orario di WarcraftLogs finisce, aspetta il reset da solo e riprende. Lo stesso fight due volte non cambia nulla, più log dello stesso boss si sommano. Più log passate, più abilità (e fasi) il file conosce.

## 2. Com'è fatto il file

```json
{
 "name": "Ula'tek",
 "encounter": 3492,
 "phases": {"1": "Stage One: Fury of the Serpent Mother", "2": "..."},
 "logs": ["RaZCT7cxPbwQ4VNA#21"],
 "abilities": {
  "1286885": {
   "en": "Falling Debris",
   "it": "Macerie Cadenti",
   "metric": "avoid",
   "kind": "oneshot",
   "note": "cadono a terra: si schivano uscendo dal cerchio",
   "sources": ["Ula'tek"],
   "phases": {"1": {"casts": 0, "hits": 2, "fights": 1}, "4": {"casts": 0, "hits": 9, "fights": 1}}
  }
 }
}
```

- **Li riempie il programma** (non modificateli, vengono riscritti): `en`, `sources` (chi la usa: boss o add), `phases` (in quali fasi compare, quanti lanci `casts` e quanti colpi `hits` sui giocatori, in quanti fight), `logs`, `phases` di primo livello (nomi delle fasi).
- **Li riempite voi** (non vengono mai toccati): `it`, `metric`, `kind`, `note`. Potete aggiungere altri campi vostri.
- `en` è il nome dell'abilità nel log. `it` è il nome italiano da usare nei commenti: se è vuoto resta l'inglese. L'`id` (la chiave) è lo stesso che si vede su WarcraftLogs.

## 3. Le metriche

| `metric` | Cosa vuol dire | Cosa succede oggi |
|---|---|---|
| `avoid` | si deve schivare | si calcolano danno e colpi presi per giocatore. Chi ne prende almeno 3 volte la media degli altri entra tra gli spunti per Gemini. Le morti su questa abilità sono segnate "da schivare" |
| `interrupt` | si deve interrompere | le morti su questa abilità sono segnate "da interrompere" |
| `dispel` | si deve dispellare | come sopra |
| `soak` | si deve assorbire in gruppo | come sopra |
| `break` | si rompe solo nel modo giusto | come sopra |

Lasciate `metric` vuoto per le abilità che non vi interessano (un'abilità senza `metric` né `it` viene ignorata). Un nome di metrica sbagliato ferma il programma con un messaggio che indica il file e le metriche valide, per non misurare niente in silenzio.

## 3 bis. Quanto pesa un colpo (`kind`)

- **`wave`** (default, campo vuoto): un colpo ogni tanto va bene. Entra tra gli spunti solo se il giocatore la prende almeno 1 volta a fight e molto più degli altri; una tendenza richiede almeno 1 colpo a fight in più o in meno.
- **`oneshot`**: anche un solo colpo conta (meccanica da schivare sempre, per esempio Macerie Cadenti). Compare tra gli spunti e tra le tendenze già dal primo colpo.

In ogni caso una morte su un'abilità `avoid` resta importante e viene segnalata anche se si ripete su più serate.

## 4. La nota (`note`)

Una frase vostra che spiega l'abilità. Va a Gemini solo quando quell'abilità compare tra gli spunti di un giocatore, tra parentesi. Esempio: `"il Guscio Maligno delle uova si rompe solo sugli Spectral Coils"`. Scrivete fatti, non battute.

## 5. Regole sul danno evitabile

- Si conta il danno dopo mitigazione e assorbimenti (`amount`), come fa Wipefest.
- I colpi presi quando erano già morti più di 5 giocatori non contano (`DEAD_CUTOFF` in `blazettino/profile.py`).
- Uno spunto compare solo se il giocatore ha almeno 2 colpi e almeno 3 volte (`OUTLIER_X`) la media degli altri. Al massimo 3 spunti a testa (`MAX_NOTES`).
- Gli spunti non cambiano il voto: servono solo a rendere il commento più preciso.

## 6. Flusso consigliato

1. Dopo la serata: `python -m blazettino --abilities <codice>`.
2. Aprite `data/abilities/<id>.json` e compilate `it`, `metric`, `note` delle abilità che contano (cercate per `sources` e per fase).
3. Generate la pagella come sempre: gli spunti compaiono nei commenti.
4. Committate il file: i vostri campi restano, i prossimi log aggiungono solo conteggi.

## Cosa non fa ancora

- Misura solo `avoid`; le altre metriche etichettano le morti e il testo (difetto D16 in [`difetti.md`](difetti.md)).
- Le abilità con la stessa denominazione e id diversi (per esempio le varie "Caustic Waves") sono voci separate: compilate quella che fa il danno.
- Gli eventi sul `Environment` finiscono nel file come fonte "Environment": ignoratele se non vi servono.
