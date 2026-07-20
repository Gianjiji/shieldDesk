from datetime import UTC, datetime
from pathlib import Path

import pytest

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.persistence.backup import backup_database
from shielddesk.infrastructure.persistence.sqlcipher_repository import (
    SQLCipherEvidenceRepository,
)

_KEY = b"\x03" * 32


def _make_message(message_id: str) -> IncomingMessage:
    return IncomingMessage(
        message_id=message_id,
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text="ciao",
        timestamp=datetime.now(UTC),
    )


def _make_result(message_id: str) -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0",
        message_id=message_id,
        tier=AnalysisTier.RULES,
        model_id="mock-analyzer",
        model_version="0.1.0",
        prompt_version="n/a",
        timestamp=datetime.now(UTC),
        risk_level=RiskLevel.SAFE,
    )


@pytest.mark.asyncio
async def test_backup_contains_all_records_and_stays_encrypted(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    repo = SQLCipherEvidenceRepository(source_path, key=_KEY)
    await repo.store(_make_message("msg-1"), _make_result("msg-1"))
    await repo.store(_make_message("msg-2"), _make_result("msg-2"))
    repo.close()

    backup_path = backup_database(source_path, tmp_path / "backups", key=_KEY)

    assert backup_path.exists()
    backup_repo = SQLCipherEvidenceRepository(backup_path, key=_KEY)
    records = await backup_repo.list_all()
    assert {r.analysis.message_id for r in records} == {"msg-1", "msg-2"}
    assert backup_repo.verify_integrity() is True
    backup_repo.close()


def test_backup_filename_is_timestamped(tmp_path: Path) -> None:
    source_path = tmp_path / "source.db"
    SQLCipherEvidenceRepository(source_path, key=_KEY).close()

    backup_path = backup_database(source_path, tmp_path / "backups", key=_KEY)

    assert backup_path.name.startswith("shielddesk-backup-")
    assert backup_path.suffix == ".db"
