"""Unit test del tier-3 SlmAnalyzer con un worker client fittizio, senza il modello
reale: copre il contratto fail-safe (SlmAnalysisUnavailable → il chiamante torna al
tier precedente, mai un risultato inventato — ANALYSIS.md §H3/§H4). Il test end-to-end
con il modello vero (test_slm_analyzer_smoke.py) è skippato senza il GGUF, quindi questi
percorsi di errore resterebbero altrimenti non testati.
"""

from datetime import UTC, datetime

import pytest

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.domain.value_objects.threat_category import ThreatCategory
from shielddesk.infrastructure.ai.slm.protocol import SlmRequest, SlmResponse
from shielddesk.infrastructure.ai.slm_analyzer import SlmAnalysisUnavailable, SlmAnalyzer


class _StubWorkerClient:
    """Restituisce una risposta prefissata (o None) senza avviare alcun processo."""

    def __init__(self, response: SlmResponse | None) -> None:
        self._response = response

    async def analyze(self, request: SlmRequest) -> SlmResponse | None:
        return self._response


def _message() -> IncomingMessage:
    return IncomingMessage(
        message_id="msg-1",
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text="un messaggio da analizzare",
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_success_maps_response_to_analysis_result() -> None:
    response = SlmResponse(
        request_id="x", risk_level="HIGH", category="threat", confidence=0.83
    )
    analyzer = SlmAnalyzer(_StubWorkerClient(response))  # type: ignore[arg-type]

    result = await analyzer.analyze(_message())

    assert result.risk_level is RiskLevel.HIGH
    assert result.tier.value == "slm"
    assert len(result.categories) == 1
    assert result.categories[0].category is ThreatCategory.THREAT
    assert result.categories[0].confidence.value == 0.83


@pytest.mark.asyncio
async def test_category_none_yields_empty_categories() -> None:
    response = SlmResponse(request_id="x", risk_level="SAFE", category="none", confidence=0.0)
    analyzer = SlmAnalyzer(_StubWorkerClient(response))  # type: ignore[arg-type]

    result = await analyzer.analyze(_message())

    assert result.risk_level is RiskLevel.SAFE
    assert result.categories == ()


@pytest.mark.asyncio
async def test_none_response_raises_unavailable() -> None:
    analyzer = SlmAnalyzer(_StubWorkerClient(None))  # type: ignore[arg-type]

    with pytest.raises(SlmAnalysisUnavailable, match="nessuna risposta valida"):
        await analyzer.analyze(_message())


@pytest.mark.asyncio
async def test_unknown_risk_level_raises_unavailable() -> None:
    response = SlmResponse(
        request_id="x", risk_level="INESISTENTE", category="none", confidence=0.0
    )
    analyzer = SlmAnalyzer(_StubWorkerClient(response))  # type: ignore[arg-type]

    with pytest.raises(SlmAnalysisUnavailable, match="risk_level sconosciuto"):
        await analyzer.analyze(_message())


@pytest.mark.asyncio
async def test_invalid_category_raises_unavailable() -> None:
    response = SlmResponse(
        request_id="x", risk_level="MEDIUM", category="categoria-inventata", confidence=0.5
    )
    analyzer = SlmAnalyzer(_StubWorkerClient(response))  # type: ignore[arg-type]

    with pytest.raises(SlmAnalysisUnavailable, match="category/confidence"):
        await analyzer.analyze(_message())


@pytest.mark.asyncio
async def test_out_of_range_confidence_raises_unavailable() -> None:
    response = SlmResponse(
        request_id="x", risk_level="MEDIUM", category="insult", confidence=1.5
    )
    analyzer = SlmAnalyzer(_StubWorkerClient(response))  # type: ignore[arg-type]

    with pytest.raises(SlmAnalysisUnavailable, match="category/confidence"):
        await analyzer.analyze(_message())
