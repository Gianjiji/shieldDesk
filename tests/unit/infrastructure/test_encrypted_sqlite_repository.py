from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.persistence.encrypted_sqlite_repository import (
    EncryptedSqliteRepository,
)

_SENSITIVE_MARKER = "ti-ammazzo-contenuto-sensibile"


def _make_message(message_id: str = "msg-1", text: str = "ciao") -> IncomingMessage:
    return IncomingMessage(
        message_id=message_id,
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text=text,
        timestamp=datetime.now(UTC),
    )


def _make_result(message_id: str = "msg-1") -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0",
        message_id=message_id,
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=RiskLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_store_and_get_roundtrip(tmp_path: Path) -> None:
    repository = EncryptedSqliteRepository(tmp_path / "test.db", passphrase="passphrase-di-test")
    message, result = _make_message(), _make_result()

    evidence_id = await repository.store(message, result)
    fetched = await repository.get(evidence_id)

    assert fetched is not None
    assert fetched.analysis.message_id == result.message_id
    assert fetched.analysis.risk_level is RiskLevel.HIGH
    assert fetched.message.sender == "tester"
    repository.close()


@pytest.mark.asyncio
async def test_get_missing_id_returns_none(tmp_path: Path) -> None:
    repository = EncryptedSqliteRepository(tmp_path / "test.db", passphrase="passphrase-di-test")
    assert await repository.get("non-esiste") is None
    repository.close()


@pytest.mark.asyncio
async def test_list_all_returns_every_stored_result(tmp_path: Path) -> None:
    repository = EncryptedSqliteRepository(tmp_path / "test.db", passphrase="passphrase-di-test")
    await repository.store(_make_message("msg-1"), _make_result("msg-1"))
    await repository.store(_make_message("msg-2"), _make_result("msg-2"))

    records = await repository.list_all()

    assert {r.analysis.message_id for r in records} == {"msg-1", "msg-2"}
    repository.close()


@pytest.mark.asyncio
async def test_db_file_never_contains_plaintext_message_id(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    repository = EncryptedSqliteRepository(db_path, passphrase="passphrase-di-test")
    await repository.store(
        _make_message(_SENSITIVE_MARKER, text=_SENSITIVE_MARKER), _make_result()
    )
    repository.close()

    raw_bytes = db_path.read_bytes()

    assert _SENSITIVE_MARKER.encode("utf-8") not in raw_bytes


@pytest.mark.asyncio
async def test_wrong_passphrase_cannot_decrypt(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    writer = EncryptedSqliteRepository(db_path, passphrase="passphrase-corretta")
    evidence_id = await writer.store(_make_message(), _make_result())
    writer.close()

    reader = EncryptedSqliteRepository(db_path, passphrase="passphrase-sbagliata")
    with pytest.raises(InvalidTag):
        await reader.get(evidence_id)
    reader.close()
