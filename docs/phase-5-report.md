# Fase 5 — Persistenza sicura: report di fine fase

Vedi `ANALYSIS.md` §M/ADR-005/ADR-006/ADR-007. Obiettivo: SQLCipher o alternativa
approvata, key storage, migrazioni, backup, hash chain.

## Changelog

- **SQLCipher verificato e adottato come default**: `sqlcipher3` ≥0.6.2 si installa
  senza compilazione (wheel autocontenuta, SQLCipher 3.51.1 incluso) — confermando la
  previsione di ADR-005 fatta in Fase 0. La cassaforte ora usa cifratura nativa
  full-file invece del fallback AES-GCM-per-riga della Fase 2.
- **`VaultKeyService`** (`infrastructure/crypto/vault_key.py`, ADR-007): envelope
  encryption — una master key casuale da 32 byte cifra davvero il database; la master
  key è "avvolta" (wrapped) due volte con AES-GCM, una con una chiave derivata dalla
  passphrase (Argon2id) e una con una chiave derivata da una **recovery key**
  generata casualmente (formato leggibile a gruppi, es. `XK3F9-7QRTL-...`, alfabeto
  senza caratteri ambigui 0/O/1/I/L, pensato per la trascrizione a mano). Lo sblocco
  funziona con l'una o l'altra; se entrambe si perdono, i dati sono irrecuperabili
  per progetto (nessuna backdoor) — coerente con la domanda residua di ANALYSIS.md §O.3.
- **`SQLCipherEvidenceRepository`** (sostituisce l'`EncryptedSqliteRepository` di Fase 2
  come default): prende la master key già risolta (32 byte), mai una passphrase
  diretta — la derivazione vive solo in `VaultKeyService`. Verifica la chiave
  all'apertura con una query di sonda (`sqlite_master`), fallisce esplicitamente se
  sbagliata invece di aprire silenziosamente un file "vuoto" corrotto.
- **Hash chain** (ADR-006, `domain/services/hash_chain.py`, puro dominio): ogni riga
  include `previous_hash` e `record_hash` (SHA-256 su payload canonico + hash
  precedente). `SQLCipherEvidenceRepository.verify_integrity()` ricalcola l'intera
  catena e rileva sia la manomissione di un record sia la rimozione silenziosa di un
  record intermedio (verificato con test dedicati per entrambi i casi).
- **Migrazioni** (`infrastructure/persistence/migrations.py`): tracciate via
  `PRAGMA user_version`, applicate idempotentemente (`apply_migrations` non fa nulla
  se lo schema è già alla versione più recente) — testato riaprendo lo stesso file due
  volte.
- **Backup** (`infrastructure/persistence/backup.py`): usa l'API di backup nativa
  SQLite/SQLCipher (`Connection.backup()`, sicura anche su un DB aperto — mai una copia
  file grezza), verifica post-copia che il conteggio righe combaci, scarta il backup se
  incompleto. Il file di backup resta cifrato con la stessa chiave.
- **Wiring nel container**: `build_container()` ora usa `vault_dir` (non più `db_path`)
  contenente `evidence.db` + `keyvault.json`. Alla prima esecuzione crea la cassaforte e
  stampa la recovery key una sola volta (sostituto minimo di una schermata di
  onboarding, non ancora costruita); alle esecuzioni successive sblocca con la
  passphrase esistente. **Fail-safe solo sulla disponibilità tecnica di SQLCipher**: se
  l'import o l'apertura falliscono per motivi di piattaforma, degrada al fallback
  AES-GCM di Fase 2 (su file separato, per non confondere i due formati). Una
  **passphrase sbagliata contro un vault già esistente non viene invece mai assorbita**:
  propaga `VaultUnlockError` e ferma l'avvio, perché mascherarla rischierebbe di
  perdere l'accesso a dati già cifrati creando un vault vuoto al suo posto.
- 57 test totali (25 nuovi): hash chain, VaultKeyService (roundtrip passphrase/recovery
  key, credenziali sbagliate), repository SQLCipher (roundtrip, niente testo in chiaro
  su disco, chiave sbagliata rifiutata, integrità della catena, migrazioni idempotenti),
  backup. `ruff` e `mypy --strict` puliti.

## Verifica manuale eseguita

Test end-to-end manuale (oltre alla suite automatica): creazione di un vault, chiusura,
riapertura con la stessa passphrase, tentativo di manomissione diretta via SQL di una
riga → `verify_integrity()` passa da `True` a `False` come atteso.

## Rischi residui

- **Nessuna UI di onboarding reale**: la recovery key viene oggi stampata su stdout al
  primo avvio, non mostrata/confermata in una schermata dedicata. Rischio concreto se
  l'output del terminale non viene salvato dall'utente — accettabile per questa fase
  (backend-focused), da correggere quando arriverà la UI di onboarding.
  **Domanda residua ancora aperta**: ANALYSIS.md §O.3 (irrecuperabilità dati confermata).
- **`EncryptedSqliteRepository` (Fase 2) non ha hash chain né migrazioni**: resta il
  fallback per quando SQLCipher non è disponibile, deliberatamente più semplice.
  Se il fallback scatta in produzione, l'integrità della catena non è verificabile —
  accettabile perché il fallback è pensato come eccezione, non norma, ma va monitorato.
- **`verify_integrity()` non è nel `EvidenceRepositoryPort`**: è un metodo aggiuntivo
  della sola implementazione SQLCipher, non parte del contratto del dominio (le
  implementazioni fake/mock/AES-GCM non lo espongono) — scelta deliberata per non
  forzare un contratto più ampio su tutte le implementazioni per una capacità nuova.
- **Nessuna UI per eseguire un backup**: il modulo `backup_database()` è pronto e
  testato, ma non ancora invocabile dall'utente tramite un bottone nella cassaforte.
- **Rotazione della passphrase non implementata**: cambiare passphrase richiederebbe
  ri-avvolgere la master key con una nuova chiave derivata — non ancora costruito.
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q                       # 57 test devono passare
uv run ruff check src tests scripts
uv run mypy src

uv run python -m shielddesk.main
# Al primo avvio: la recovery key appare nel terminale — annotarla.
# "Elabora messaggi simulati" scrive nella cassaforte SQLCipher reale
# (file .shielddesk_vault/evidence.db nella cwd).
```

## Definition of Done

- [x] Test verdi (57/57, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 6 — Integrazione Windows (listener, permessi, filtro WhatsApp,
notifiche mitigate, modalità degradate), secondo `ANALYSIS.md` §M. Richiede lo spike
Windows di §L, non ancora eseguito (questo ambiente di sviluppo è macOS): è il primo
vero blocker della roadmap, da segnalare esplicitamente prima di procedere.
