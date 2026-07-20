# Fase 3 — AI fast path: report di fine fase

Vedi `ANALYSIS.md` §K/§M. Obiettivo: sostituire il segnale finto del `MockAnalyzer` con
un classificatore ONNX reale (tier 1, fast path) e verificarlo su un piccolo set italiano.

## Changelog

- **Modello scelto**: [`unitary/multilingual-toxic-xlm-roberta`](https://huggingface.co/unitary/multilingual-toxic-xlm-roberta)
  — licenza **Apache-2.0** (verificata il 2026-07-17 sulla model card), base `xlm-roberta-base`
  (~270M parametri), supporta esplicitamente l'italiano tra le lingue di training. Espone
  **una sola etichetta** ("toxic", punteggio 0–1): niente sotto-categorie fini, coerente con
  il ruolo di tier 1 (segnale grezzo e veloce; le categorie fini restano compito di regole/SLM).
- **Conversione ONNX**: fatta con `optimum-onnx` (il pacchetto `optimum[exporters]` non esiste
  più dalla 2.x — la funzionalità di export è stata spostata in un pacchetto separato) usando
  dipendenze **effimere** (`uv run --with torch --with optimum-onnx[onnxruntime] --with
  transformers`): torch/optimum non sono mai stati aggiunti alle dipendenze del progetto.
  Script riproducibile in `scripts/convert_toxicity_model_to_onnx.py`.
- **Manifest del modello** (`product/model_manifest.json`, `scripts/generate_model_manifest.py`):
  model_id, fonte, licenza, hash SHA-256 del file `model.onnx`, data di export (ADR-011).
- **`OnnxToxicityAnalyzer`** (`infrastructure/ai/onnx_analyzer.py`): `onnxruntime` per
  l'inferenza + tokenizer **slow** di `transformers` (nessun backend torch/tensorflow a
  runtime). Mappa il punteggio di tossicità a `RiskLevel` con soglie **esplicitamente
  dichiarate non calibrate** (placeholder in attesa di un benchmark statistico vero).
