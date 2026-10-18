# Backlog idee (non ancora in scope)

Idee emerse durante il PRD. Non sono requisiti: si promuovono nel PRD solo quando servono.

## Dati e memoria
- **DB di storico** (per trend, streak, gag ricorrenti, pagella settimanale). Decisione: **SQLite** per l'MVP (nessun servizio da avviare), migrazione a **Postgres** (Docker o deploy) quando servirà, soprattutto se arriva il RAG vettoriale (pgvector).
  - **Migrazioni versionate**: file `.sql` numerati con `-- migrate:up` / `-- migrate:down` (formato dbmate) + runner minimo con tabella `schema_migrations`. Niente Liquibase (richiede JVM, eccessivo qui). Con la migrazione a Postgres si può passare a dbmate (da verificare) usando gli stessi file.
  - **SQL portabile**: solo tipi e costrutti standard (niente `AUTOINCREMENT`, `PRAGMA`, funzioni data SQLite-only nelle migrazioni), così gli stessi changeset valgono su entrambi.
  - Se Postgres: serve un controllo all'avvio che DB e container siano su.
- **RAG vettoriale**: recuperare vecchi commenti, lore di gilda o frasi memorabili per lo stile. Non ora: manca un corpus. Riaprire quando c'è materiale. Attenzione al consenso se si usano chat di persone reali.
- **Callback**: memoria dei gag ("terza serata che muore sulla stessa abilità", "da 4 a 8,5 rispetto a martedì scorso").

## KPI
- KPI "pesanti" da valutare dopo l'MVP: taunt swap timing, uptime mitigazione attiva, interrupt (count/target), dispel timing, danno evitabile subìto, padding su add, uso dei raid cooldown.
- Premi speciali: MVP, LVP, "Premio Yordata" (morte sciocca: salto dalla piattaforma, teletrasporto nel frontale del boss, ecc.). Il meme nasce da Yorda, che lo gioca per primo.

- **Nuovi KPI, in ordine di costo/beneficio** (da calibrare sulle serate reali): interrupt mancati/riusciti, dispel, danno evitabile subito (per abilità), uptime sulla mitigazione attiva dei tank, uso dei cooldown di raid, tempo di presenza in combattimento (afk/late).
- **Premi di serata/settimana oltre MVP/LVP**: "Premio Yordata", più costante, più migliorato (voto vs settimana scorsa), "muro" (meno danno subito).
- **Pagelle migliori**: trend per giocatore (richiede lo storico), callback ai gag ricorrenti, confronto con la settimana precedente, voti per ruolo meglio calibrati (soglie ancora da validare), tono per boss/wipe, sezione "momento clou" (strage più grossa).
- **Qualità dei voti**: tarare i pesi sulla formula dopo il primo sondaggio; considerare ilvl e difficoltà del boss; gestire casi limite (player senza dati su un boss, cambio spec a metà serata).

## LLM
- Backend per i commenti: Ollama locale (costo 0, offline) e/o Gemini via Google AI Studio (free tier, qualità migliore in italiano). Controllare limiti e policy sui dati sulla documentazione ufficiale prima di dipendere dal free tier.
- Modelli locali candidati (4060 Ti 16GB): gemma3:12b, qwen3:14b.

## Output
- Embed HTML interattivo esplorabile (POC accettabile: solo testo).
- Canale di pubblicazione: Discord/Telegram. Le reazioni sono una metrica di successo.

## Video / voce (milestone successive)
- Notiziario settimanale (martedì, ~1,5-3 min) letto da un personaggio della gilda.
- Voce: VoiceStudio (github.com/debpalash/VoiceStudio), se i membri acconsentono, altrimenti TTS generico.
- Modelli 3D: wowextractor + armory, oppure toon stilizzato. Verificare licenza/ToS.
- Montaggio: getartcraft.com/apps (da valutare).
- Pipeline abbozzata: log → KPI → script LLM → TTS → lip-sync/avatar → montaggio.

## Format extra (dopo il sondaggio)
- Il Pentito (intervista/scena in cui il player giustifica il disastro), regia caustica, personaggi ricorrenti.

## Etica
- Tutti dentro di default; chi vuole esce per nome da config. Tono: sarcasmo affettuoso, scopo coesione.
