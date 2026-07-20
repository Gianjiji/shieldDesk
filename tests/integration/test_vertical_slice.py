"""Flusso completo di Fase 2: messaggio simulato → normalizzazione → analisi mock
→ risultato → salvataggio cifrato → visualizzazione cassaforte → report minimale.
"""

import json
from pathlib import Path

import pytest

from shielddesk.application.commands.analyze_message import AnalyzeMessageCommand
from shielddesk.application.commands.export_report_minimal import ExportReportMinimalCommand
from shielddesk.application.commands.process_incoming_messages import (
    ProcessIncomingMessagesCommand,
)
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.config.container import build_container


@pytest.mark.asyncio
async def test_full_vertical_slice(tmp_path: Path) -> None:
    # analyzer=MockAnalyzer(): questo test verifica il FLUSSO (pipeline end-to-end),
    # non la qualità del modello — quella è coperta da test_onnx_analyzer_benchmark.py.
    container = build_container(vault_dir=tmp_path / "vault", analyzer=MockAnalyzer())
    analyze_message = AnalyzeMessageCommand(
        analyzer=container.analyzer, evidence_repository=container.evidence_repository
    )
    process_incoming = ProcessIncomingMessagesCommand(
        notification_source=container.notification_source, analyze_message=analyze_message
    )
    export_report = ExportReportMinimalCommand(evidence_repository=container.evidence_repository)

    evidence_ids = await process_incoming.execute()
    assert len(evidence_ids) == 2  # i due messaggi simulati di default

    stored = await container.evidence_repository.list_all()
    risk_levels = {record.analysis.risk_level for record in stored}
    assert RiskLevel.HIGH in risk_levels
    assert RiskLevel.SAFE in risk_levels

    report_path = await export_report.execute(tmp_path / "report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["entry_count"] == 2
    assert len(report["entries"]) == 2