- **Dipendenze runtime aggiunte**: `onnxruntime`, `transformers`, `sentencepiece`, `numpy`.
  Deviazione dal piano originale di ANALYSIS.md §K ("solo tokenizers, non transformers
  completo"): il repo del modello non pubblica un `tokenizer.json` (tokenizer "fast"), solo
  `sentencepiece.bpe.model` — usare la sola libreria `tokenizers` avrebbe richiesto
  reimplementare a mano lo schema di offset dei token speciali di XLM-R, un rischio concreto
  di introdurre un bug silenzioso (tokenizzazione sbagliata → classificazioni sbagliate con
  falsa sicurezza). `transformers` in modalità tokenizer-only non richiede torch/tensorflow.
- **Fallback fail-safe nel DI container**: `build_container()` ora prova `OnnxToxicityAnalyzer`
  e degrada esplicitamente (log di warning, mai un crash o un risultato inventato) a
  `MockAnalyzer` se il modello manca o non carica — coerente con il flusso H4 di ANALYSIS.md.
  Nuovo parametro `analyzer=` per iniettare esplicitamente un'implementazione nei test.
- **Test vector italiani** (`tests/vectors/italian_smoke_set.json`): 10 frasi scritte a mano
  per questo progetto (safe/insulto/esclusione/minaccia/ironia/gergo), **non** un dataset
  statisticamente significativo — dichiarato esplicitamente nel file e nel test.
- 25 test totali (1 nuovo: benchmark smoke-test che verifica ≥70% delle frasi entro il range
  di rischio atteso; soglia lasca perché il set è minuscolo). `ruff` e `mypy --strict` puliti.

## Bug scoperti e risolti durante lo sviluppo

1. **`optimum[exporters]` non esiste più** in `optimum` 2.x: la funzionalità di export ONNX è
   stata spostata nel pacchetto separato `optimum-onnx`. Risolto installando quest'ultimo.
2. **Conflitto protobuf tra `onnxruntime` e `sentencepiece`** (riproducibile solo sotto pytest,
   non in script standalone): quando manca un `tokenizer.json`, `AutoTokenizer.from_pretrained`
   in modalità "fast" (default) tenta una conversione slow→fast che importa
   `sentencepiece_model_pb2` via `protobuf` — in conflitto con il pool di descriptor già
   inizializzato da `onnxruntime` nello stesso processo, causando `TypeError: Couldn't build
   proto file into descriptor pool`. **Fix**: `use_fast=False` — il tokenizer "slow" usa
   SentencePiece direttamente, senza passare da protobuf. Effetto collaterale positivo: anche
   più veloce da costruire (nessun passaggio di conversione).
3. Warning innocuo "`fix_mistral_regex`" durante il caricamento del tokenizer: bug noto e
   confermato di `transformers` ([issue #42591](https://github.com/huggingface/transformers/issues/42591))
   che scatta erroneamente su tokenizer non-Mistral quando i file del tokenizer condividono la
   cartella con i file del modello — cosmetico, non influisce sulla correttezza.

## Verifica manuale eseguita

Test diretto su 4 frasi italiane fuori dal set di test automatico:

| Frase | Esito | Latenza |
|---|---|---|
| "Ci vediamo domani per il compito di matematica?" | SAFE | 15.5ms |
| "Sei proprio uno stupido idiota, nessuno ti sopporta" | CRITICAL | 16.3ms |
| "Ti ammazzo se lo dici a qualcuno" | HIGH | 12.2ms |
| "Grazie mille per l'aiuto di ieri" | SAFE | 12.0ms |

Latenza ben dentro il budget p95 <300ms di ANALYSIS.md §K (CPU, nessuna GPU).

## Rischi residui

- **Soglie di RiskLevel non calibrate**: sono un placeholder ragionevole, non il risultato di
  un benchmark statistico. Il benchmark smoke-test passa all'80% (8/10) sul set minuscolo, ma
  con N=10 questo non ha significatività statistica — va sostituito con il dataset di
  benchmark vero pianificato in ANALYSIS.md §K prima di qualunque affermazione di qualità.
- **Un solo modello, una sola etichetta**: nessuna distinzione tra minaccia/insulto/blackmail/
  autolesionismo a livello di tier 1 — quella distinzione resta a carico delle regole
  deterministiche (tier 0, non ancora implementate) e dell'SLM (tier 3, Fase 4).
- **Nessuna regola tier 0**: ANALYSIS.md §K prevede regole deterministiche che possono solo
  *alzare* il rischio prima del classificatore. Non ancora costruite; oggi solo tier 1.
- **Percorso del modello hardcoded relativo al progetto** (`models/toxic-xlm-roberta-onnx/`,
  gitignored): chi clona il repo deve eseguire lo script di conversione per avere il fast path
  reale; senza, l'app degrada automaticamente (e correttamente) al `MockAnalyzer`.
- Nessun TODO critico nascosto: il degrado a mock quando il modello manca è esplicito e loggato,
  non silenzioso.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

# se models/toxic-xlm-roberta-onnx/model.onnx non esiste ancora:
uv run --with torch --with "optimum-onnx[onnxruntime]" --with transformers \
    python scripts/convert_toxicity_model_to_onnx.py
curl -sL -o models/toxic-xlm-roberta-onnx/sentencepiece.bpe.model \
    https://huggingface.co/unitary/multilingual-toxic-xlm-roberta/resolve/main/sentencepiece.bpe.model
curl -sL -o models/toxic-xlm-roberta-onnx/tokenizer_config.json \
    https://huggingface.co/unitary/multilingual-toxic-xlm-roberta/resolve/main/tokenizer_config.json
curl -sL -o models/toxic-xlm-roberta-onnx/special_tokens_map.json \
    https://huggingface.co/unitary/multilingual-toxic-xlm-roberta/resolve/main/special_tokens_map.json
uv run python scripts/generate_model_manifest.py

uv run pytest -q            # 25 test devono passare (il benchmark si salta se manca il modello)
uv run ruff check src tests scripts
uv run mypy src

uv run python -m shielddesk.main
# "Elabora messaggi simulati" ora usa il classificatore ONNX reale, non più le
# parole chiave hardcoded del MockAnalyzer.
```

## Definition of Done

- [x] Test verdi (25/25, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 4 — SLM locale (worker process, llama-cpp-python, JSON vincolato, timeout,
unload) per i casi ambigui, secondo `ANALYSIS.md` §M. Come per la Fase 3, richiederà scegliere
e scaricare un modello (candidati con licenza pulita già identificati in ANALYSIS.md §J: Qwen3-4B
o Qwen2.5-1.5B Apache-2.0, Phi-3.5/Phi-4-mini MIT — **non** Qwen2.5-3B, licenza non commerciale).
