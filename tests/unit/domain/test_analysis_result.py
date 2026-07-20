from datetime import UTC, datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.value_objects.risk_level import RiskLevel


def test_analysis_result_is_immutable() -> None:
    result = AnalysisResult(
        schema_version="1.0",
        message_id="msg-1",
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=RiskLevel.SAFE,
    )

    assert result.risk_level is RiskLevel.SAFE
    try:
        result.risk_level = RiskLevel.HIGH  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("AnalysisResult non dovrebbe essere modificabile")
