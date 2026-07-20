"""Smoke-benchmark del fast path ONNX su un piccolo set curato di frasi italiane.

ATTENZIONE: con ~10 esempi le metriche qui sotto NON sono statisticamente
significative. Servono solo a verificare che la pipeline (tokenizer + ONNX +
mappatura a RiskLevel) produca segnali sensati sull'italiano, non a certificare
la qualità del modello. Il dataset di benchmark vero è pianificato in
ANALYSIS.md §K e non esiste ancora.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.ai.onnx_analyzer import OnnxToxicityAnalyzer

_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "toxic-xlm-roberta-onnx"
_VECTORS_PATH = Path(__file__).resolve().parent.parent / "vectors" / "italian_smoke_set.json"

pytestmark = pytest.mark.skipif(
    not (_MODEL_DIR / "model.onnx").exists(),
    reason="modello ONNX assente in models/ (esegui scripts/convert_toxicity_model_to_onnx.py)",
)


@pytest.mark.asyncio
async def test_onnx_analyzer_smoke_set_within_expected_bounds() -> None:
    analyzer = OnnxToxicityAnalyzer(_MODEL_DIR)
    vectors = json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))

    results = []
    for case in vectors["cases"]:
        message = IncomingMessage(
            message_id=case["id"],
            source=MessageSource.MANUAL_PASTE,
            sender="benchmark",
            text=case["text"],
            timestamp=datetime.now(UTC),
        )
        result = await analyzer.analyze(message)
        lower = RiskLevel[case["expected_risk_at_least"]]
        upper = RiskLevel[case["expected_risk_at_most"]]
        within_bounds = lower <= result.risk_level <= upper
        results.append((case["id"], result.risk_level, within_bounds))

    within_bounds_count = sum(1 for _, _, ok in results if ok)
    report_lines = [
        f"{cid}: {level.name} ({'OK' if ok else 'FUORI RANGE'})" for cid, level, ok in results
    ]
    print("\n".join(report_lines))

    # Soglia lasca (>=70%) perché il set è minuscolo e le soglie non calibrate:
    # questo è un test di tenuta della pipeline, non di qualità del modello.
    assert within_bounds_count / len(results) >= 0.7, "\n" + "\n".join(report_lines)
