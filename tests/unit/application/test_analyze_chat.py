import pytest

from shielddesk.application.commands.analyze_chat import AnalyzeChatCommand
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer

_EXPORT = """\
[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?
[24/07/26, 09:17:12] Sconosciuto: Stai attento perché ti ammazzo se lo dici a qualcuno
"""


@pytest.mark.asyncio
async def test_analyze_chat_produces_ordered_timeline_with_results() -> None:
    command = AnalyzeChatCommand(analyzer=MockAnalyzer())

    entries = await command.execute(_EXPORT)

    assert len(entries) == 2
    assert entries[0].message.sender == "Mario Rossi"
    assert entries[0].analysis.risk_level is RiskLevel.SAFE
    assert entries[1].message.sender == "Sconosciuto"
    assert entries[1].analysis.risk_level is RiskLevel.HIGH


@pytest.mark.asyncio
async def test_analyze_chat_uses_requested_source() -> None:
    command = AnalyzeChatCommand(analyzer=MockAnalyzer())

    entries = await command.execute(_EXPORT, source=MessageSource.MANUAL_PASTE)

    assert all(entry.message.source == MessageSource.MANUAL_PASTE for entry in entries)


@pytest.mark.asyncio
async def test_analyze_chat_empty_input_returns_empty_timeline() -> None:
    command = AnalyzeChatCommand(analyzer=MockAnalyzer())

    entries = await command.execute("")

    assert entries == []
