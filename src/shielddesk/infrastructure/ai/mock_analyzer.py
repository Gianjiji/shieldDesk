from datetime import UTC, datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.risk_level import RiskLevel

SCHEMA_VERSION = "1.0"


class MockAnalyzer:
    """Analyzer finto per lo sviluppo: classifica SAFE tutto tranne parole chiave ovvie.

    Non è un modello AI. Serve solo a esercitare la pipeline (Fase 1/2) prima che
    il fast path ONNX e l'SLM siano integrati (Fase 3/4).
    """

    _THREAT_KEYWORDS = ("ti ammazzo", "ti uccido", "ti picchio")

    async def analyze(self, message: IncomingMessage) -> AnalysisResult:
        lowered = message.text.lower()
        is_threat = any(keyword in lowered for keyword in self._THREAT_KEYWORDS)
        return AnalysisResult(
            schema_version=SCHEMA_VERSION,
            message_id=message.message_id,
            tier=AnalysisTier.RULES,
            model_id="mock-analyzer",
            model_version="0.1.0",
            prompt_version="n/a",
            timestamp=datetime.now(UTC),
            risk_level=RiskLevel.HIGH if is_threat else RiskLevel.SAFE,
            categories=(),
            latency_ms=0.0,
        )
