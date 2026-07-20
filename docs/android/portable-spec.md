# Specifiche portabili — cosa si porta su Android e cosa no

Fase 10 (`ANALYSIS.md` §M/§23). Riferimento per un futuro porting Kotlin/Jetpack Compose,
basato sullo stato reale del codice a fine Fase 9, non su un piano teorico.

## Principio

Il porting Android **non traduce l'intera codebase**, solo il dominio e i contratti. Tutto
ciò che nel progetto Python vive in `infrastructure/` o `presentation/` è per costruzione
specifico della piattaforma (Qt, ONNX Runtime desktop, llama-cpp-python, SQLCipher-Python,
WinRT) e va **riscritto**, non tradotto riga per riga — Android ha le sue controparti native
(vedi `docs/android/backlog.md`).

## Cosa si porta 1:1 (dominio + contratti)

| Livello | Contenuto | Perché è portabile |
|---|---|---|
| `domain/entities/` | `IncomingMessage`, `AnalysisResult` (+ `AnalysisTier`, `CategoryScore`) | Nessun import di libreria esterna: solo `dataclasses`, `datetime`, `enum` |
| `domain/value_objects/` | `RiskLevel`, `ThreatCategory`, `Confidence`, `MessageSource` | Idem — value object puri con validazione minima |
| `domain/events/` | `MessageReceived`, `AnalysisCompleted`, `HighRiskDetected`, `ModelFailed` | Eventi di dominio, nessuna dipendenza da infrastruttura |
| `domain/services/hash_chain.py` | `compute_record_hash`, `verify_chain`, `GENESIS_HASH` | Solo `hashlib`, algoritmo deterministico — stesso output su qualunque piattaforma |
| `domain/services/redaction.py` | `RedactionService` | Logica pura di pseudonimizzazione, nessuna I/O |
| `domain/ports/*.py` | `NotificationSourcePort`, `AnalyzerPort`, `EvidenceRepositoryPort`, `ClockPort` | Come `Protocol` Python diventano `interface` Kotlin: il *contratto* si porta, le implementazioni no |
| `docs/schemas/*.schema.json` | Contratti JSON (`AnalysisResult`, report, model manifest) | Language-agnostic per costruzione: la stessa fonte di verità per entrambe le piattaforme |
| `tests/vectors/*.json` | Test vector | Da eseguire contro **entrambe** le implementazioni (Python e Kotlin) per garantire risultati identici |

## Cosa NON si porta (da riscrivere nativo)

| Componente Python | Motivo | Equivalente Android |
|---|---|---|
| `infrastructure/notifications/fake_adapter.py` + (futuro) `WindowsNotificationAdapter` | Specifico WinRT/Windows | `NotificationListenerService` (Android nativo, già più maturo del desktop — vedi ANALYSIS.md §C) |
| `infrastructure/persistence/sqlcipher_repository.py` (Python `sqlcipher3`) | Binding Python-specifico | SQLCipher for Android (libreria nativa, stesso formato file — compatibilità cross-platform del *dato*, non del codice) |
| `infrastructure/ai/onnx_analyzer.py` (ONNX Runtime + `transformers` tokenizer Python) | Binding Python | ONNX Runtime Mobile o TFLite (stesso file `.onnx`, tokenizer da reimplementare o via ONNX Runtime Extensions) |
| `infrastructure/ai/slm/` (llama-cpp-python, worker process) | Binding Python + IPC via subprocess | llama.cpp via JNI, o MLC LLM (ANALYSIS.md §4.2 già indicava MLC LLM per Android) |
| `presentation/` (PySide6/QML) | Framework UI desktop | Jetpack Compose (già scelto in ANALYSIS.md come riferimento architetturale MVVM) |
| `infrastructure/reporting/pdf_report.py` (ReportLab) | Libreria Python | Libreria PDF Android nativa (es. `PdfDocument` di Android SDK, o iText) |
| `infrastructure/crypto/vault_key.py` | Usa `argon2-cffi`/`cryptography` Python | Stesso *algoritmo* (Argon2id + AES-GCM), libreria Android nativa (es. `libsodium-jni`, o Android Keystore per l'unwrap finale) |

## Vincoli di compatibilità da rispettare nel porting

1. **Hash chain**: `compute_record_hash` deve produrre lo stesso hash SHA-256 dato lo stesso
   `previous_hash` + payload canonico — l'algoritmo di canonicalizzazione JSON (chiavi
   ordinate, nessuno spazio extra) va replicato esattamente in Kotlin (`kotlinx.serialization`
   con `explicitNulls=false` e chiavi ordinate, o serializzazione manuale).
2. **Schema `AnalysisResult`**: `risk_level` è un intero 0-4 (non una stringa), `categories`
   è sempre un array (mai `null`, può essere vuoto), `timestamp` è ISO 8601 con offset.
3. **Manifest dei modelli**: stesso schema (`docs/schemas/model_manifest_v1.schema.json`) per
   verificare l'hash SHA-256 dei modelli anche su Android, prima di caricarli.
4. **Nessuna rete**: il vincolo "zero rete in runtime" (ANALYSIS.md §25) vale identico su
   Android — nessuna eccezione per il fatto di essere una piattaforma mobile.

## Cosa NON è ancora deciso (bloccante per iniziare il porting reale)

- Se il modello ONNX del fast path (Fase 3) va ri-quantizzato/convertito per mobile (dimensione,
  formato) — non verificato.
- Se llama.cpp via JNI raggiunge latenze accettabili su hardware mobile medio (il budget di
  ANALYSIS.md §K era tarato su CPU desktop) — richiede uno spike dedicato, non fatto in questa fase.
- Se SQLCipher for Android produce file `.db` byte-compatibili con quelli generati da
  `sqlcipher3` Python (stesso formato SQLCipher, ma da verificare in pratica) — non testato.

Queste tre domande sono il primo lavoro di uno spike Android, analogo allo spike Windows di
`ANALYSIS.md` §L — non eseguibile in questa sessione (nessun ambiente Android disponibile).
