from datetime import UTC, datetime

import pytest

from shielddesk.application.commands.analyze_message import AnalyzeMessageCommand
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.persistence.in_memory_repository import (
    InMemoryEvidenceRepository,
)


@pytest.mark.asyncio
async def test_execute_stores_analysis_result() -> None:
    repository = InMemoryEvidenceRepository()
    command = AnalyzeMessageCommand(analyzer=MockAnalyzer(), evidence_repository=repository)
    message = IncomingMessage(
        message_id="msg-1",
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text="ciao come stai",
        timestamp=datetime.now(UTC),
    )

    evidence_id = await command.execute(message)

    stored = await repository.get(evidence_id)
    assert stored is not None
    assert stored.message.message_id == "msg-1"
    assert stored.analysis.risk_level is RiskLevel.SAFE


@pytest.mark.asyncio
async def test_execute_flags_explicit_threat_keyword() -> None:
    repository = InMemoryEvidenceRepository()
    command = AnalyzeMessageCommand(analyzer=MockAnalyzer(), evidence_repository=repository)
    message = IncomingMessage(
        message_id="msg-2",
        source=MessageSource.MANUAL_PASTE,
        sender="tester",
        text="stai attento perché ti ammazzo",
        timestamp=datetime.now(UTC),
    )

    evidence_id = await command.execute(message)

    stored = await repository.get(evidence_id)
    assert stored is not None
    assert stored.analysis.risk_level is RiskLevel.HIGH
