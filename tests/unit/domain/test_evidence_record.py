from datetime import UTC, datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel


def test_evidence_record_bundles_message_and_analysis() -> None:
    message = IncomingMessage(
        message_id="msg-1",
        source=MessageSource.MANUAL_PASTE,
        sender="Mario Rossi",
        text="ciao",
        timestamp=datetime.now(UTC),
    )
    analysis = AnalysisResult(
        schema_version="1.0",
        message_id="msg-1",
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=RiskLevel.SAFE,
    )

    record = EvidenceRecord(
        evidence_id="ev-1", message=message, analysis=analysis, stored_at=datetime.now(UTC)
    )

    assert record.message.sender == "Mario Rossi"
    assert record.analysis.risk_level is RiskLevel.SAFE
    assert record.user_annotation is None


def test_evidence_record_is_immutable() -> None:
    message = IncomingMessage(
        message_id="msg-1",
        source=MessageSource.MANUAL_PASTE,
        sender="Mario Rossi",
        text="ciao",
        timestamp=datetime.now(UTC),
    )
    analysis = AnalysisResult(
        schema_version="1.0",
        message_id="msg-1",
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=RiskLevel.SAFE,
    )
    record = EvidenceRecord(
        evidence_id="ev-1", message=message, analysis=analysis, stored_at=datetime.now(UTC)
    )

    try:
        record.evidence_id = "altro"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("EvidenceRecord non dovrebbe essere modificabile")
