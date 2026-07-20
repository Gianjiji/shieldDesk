"""Serializzazione JSON di EvidenceRecord: è questo il payload canonico usato
per la hash chain (ADR-006) — non più il solo AnalysisResult.
"""

from datetime import datetime
from typing import Any

from shielddesk.application.dto.analysis_result_v1 import (
    from_dict as analysis_result_from_dict,
)
from shielddesk.application.dto.analysis_result_v1 import (
    to_dict as analysis_result_to_dict,
)
from shielddesk.application.dto.incoming_message_v1 import (
    from_dict as incoming_message_from_dict,
)
from shielddesk.application.dto.incoming_message_v1 import (
    to_dict as incoming_message_to_dict,
)
from shielddesk.domain.entities.evidence_record import EvidenceRecord

SCHEMA_VERSION = "1.0"


def to_dict(record: EvidenceRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": record.evidence_id,
        "message": incoming_message_to_dict(record.message),
        "analysis": analysis_result_to_dict(record.analysis),
        "stored_at": record.stored_at.isoformat(),
        "user_annotation": record.user_annotation,
    }


def from_dict(data: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=data["evidence_id"],
        message=incoming_message_from_dict(data["message"]),
        analysis=analysis_result_from_dict(data["analysis"]),
        stored_at=datetime.fromisoformat(data["stored_at"]),
        user_annotation=data.get("user_annotation"),
    )
