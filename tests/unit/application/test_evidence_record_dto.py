from datetime import UTC, datetime

from shielddesk.application.dto.evidence_record_v1 import from_dict, to_dict
from shielddesk.application.dto.incoming_message_v1 import (
    from_dict as message_from_dict,
)
from shielddesk.application.dto.incoming_message_v1 import (
    to_dict as message_to_dict,
)
from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel


def _make_message() -> IncomingMessage:
    return IncomingMessage(
        message_id="msg-1",
        source=MessageSource.WHATSAPP_NOTIFICATION,
        sender="Mario Rossi",
        text="ciao come stai?",
        timestamp=datetime(2026, 7, 17, 9, 15, tzinfo=UTC),
        is_truncated=False,
    )


def _make_record() -> EvidenceRecord:
    analysis = AnalysisResult(
        schema_version="1.0",
        message_id="msg-1",
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime(2026, 7, 17, 9, 15, tzinfo=UTC),
        risk_level=RiskLevel.SAFE,
    )
    return EvidenceRecord(
        evidence_id="ev-1",
        message=_make_message(),
        analysis=analysis,
        stored_at=datetime(2026, 7, 17, 9, 16, tzinfo=UTC),
        user_annotation="nota di prova",
    )


def test_incoming_message_dto_roundtrip() -> None:
    message = _make_message()

    reconstructed = message_from_dict(message_to_dict(message))

    assert reconstructed == message


def test_evidence_record_dto_roundtrip() -> None:
    record = _make_record()

    reconstructed = from_dict(to_dict(record))

    assert reconstructed == record


def test_evidence_record_to_dict_includes_message_and_analysis() -> None:
    payload = to_dict(_make_record())

    assert payload["schema_version"] == "1.0"
    assert payload["message"]["sender"] == "Mario Rossi"
    assert payload["analysis"]["risk_level"] == 0
    assert payload["user_annotation"] == "nota di prova"


def test_evidence_record_dto_handles_missing_annotation() -> None:
    payload = to_dict(_make_record())
    payload["user_annotation"] = None

    reconstructed = from_dict(payload)

    assert reconstructed.user_annotation is None
