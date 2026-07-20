# Fase 10 — Preparazione Android: report di fine fase

Vedi `ANALYSIS.md` §M/§23. Obiettivo: specifiche portabili, test vector, contratti JSON,
mapping Python/Kotlin, backlog Android. Ultima fase della roadmap originale a 10 fasi
(Fase 6 e il packaging di Fase 9 restano rimandati, bloccati dallo spike Windows §L).

## Changelog

- **Contratti JSON formalizzati** (`docs/schemas/*.schema.json`, JSON Schema Draft 2020-12):
  - `analysis_result_v1.schema.json` — lo schema di `AnalysisResult`, prima esistente solo
    come implementazione Python (`to_dict`/`from_dict`), ora una fonte di verità
    language-agnostic.
  - `report_v1.schema.json` — lo schema del payload JSON nel bundle di report professionale
    (Fase 8), con `$ref` verso lo schema di `AnalysisResult` per le voci della timeline.
  - `model_manifest_v1.schema.json` — schema unificato per i manifest dei modelli AI.
    **Nel formalizzarlo è emersa un'inconsistenza reale**: il manifest ONNX (Fase 3) usava
    `exported_file`/`exported_at`, quello SLM (Fase 4) usava `file`/`downloaded_at` — stesso
    concetto, nomi diversi. Corretto unificando su `file`/`generated_at` in entrambi gli
    script di generazione, con rigenerazione dei manifest esistenti.
  - `scripts/generate_slm_model_manifest.py`: lo script per il manifest SLM esisteva finora
    solo come comando inline eseguito una tantum in Fase 4, non versionato — formalizzato qui
    per renderlo riproducibile.
- **Test vector cross-platform** (`tests/vectors/analysis_result_v1_examples.json`): tre esempi
  canonici (messaggio sicuro, minaccia con categoria singola, caso ambiguo multi-categoria)
  pensati per essere eseguiti sia dalla suite Python sia da una futura suite Kotlin contro gli
  stessi schema.
- **Test di conformità** (`tests/unit/application/test_json_contracts.py` + estensione a
  `test_export_professional_report.py`): verifica **con evidenza**, non per dichiarazione, che
  i DTO Python producano JSON conforme agli schema formali — sui test vector, sui manifest
  reali dei modelli scaricati in Fase 3/4, e su un report professionale generato end-to-end.
  10 test nuovi (92 totali).
- **`docs/android/portable-spec.md`**: cosa del codice attuale si porta 1:1 su Android
  (dominio, contratti JSON, hash chain, redazione) e cosa va riscritto nativo (adapter
  notifiche, persistenza, AI, UI, PDF) — con tre domande esplicitamente non ancora verificabili
  (compatibilità formato SQLCipher, latenza SLM mobile, conversione modello ONNX) che
  richiedono un futuro spike Android, analogo a quello Windows.
- **`docs/android/kotlin-mapping.md`**: tabella di mapping concreta tipo-per-tipo (value
  object, entità, eventi, port→interface, domain service, DTO) con le scelte idiomatiche
  Kotlin (`enum class` con valore esplicito, `value class` per `Confidence`,
  `kotlinx.serialization`, `Flow` al posto di `AsyncIterator`).
- **`docs/android/backlog.md`**: lavoro strutturato in 5 blocchi (spike bloccante → dominio →
  infrastruttura → presentazione → hardening), senza stime di tempo (nessuna base per darle
  in modo affidabile) e con un blocco esplicito "fuori scope" per evitare di far credere che
  qui sia stato scritto codice Kotlin (non lo è stato).

## Rischi residui

- **Nessuno spike Android eseguito**: le tre domande aperte in `portable-spec.md` (formato
  SQLCipher, latenza SLM mobile, conversione ONNX) restano non verificate — analogo esatto
  del blocco Windows, ma non ancora nemmeno tentato (nessun ambiente Android disponibile qui).
- **`kotlinx.serialization` non verificata in pratica**: il mapping è un piano ragionato, non
  testato con un vero progetto Kotlin — la canonicalizzazione JSON per l'hash chain in
  particolare (`json.dumps(..., sort_keys=True)` lato Python) è un punto delicato da validare
  byte-per-byte quando il porting inizierà davvero.
- **Nessun codice Kotlin scritto**: per esplicita decisione di scope (coerente con
  `ANALYSIS.md` §23, che per la Fase 10 elenca solo specifiche/contratti/backlog, non
  implementazione).
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q                                          # 92 test devono passare
uv run pytest tests/unit/application/test_json_contracts.py -v   # solo conformità schema
uv run ruff check src tests scripts
uv run mypy src

# Rigenerare i manifest dei modelli con lo schema unificato (se necessario):
uv run python scripts/generate_model_manifest.py
uv run python scripts/generate_slm_model_manifest.py
```

## Definition of Done

- [x] Test verdi (92/92, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

## Stato della roadmap a fine Fase 10

Tutte le fasi di `ANALYSIS.md` §23 sono state eseguite o esplicitamente rimandate con
motivazione:

| Fase | Stato |
|---|---|
| 0 — Analisi | ✅ Completa |
| 1 — Foundation | ✅ Completa |
| 2 — Vertical slice locale | ✅ Completa |
| 3 — AI fast path | ✅ Completa |
| 4 — SLM locale | ✅ Completa |
| 5 — Persistenza sicura | ✅ Completa |
| 6 — Integrazione Windows | ⏸️ Rimandata: richiede lo spike `ANALYSIS.md` §L su hardware Windows reale |
| 7 — Analisi chat | ✅ Completa |
| 8 — Report professionali | ✅ Completa |
| 9 — Hardening | ✅ Completa (packaging/firma/installer esclusi, stesso motivo della Fase 6) |
| 10 — Preparazione Android | ✅ Completa (solo specifiche/contratti/backlog, nessun codice Kotlin) |

**Lavoro rimasto, in ordine di dipendenza**: (1) spike Windows — sblocca Fase 6 e il
packaging della Fase 9; (2) `EvidenceRecord` come unità persistita (gap identificato in Fase
8) — sbloccherebbe report professionali dalla cassaforte storica, non solo da una sessione
di analisi chat corrente; (3) spike Android — sbloccherebbe l'inizio reale del porting
Kotlin secondo `docs/android/backlog.md`.
