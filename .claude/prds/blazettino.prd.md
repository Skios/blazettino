# Il Blazettino — Pagelle sarcastiche di raid

## Problem
La gilda (raid WoW, 20 persone, molti rientrati di recente) vive un periodo di tensione: raid più complessi e più lenti, animi accesi. Le pagelle sarcastiche si fanno già a mano, saltuariamente, e piacciono, ma richiedono tempo e voglia. Senza un modo leggero per scherzare insieme, la gilda perde un rito di coesione.

## Evidence
- Pagelle manuali già prodotte e gradite (esempio di riferimento fornito dall'utente, tono: sarcasmo affettuoso su dati reali WCL).
- Meme interno "Premio Yordata" (morti sciocche) già vivo, giocato per primo dal diretto interessato.
- Efficacia sulla coesione: Assumption — needs validation via prova di qualche giorno + sondaggio.

## Users
- **Primary**: raider della gilda (solo PG, nessun dato reale) che leggono la pagella su Discord/Telegram a fine serata; il maintainer (utente) che la genera.
- **Not for**: miglioramento delle performance dei giocatori; analisi seria/competitiva; pubblico esterno alla gilda.

## Hypothesis
We believe **una pagella sarcastica semi-automatica, con voti calcolati da KPI WarcraftLogs e commenti ironici** will **dare alla gilda un rito leggero di scherzo condiviso** for **i raider**.
We'll know we're right when **dopo alcuni giorni di prova, il sondaggio "continuare?" è favorevole e le reazioni/commenti in chat sono costanti**.

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Reazioni/commenti alla pagella | TBD — baseline dopo i primi giorni | Conteggio reazioni Discord/Telegram |
| Esito sondaggio continuare/cambiare/smettere | Maggioranza "continuare" (soglia TBD) | Sondaggio dopo la prova |
| Richieste di esclusione/lamentele | 0 non gestite | Feedback diretto; esclusione per nome |
| Costo per pagella | 0 € | Stack locale/gratuito |

## Scope
**MVP** — Dato il report WCL di una serata: pagella testuale con podio (MVP e "LVP"), voto per player calcolato da formula su KPI (parse, DPS/HPS, morti con abilità/minuto, danno subìto, mitigazione, parse incrociati tra ruoli) e un commento sarcastico per ognuno. Esclusioni per nome via config. Generazione semi-automatica dei commenti con LLM a costo 0: Ollama locale e/o Gemini free tier (AI Studio), backend scelto da config. Output testo; embed HTML interattivo accettabile come evoluzione, non requisito.

**Out of scope**
- Video, avatar, voce (clonata o TTS) — milestone successiva.
- Format extra (il Pentito, regia caustica, personaggi) — da valutare dopo la prova.
- Pubblicazione automatica — canale ancora da decidere, pubblica l'utente.
- KPI complessi (taunt swap, dispel timing, posizionamento) — da valutare dopo l'MVP.
- Obiettivi di coaching/miglioramento dei giocatori.

## Delivery Milestones
| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Pagella di serata | Report WCL → pagella testuale con podio, voti da KPI, commenti sarcastici, esclusioni per nome | pending | — |
| 2 | Prova gilda | Qualche giorno di uso reale + sondaggio continuare/cambiare/smettere | pending | — |
| 3 | Pagella settimanale (martedì) | Aggregato delle 2–3 serate della settimana | pending | — |
| 4 | Pagina HTML interattiva | Embed esplorabile della pagella | pending | — |
| 5 | Notiziario video | TG settimanale letto da un personaggio (voce + avatar) | pending | — |
| 6 | Format extra | Il Pentito, regia caustica, personaggi (se il sondaggio lo giustifica) | pending | — |

## Open Questions
- [ ] Hardware noto: RTX 4060 Ti 16GB, 32GB RAM. Modello locale (classe 12–14B) da scegliere con test di qualità dell'umorismo in italiano.
- [x] Credenziali API WarcraftLogs v2: ottenute (720 punti/ora; un report di serata costa ~8 punti/fight, verificato).
- [ ] Storico dati (SQLite vs Postgres+pgvector) e RAG vettoriale: rimandati, vedi `docs/backlog.md`.
- [ ] Canale di pubblicazione (Discord/Telegram) e formato (testo, immagine, embed).
- [ ] Quali KPI "pesanti" valgono lo sforzo dopo l'MVP?
- [ ] Milestone video: modelli 3D da armory/estrattori (licenza/ToS di Blizzard, sforzo) e tool di rendering ("getartcraft" non verificato) — TBD, da validare.
- [ ] Soglie dei voti: formula e pesi da calibrare insieme su serate reali.

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Sarcasmo percepito come presa in giro pesante | Medium | High | Tono affettuoso, esclusione per nome, sondaggio di verifica, rilettura prima di pubblicare |
| Modello locale produce battute deboli/errate in italiano | High | Medium | Voti e fatti calcolati a formula, LLM solo per il commento; test di qualità precoce; revisione umana |
| Voti percepiti ingiusti (ruolo/boss) | Medium | Medium | Normalizzare per ruolo; parse/percentili invece di valori assoluti |
| Dipendenza da API WCL (limiti, formato) | Low | Medium | Cache locale dei report |
| Scope creep (video/format) prima di validare | High | Medium | Milestone gated dal sondaggio |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
