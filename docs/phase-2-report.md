# Fase 2 — Vertical slice locale: report di fine fase

Flusso completo richiesto da `ANALYSIS.md` §M / prompt.md §23:

```text
messaggio simulato → normalizzazione → analisi mock → risultato →
salvataggio cifrato → visualizzazione cassaforte → report minimale
```

## Changelog

- **Crypto** (`infrastructure/crypto/`): `key_derivation.py` (Argon2id, ADR-006/007) e
  `aes_gcm.py` (cifratura/decifratura AES-GCM per singolo blob). Nessun segreto o passphrase
  hard-coded nel codice.
- **Persistenza cifrata** (`infrastructure/persistence/encrypted_sqlite_repository.py`):
  `EncryptedSqliteRepository` sostituisce il repository in-memory di Fase 1 come default;
  ogni riga SQLite contiene un blob AES-GCM con salt proprio, mai testo in chiaro. Verificato
  con un test che legge i byte grezzi del file `.db` e conferma l'assenza del contenuto originale.
  Fallback di ADR-005 in attesa della valutazione di SQLCipher in Fase 5.
- **Gestione passphrase** (`infrastructure/config/settings.py`): letta da
  `SHIELDDESK_DEV_PASSPHRASE`; se assente, ne viene generata una effimera per il solo processo
  corrente con un warning esplicito nei log (mai silenzioso). Il flusso reale di onboarding/
  recovery key (ADR-007) resta pianificato per la Fase 5.
- **DTO versionato** (`application/dto/analysis_result_v1.py`): serializzazione JSON di
  `AnalysisResult` (schema_version "1.0"), contratto condiviso in futuro con Android.
- **Pipeline** (`application/commands/process_incoming_messages.py`): drena
  `NotificationSourcePort.listen()` ed esegue `AnalyzeMessageCommand` per ogni messaggio.
  `FakeNotificationAdapter.listen()` ora consuma la coda una volta sola (semantica di stream,
  non di replay) — più fedele a un vero listener di notifiche.
- **Report minimale** (`application/commands/export_report_minimal.py`): esporta un JSON
  (`report_schema_version`, `entry_count`, `entries[]`) dalla cassaforte. Il PDF professionale
  con redazione resta pianificato per la Fase 8.
- **UI**: `Vault.qml` mostra ora la lista delle prove (livello di rischio + timestamp, non solo
  un contatore), con tre azioni: "Elabora messaggi simulati", "Aggiungi prova demo", "Esporta
  report". `VaultViewModel` orchestra tramite i tre command applicativi, senza business logic
  propria.
- Container DI aggiornato: semina di default due messaggi simulati (uno neutro, uno che il
  `MockAnalyzer` classifica HIGH per parola chiave esplicita) per rendere la vertical slice
  dimostrabile senza input manuale.
- 23 test totali (11 nuovi rispetto a Fase 1): roundtrip crypto, repository cifrato (incluso il
  test "nessun testo in chiaro su disco" e "passphrase sbagliata non decifra"), pipeline
  end-to-end, export report. `ruff` e `mypy --strict` puliti.

## Verifica end-to-end eseguita

Oltre ai test automatici, ho eseguito manualmente il flusso completo headless: elaborazione dei
due messaggi simulati di default, conferma che uno viene classificato SAFE e l'altro HIGH,
esportazione del report ed ispezione byte-per-byte del file `.db` per escludere che contenesse
in chiaro le stringhe originali ("ammazzo", "matematica").

## Rischi residui

- **`asyncio.run()` per chiamata, ora su I/O reale**: con Argon2id (SQLCipher-fallback) il costo
  della KDF (decine-centinaia di ms secondo l'hardware) blocca brevemente il thread UI a ogni
  azione. Accettabile per il volume di Fase 2; da sostituire con un event loop persistente o un
  worker thread quando arriveranno operazioni realmente lente (worker SLM, Fase 4).
- **Percorso del DB di sviluppo** (`Path.cwd() / ".shielddesk_dev.db"`) non è ancora la directory
  dati per-utente propria della piattaforma: accettabile per la vertical slice locale, da
  correggere quando la persistenza reale (Fase 5) definirà la struttura definitiva.
- **Nessuna hash chain** sulle prove ancora: prevista esplicitamente in Fase 5 (ADR-006), non
  anticipata qui per restare nello scope dichiarato della vertical slice.
- **Licenza del progetto** ancora placeholder (`ANALYSIS.md` §O.2, non risolta).
- Non ancora verificato su un display reale (solo `QT_QPA_PLATFORM=offscreen`).
- Nessun TODO critico nascosto: ogni componente mancante rispetto al flusso finale (SQLCipher
  vero, ONNX/SLM, PDF, hash chain, listener Windows) è esplicitamente rinviato a una fase futura
  già nominata in `ANALYSIS.md` §M, non taciuto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q              # 23 test devono passare
uv run ruff check src tests
uv run mypy src

# Avvio con UI reale (richiede un display):
uv run python -m shielddesk.main
# Nella tab "Cassaforte":
#  1. clic su "Elabora messaggi simulati" → compaiono 2 voci (una SAFE, una HIGH)
#  2. clic su "Aggiungi prova demo" → si aggiunge una terza voce SAFE
#  3. clic su "Esporta report" → crea report_minimale.json nella cwd

# Avvio headless (nessun display):
QT_QPA_PLATFORM=offscreen uv run python -m shielddesk.main
```

## Definition of Done

- [x] Test verdi (23/23, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 3 — AI fast path (ONNX Runtime, benchmark, output normalizzato, test
italiano), secondo `ANALYSIS.md` §M. Richiede di scaricare/importare un modello reale: da
verificare con l'utente quale modello candidato usare per il benchmark iniziale, dato il vincolo
"nessun download automatico" (§25).
