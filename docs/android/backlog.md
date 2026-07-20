# Backlog Android

Fase 10. Elenco strutturato del lavoro necessario per un porting Android reale, basato su
`docs/android/portable-spec.md` e `docs/android/kotlin-mapping.md`. Non è una stima di tempi
(nessuna evidenza per darne una attendibile), è un ordine di dipendenze.

## 0 — Spike (bloccante, prima di tutto il resto)

- [ ] Verificare che SQLCipher for Android apra correttamente un file `.db` generato da
  `sqlcipher3` Python (stesso formato? stessa versione di SQLCipher?).
- [ ] Verificare latenza/RAM di llama.cpp via JNI (o MLC LLM) sul modello SLM scelto in Fase 4
  (`Qwen2.5-1.5B-Instruct` Q4_K_M) su hardware Android medio.
- [ ] Verificare che ONNX Runtime Mobile carichi il modello fast path di Fase 3 senza
  riconversione, o quantificare il lavoro di conversione necessario.
- [ ] Confermare la disponibilità e i limiti pratici di `NotificationListenerService` per
  intercettare le notifiche WhatsApp su Android moderno (permessi, restrizioni Doze/battery).

## 1 — Dominio e contratti (porting diretto, basso rischio)

- [ ] Tradurre `domain/entities/`, `domain/value_objects/`, `domain/events/` in Kotlin
  `data class`/`enum class` secondo `docs/android/kotlin-mapping.md`.
- [ ] Tradurre `domain/services/hash_chain.py` e `domain/services/redaction.py`.
- [ ] Tradurre i `Protocol` di `domain/ports/` in `interface` Kotlin.
- [ ] Serializzazione `kotlinx.serialization` conforme a `docs/schemas/*.schema.json`.
- [ ] Portare `tests/vectors/*.json` in una suite Kotest/JUnit e verificare che passino
  (round-trip serializzazione, conformità schema) — stesso principio dei test Python in
  `tests/unit/application/test_json_contracts.py`.

## 2 — Infrastruttura Android-specifica

- [ ] `NotificationListenerService` come implementazione di `NotificationSource`.
- [ ] Persistenza: SQLCipher for Android come implementazione di `EvidenceRepository`
  (stessa hash chain, stesso schema di `infrastructure/persistence/sqlcipher_repository.py`).
- [ ] Key management: envelope encryption equivalente a `VaultKeyService` (Argon2id + wrap
  con AES-GCM), valutando l'uso di Android Keystore per l'ultimo livello di protezione.
- [ ] Fast path AI: ONNX Runtime Mobile (o conversione TFLite) per il classificatore di Fase 3.
- [ ] SLM: worker equivalente (llama.cpp via JNI o MLC LLM) con lo stesso protocollo di stati
  (`STARTING/READY/BUSY/UNLOADING/FAILED`) di `infrastructure/ai/slm/worker_client.py`.
- [ ] Report: generazione PDF nativa Android + stesso schema `report_v1.schema.json`.

## 3 — Presentazione (Jetpack Compose)

- [ ] ViewModel Android (`androidx.lifecycle.ViewModel`) equivalenti a
  `DashboardViewModel`/`VaultViewModel`/`ChatAnalysisViewModel` — stessa separazione MVVM,
  nessuna business logic nel ViewModel (stesso principio di `CLAUDE.md`).
  - Le tre schermate esistenti sul desktop hanno oggi un contatore/lista che il ViewModel
    Android deve poter esporre nello stesso modo agli use case applicativi.
- [ ] Navigazione a tab equivalente a `Main.qml` (Dashboard / Cassaforte / Analisi chat).

## 4 — Qualità e hardening (equivalenti Android delle Fasi 1/9 desktop)

- [ ] Test privacy equivalente a `tests/integration/test_no_network_access.py` (bloccare le
  API di rete Android nei test, verificare che il flusso completo non le tocchi).
- [ ] Audit dipendenze Android (Gradle equivalente di `pip-audit`) + SBOM.
- [ ] Firma dell'APK/AAB, policy di distribuzione (Play Store vs sideload — implica requisiti
  diversi sui permessi di `NotificationListenerService`).

## Esplicitamente fuori scope di questo backlog

- Stima di tempi/sforzo: nessuna base per darla in modo affidabile in questa sessione.
- Scelta definitiva tra llama.cpp-JNI e MLC LLM: richiede lo spike 0 prima di decidere.
- Qualunque codice Kotlin: questa fase produce solo specifiche, contratti e backlog
  (`ANALYSIS.md` §23, Fase 10), non implementazione.
