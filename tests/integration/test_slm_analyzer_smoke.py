"""Smoke test end-to-end del worker SLM reale (Qwen2.5-1.5B-Instruct GGUF).

Verifica solo che la pipeline (processo separato + grammar GBNF + parsing)
produca un AnalysisResult valido su un caso non ambiguo. Non è un benchmark di
qualità: quello richiede il dataset vero pianificato in ANALYSIS.md §K.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.infrastructure.ai.slm.worker_client import SlmWorkerClient
from shielddesk.infrastructure.ai.slm_analyzer import SlmAnalyzer, default_worker_command

_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "models"
    / "qwen2.5-1.5b-instruct-gguf"
    / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)

pytestmark = pytest.mark.skipif(
    not _MODEL_PATH.exists(),
    reason="modello SLM assente in models/ (vedi docs/phase-4-report.md per scaricarlo)",
)


@pytest.mark.asyncio
async def test_slm_analyzer_end_to_end_on_explicit_threat() -> None:
    worker_client = SlmWorkerClient(
        command=default_worker_command(_MODEL_PATH),
        startup_timeout_s=120.0,
        request_timeout_s=60.0,
    )
    analyzer = SlmAnalyzer(worker_client)
    message = IncomingMessage(
        message_id="slm-smoke-1",
        source=MessageSource.MANUAL_PASTE,
        sender="benchmark",
        text="Ti aspetto fuori da scuola e te la faccio pagare, stai attento",
        timestamp=datetime.now(UTC),
    )

    try:
        result = await analyzer.analyze(message)
    finally:
        await worker_client.unload()

    assert result.tier.value == "slm"
    assert result.risk_level.value >= 2  # almeno MEDIUM: non deve sembrare un caso SAFE
    print(f"\nSLM risk_level={result.risk_level.name} latency_ms={result.latency_ms:.0f}")
