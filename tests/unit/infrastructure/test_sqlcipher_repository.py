from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlcipher3

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.persistence.migrations import LATEST_VERSION
from shielddesk.infrastructure.persistence.sqlcipher_repository import (
    SQLCipherEvidenceRepository,
)

_KEY = b"\x01" * 32
_OTHER_KEY = b"\x02" * 32
_SENSITIVE_MARKER = "ti-ammazzo-contenuto-sensibile"


def _make_message(message_id: str = "msg-1", text: str = "ciao") -> IncomingMessage:
    return IncomingMessage(
        message_id=message_id,
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text=text,
        timestamp=datetime.now(UTC),
    )


def _make_result(message_id: str = "msg-1", risk: RiskLevel = RiskLevel.HIGH) -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0",
        message_id=message_id,
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=risk,
    )


@pytest.mark.asyncio
async def test_store_and_get_roundtrip(tmp_path: Path) -> None:
    repo = SQLCipherEvidenceRepository(tmp_path / "test.db", key=_KEY)
    evidence_id = await repo.store(_make_message(), _make_result())

    fetched = await repo.get(evidence_id)

    assert fetched is not None
    assert fetched.message.sender == "tester"
    assert fetched.analysis.message_id == "msg-1"
    assert fetched.analysis.risk_level is RiskLevel.HIGH
    repo.close()


@pytest.mark.asyncio
async def test_list_all_returns_every_stored_result(tmp_path: Path) -> None:
    repo = SQLCipherEvidenceRepository(tmp_path / "test.db", key=_KEY)
    await repo.store(_make_message("msg-1"), _make_result("msg-1"))
    await repo.store(_make_message("msg-2"), _make_result("msg-2"))

    records = await repo.list_all()

    assert {r.analysis.message_id for r in records} == {"msg-1", "msg-2"}
    repo.close()


@pytest.mark.asyncio
async def test_db_file_never_contains_plaintext(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = SQLCipherEvidenceRepository(db_path, key=_KEY)
    await repo.store(_make_message(_SENSITIVE_MARKER, text=_SENSITIVE_MARKER), _make_result())
    repo.close()

    raw_bytes = db_path.read_bytes()

    assert _SENSITIVE_MARKER.encode("utf-8") not in raw_bytes


@pytest.mark.asyncio
async def test_wrong_key_cannot_open_database(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    writer = SQLCipherEvidenceRepository(db_path, key=_KEY)
    await writer.store(_make_message(), _make_result())
    writer.close()

    with pytest.raises(sqlcipher3.DatabaseError):
        SQLCipherEvidenceRepository(db_path, key=_OTHER_KEY)


def test_rejects_key_of_wrong_length(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="32 byte"):
        SQLCipherEvidenceRepository(tmp_path / "test.db", key=b"troppo-corta")


@pytest.mark.asyncio
async def test_verify_integrity_true_on_untampered_chain(tmp_path: Path) -> None:
    repo = SQLCipherEvidenceRepository(tmp_path / "test.db", key=_KEY)
    await repo.store(_make_message("msg-1"), _make_result("msg-1"))
    await repo.store(_make_message("msg-2"), _make_result("msg-2"))
    await repo.store(_make_message("msg-3"), _make_result("msg-3"))

    assert repo.verify_integrity() is True
    repo.close()


@pytest.mark.asyncio
async def test_verify_integrity_false_after_tampering(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo = SQLCipherEvidenceRepository(db_path, key=_KEY)
    await repo.store(_make_message("msg-1"), _make_result("msg-1"))
    await repo.store(_make_message("msg-2"), _make_result("msg-2"))
    repo.close()

    # riapre con la stessa chiave e manomette direttamente una riga via SQL
    tamper_repo = SQLCipherEvidenceRepository(db_path, key=_KEY)
    tamper_repo._connection.execute(
        "UPDATE evidence SET payload = replace(payload, 'msg-1', 'msg-1-manomesso') WHERE seq = 1"
    )
    tamper_repo._connection.commit()

    assert tamper_repo.verify_integrity() is False
    tamper_repo.close()


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repo1 = SQLCipherEvidenceRepository(db_path, key=_KEY)
    version_after_first = repo1._connection.execute("PRAGMA user_version").fetchone()[0]
    repo1.close()

    repo2 = SQLCipherEvidenceRepository(db_path, key=_KEY)  # riapplica le migrazioni
    version_after_second = repo2._connection.execute("PRAGMA user_version").fetchone()[0]
    repo2.close()

    assert version_after_first == LATEST_VERSION
    assert version_after_second == LATEST_VERSION
