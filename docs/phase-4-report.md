# Fase 4 — SLM locale: report di fine fase

Vedi `ANALYSIS.md` §K/§M/ADR-004. Obiettivo: worker process separato per l'SLM, con
protocollo JSON vincolato, timeout, unload per inattività — per i casi ambigui del tier 1.

## Changelog

- **Modello scelto**: [`Qwen/Qwen2.5-1.5B-Instruct-GGUF`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)
  (quantizzazione Q4_K_M, ~1.06GB) — repository **ufficiale Qwen**, non una quantizzazione
  di terze parti. Licenza **Apache-2.0** (verificata il 2026-07-17), supporto italiano
  esplicito tra le 29+ lingue dichiarate. Deliberatamente il più piccolo dei candidati
  identificati in ANALYSIS.md §J (1.5B invece di 3-4B) per restare ben dentro il budget RAM
  di §K, dato che è un tier usato solo per i casi ambigui, non per ogni messaggio.
  **Nota**: Qwen2.5-**3B** è stato scartato in Fase 0 perché la sua licenza è
  "Qwen Research" (non commerciale) — questa scelta rispetta quella verifica precedente.
- **`llama-cpp-python`** 0.3.34: nessuna wheel precompilata per questa configurazione,
  compilato da sorgente (CMake + clang, supporto Metal su Apple Silicon) — riuscito senza
  intervento manuale. Manifest con hash SHA-256 del modello in
  `product/slm_model_manifest.json` (ADR-011).
- **Worker process separato** (ADR-004, `infrastructure/ai/slm/`):
  - `protocol.py` — `WorkerRequest`/`WorkerResponse` JSON-line, enum `WorkerState`
    (`UNLOADED, STARTING, READY, BUSY, UNLOADING, FAILED`). `UNLOADED` è un'aggiunta
    rispetto all'elenco di ANALYSIS.md §G, necessaria per rappresentare "nessun processo
    in esecuzione" senza sovraccaricare il significato di `FAILED`.
  - `grammar.py` — grammar **GBNF** che vincola l'output a
    `{"risk_level": ..., "category": ..., "confidence": ...}`: il modello non può produrre
    testo libero né JSON parzialmente malformato.
  - `worker_main.py` — entry point del processo figlio: carica il modello una volta,
    legge richieste da stdin, scrive risposte da stdout, una riga per messaggio; il testo
    dell'utente è sempre delimitato (`<<<MESSAGGIO>>>...<<<FINE_MESSAGGIO>>>`) e dichiarato
    esplicitamente come dato, mai istruzione (mitigazione di prompt injection, ANALYSIS.md §K).
  - `worker_client.py` — `SlmWorkerClient`, lato genitore: avvio del processo con timeout,
    invio richiesta con timeout (kill del processo se supera la soglia), unload esplicito e
    unload automatico per inattività (controllato a ogni chiamata, non con un thread separato).
    **Nessun risultato è mai inventato**: ogni percorso di fallimento restituisce `None`.
- **`SlmAnalyzer`** (`infrastructure/ai/slm_analyzer.py`): implementa `AnalyzerPort` mappando
  la risposta del worker a `AnalysisResult` (tier `SLM`). Se il worker non produce un
  risultato valido, solleva `SlmAnalysisUnavailable` (non fabbrica un `RiskLevel`): il
  chiamante deve tornare esplicitamente al tier precedente, coerente con §H3/§H4.
- **32 test totali** (8 nuovi): 6 test di lifecycle del worker con un **worker fittizio**
  (`tests/fixtures/fake_slm_worker.py`, modalità `normal/hang/no_ready/garbage/crash`) — veloci
  e deterministici, non richiedono il modello reale da 1GB; 1 smoke test end-to-end con il
  worker e il modello reali (skippato se il modello manca, come per l'ONNX in Fase 3).
  `ruff` e `mypy --strict` puliti.

## Bug scoperto e risolto durante lo sviluppo

Il test `crash` (worker che termina da solo prima di rispondere) ha fatto emergere un bug
reale in `SlmWorkerClient._kill()`: chiamare `.kill()` su un processo già terminato solleva
`ProcessLookupError` invece di essere un no-op — la libreria standard di asyncio non lo
gestisce automaticamente. **Fix**: `try/except ProcessLookupError` esplicito, con test di
regressione (`test_worker_crash_returns_none_and_sets_failed`) che lo copre.

## Verifica manuale eseguita

Smoke test end-to-end reale: messaggio italiano con minaccia velata ("Ti aspetto fuori da
scuola e te la faccio pagare, stai attento") → `MEDIUM` (categoria "threat"), **cold-start
incluso ~18s** la prima volta, più veloce nelle esecuzioni successive (cache del filesystem).
Dentro il budget di ANALYSIS.md §K ("cold-start <20s"), ma al limite: da tenere d'occhio
quando si passerà a un uso più intensivo.

## Rischi residui

- **Nessun routing tier 0→1→3 per ambiguità**: questa fase consegna l'infrastruttura SLM come
  componente autonomo, testabile e funzionante, ma **non** collega ancora il classificatore
  ONNX (tier 1) all'SLM (tier 3) tramite una soglia di confidenza — quel routing (ADR-003,
  "fascia ambigua") è deliberatamente rinviato: non è nell'elenco esplicito della Fase 4 in
  `ANALYSIS.md` §23 ("worker process; llama-cpp-python; import modello; JSON vincolato;
  timeout; unload" — tutti presenti), e costruirlo ora avrebbe anche richiesto le regole
  deterministiche del tier 0, anch'esse non ancora esistenti. Prossimo passo naturale, non
  nascosto.
- **`SlmAnalyzer` non è wired nel DI container**: dato il costo (RAM, latenza, cold-start),
  cablarlo come analyzer di default sarebbe scorretto per un tier pensato per un uso raro.
  Resta disponibile come componente standalone (vedi test end-to-end) in attesa del router.
- **Soglie/qualità del prompt non calibrate**: un solo esempio manuale verificato, non un
  benchmark. Stessa cautela già dichiarata per l'ONNX in Fase 3.
- **Percorso del modello relativo al progetto**, gitignored: senza eseguire il download,
  chi clona il repo semplicemente non ha il tier 3 disponibile (il test si salta, non fallisce).
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"

# se models/qwen2.5-1.5b-instruct-gguf/ non esiste ancora:
mkdir -p models/qwen2.5-1.5b-instruct-gguf
curl -sL -o models/qwen2.5-1.5b-instruct-gguf/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf

uv run pytest -q                       # 32 test devono passare
uv run pytest tests/unit/infrastructure/test_slm_worker_client.py -v   # solo lifecycle, veloce
uv run pytest tests/integration/test_slm_analyzer_smoke.py -v -s       # end-to-end, ~15-20s
uv run ruff check src tests scripts
uv run mypy src
```

## Definition of Done

- [x] Test verdi (32/32, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 5 — Persistenza sicura (SQLCipher o alternativa approvata, key storage,
migrazioni, backup, hash chain), secondo `ANALYSIS.md` §M. Non richiede download di modelli.
