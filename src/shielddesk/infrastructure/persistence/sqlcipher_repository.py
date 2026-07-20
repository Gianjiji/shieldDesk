import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import sqlcipher3

from shielddesk.application.dto.evidence_record_v1 import from_dict, to_dict
from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.services.hash_chain import GENESIS_HASH, compute_record_hash, verify_chain
from shielddesk.infrastructure.persistence.migrations import apply_migrations


def _canonical_payload(record: EvidenceRecord) -> bytes:
    """Serializzazione con chiavi ordinate: lo stesso EvidenceRecord produce
    sempre lo stesso hash, indipendentemente dall'ordine di inserimento in dict.
    """
    return json.dumps(to_dict(record), sort_keys=True).encode("utf-8")


class SQLCipherEvidenceRepository:
    """Persistenza cifrata su SQLCipher (ADR-005, prima scelta) con hash chain
    (ADR-006): ogni riga include l'hash del record precedente, così una
    manomissione o cancellazione silenziosa diventa rilevabile con
    `verify_integrity()`. `key` è la master key già risolta (32 byte), mai una
    passphrase diretta: la derivazione passphrase→chiave vive in VaultKeyService.

    Il payload cifrato è l'intero EvidenceRecord (messaggio + analisi), non il
    solo AnalysisResult: senza il messaggio non si può ricostruire un report
    leggibile ("chi ha detto cosa").
    """

    def __init__(self, db_path: Path, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("la chiave deve essere di 32 byte (AES-256)")
        self._connection = sqlcipher3.connect(str(db_path))
        self._connection.execute(f'PRAGMA key = "x\'{key.hex()}\'"')
        # Verifica che la chiave sia corretta: un'operazione qualsiasi fallisce
        # con "file is not a database" se la chiave è sbagliata.
        self._connection.execute("SELECT count(*) FROM sqlite_master")
        apply_migrations(self._connection)

    async def store(self, message: IncomingMessage, analysis: AnalysisResult) -> str:
        evidence_id = str(uuid.uuid4())
        record = EvidenceRecord(
            evidence_id=evidence_id,
            message=message,
            analysis=analysis,
            stored_at=datetime.now(UTC),
        )
        payload = _canonical_payload(record)
        previous_hash = self._last_record_hash()
        record_hash = compute_record_hash(previous_hash, payload)
        self._connection.execute(
            "INSERT INTO evidence (id, payload, previous_hash, record_hash, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                evidence_id,
                payload.decode("utf-8"),
                previous_hash,
                record_hash,
                record.stored_at.isoformat(),
            ),
        )
        self._connection.commit()
        return evidence_id

    async def get(self, evidence_id: str) -> EvidenceRecord | None:
        row = self._connection.execute(
            "SELECT payload FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return None if row is None else from_dict(json.loads(row[0]))

    async def list_all(self) -> list[EvidenceRecord]:
        rows = self._connection.execute(
            "SELECT payload FROM evidence ORDER BY seq ASC"
        ).fetchall()
        return [from_dict(json.loads(row[0])) for row in rows]

    def verify_integrity(self) -> bool:
        rows = self._connection.execute(
            "SELECT previous_hash, record_hash, payload FROM evidence ORDER BY seq ASC"
        ).fetchall()
        records = [
            (previous_hash, record_hash, payload.encode("utf-8"))
            for previous_hash, record_hash, payload in rows
        ]
        return verify_chain(records)

    def close(self) -> None:
        self._connection.close()

    def _last_record_hash(self) -> str:
        row = self._connection.execute(
            "SELECT record_hash FROM evidence ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return GENESIS_HASH if row is None else str(row[0])
