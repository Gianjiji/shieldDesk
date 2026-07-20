"""Tier 1 (fast path): classificatore di tossicità ONNX (unitary/multilingual-toxic-xlm-roberta).

Il modello espone una sola etichetta ("toxic"): dà un segnale di rischio grezzo,
non la categoria fine (minaccia/insulto/blackmail...), che resta compito delle
regole (tier 0) e dell'SLM (tier 3, Fase 4). Le soglie qui sotto sono un punto
di partenza dichiaratamente non calibrato: la calibrazione reale richiede il
dataset di benchmark completo di ANALYSIS.md §K, non il piccolo smoke-set
italiano usato per validare la pipeline in questa fase.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.risk_level import RiskLevel

SCHEMA_VERSION = "1.0"
MODEL_ID = "unitary/multilingual-toxic-xlm-roberta"

# Soglie provvisorie, non calibrate (ANALYSIS.md §K le marca esplicitamente
# come da rivedere con un vero dataset di benchmark prima del rilascio).
_THRESHOLDS: tuple[tuple[float, RiskLevel], ...] = (
    (0.90, RiskLevel.CRITICAL),
    (0.70, RiskLevel.HIGH),
    (0.45, RiskLevel.MEDIUM),
    (0.20, RiskLevel.LOW),
)


def _risk_level_from_score(score: float) -> RiskLevel:
    for threshold, level in _THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.SAFE


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class OnnxToxicityAnalyzer:
    """Analyzer reale (non mock) basato su ONNX Runtime. CPU-only, nessuna rete a runtime."""

    def __init__(self, model_dir: Path) -> None:
        # Import posticipato: `transformers` serve solo per il tokenizer (nessun
        # backend torch/tensorflow richiesto per il solo tokenizing).
        # use_fast=False: il repo non ha un tokenizer.json, quindi la modalità
        # "fast" tenterebbe una conversione slow→fast che importa
        # sentencepiece_model_pb2 (via protobuf) — in conflitto con il pool di
        # descriptor già inizializzato da onnxruntime nello stesso processo.
        # Il tokenizer "slow" usa SentencePiece direttamente, senza protobuf.
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
            str(model_dir), use_fast=False
        )
        self._session = ort.InferenceSession(
            str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"]
        )
        self._model_version = _read_model_version(model_dir)

    async def analyze(self, message: IncomingMessage) -> AnalysisResult:
        start = time.perf_counter()
        inputs = self._tokenizer(
            message.text, return_tensors="np", truncation=True, max_length=512
        )
        onnx_inputs: dict[str, Any] = {
            name: value for name, value in inputs.items() if name in self._input_names()
        }
        outputs = self._session.run(None, onnx_inputs)
        logits = outputs[0]
        score = float(_sigmoid(logits)[0, 0])
        latency_ms = (time.perf_counter() - start) * 1000

        return AnalysisResult(
            schema_version=SCHEMA_VERSION,
            message_id=message.message_id,
            tier=AnalysisTier.FAST,
            model_id=MODEL_ID,
            model_version=self._model_version,
            prompt_version="n/a",
            timestamp=message.timestamp,
            risk_level=_risk_level_from_score(score),
            categories=(),
            latency_ms=latency_ms,
        )

    def _input_names(self) -> set[str]:
        return {inp.name for inp in self._session.get_inputs()}


def _read_model_version(model_dir: Path) -> str:
    manifest_path = model_dir / "onnx_export_commit.txt"
    if manifest_path.exists():
        return manifest_path.read_text(encoding="utf-8").strip()
    return "unknown"
