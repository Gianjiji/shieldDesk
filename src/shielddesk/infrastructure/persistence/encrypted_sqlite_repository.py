import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from shielddesk.application.dto.evidence_record_v1 import from_dict, to_dict
from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.infrastructure.crypto.aes_gcm import EncryptedBlob, decrypt, encrypt
from shielddesk.infrastructure.crypto.key_derivation import SALT_LENGTH_BYTES, derive_key

_Row = tuple[bytes, bytes, bytes]


class EncryptedSqliteRepository:
    """Persistenza cifrata su SQLite: ogni riga contiene un blob AES-GCM, mai testo in chiaro.

    Fallback di ADR-005 quando SQLCipher non è disponibile; stessa interfaccia
    (EvidenceRepositoryPort), sostituibile senza toccare dominio o application
    layer. Ogni record usa un salt proprio: la chiave non è mai riutilizzata
    identica tra righe diverse. A differenza di SQLCipherEvidenceRepository non
    ha hash chain (fallback deliberatamente più semplice, vedi docs/phase-5-report.md).
    """

    def __init__(self, db_path: Path, passphrase: str) -> None:
        self._passphrase = passphrase
        self._connection = sqlite3.connect(db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL
            )
            """
        )
        self._connection.commit()

    async def store(self, message: IncomingMessage, analysis: AnalysisResult) -> str:
        evidence_id = str(uuid.uuid4())
        record = EvidenceRecord(
            evidence_id=evidence_id,
            message=message,
            analysis=analysis,
            stored_at=datetime.now(UTC),
        )
        salt = os.urandom(SALT_LENGTH_BYTES)
        key = derive_key(self._passphrase, salt)
        plaintext = json.dumps(to_dict(record)).encode("utf-8")
        blob = encrypt(key, plaintext)
        self._connection.execute(
            "INSERT INTO evidence (id, salt, nonce, ciphertext) VALUES (?, ?, ?, ?)",
            (evidence_id, salt, blob.nonce, blob.ciphertext),
        )
        self._connection.commit()
        return evidence_id

    async def get(self, evidence_id: str) -> EvidenceRecord | None:
        row = self._connection.execute(
            "SELECT salt, nonce, ciphertext FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return None if row is None else self._decode_row(row)

    async def list_all(self) -> list[EvidenceRecord]:
        rows = self._connection.execute("SELECT salt, nonce, ciphertext FROM evidence").fetchall()
        return [self._decode_row(row) for row in rows]

    def close(self) -> None:
        self._connection.close()

    def _decode_row(self, row: _Row) -> EvidenceRecord:
        salt, nonce, ciphertext = row
        key = derive_key(self._passphrase, salt)
        plaintext = decrypt(key, EncryptedBlob(nonce=nonce, ciphertext=ciphertext))
        return from_dict(json.loads(plaintext))
