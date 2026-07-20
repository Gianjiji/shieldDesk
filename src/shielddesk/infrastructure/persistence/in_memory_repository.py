import uuid
from datetime import UTC, datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage


class InMemoryEvidenceRepository:
    """Repository in-memory per test rapidi: nessun dato è cifrato né persistito su
    disco, mai da usare come persistenza reale (solo Fase 5/SQLCipher lo è).
    """

    def __init__(self) -> None:
        self._store: dict[str, EvidenceRecord] = {}

    async def store(self, message: IncomingMessage, analysis: AnalysisResult) -> str:
        evidence_id = str(uuid.uuid4())
        self._store[evidence_id] = EvidenceRecord(
            evidence_id=evidence_id,
            message=message,
            analysis=analysis,
            stored_at=datetime.now(UTC),
        )
        return evidence_id

    async def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._store.get(evidence_id)

    async def list_all(self) -> list[EvidenceRecord]:
        return list(self._store.values())
