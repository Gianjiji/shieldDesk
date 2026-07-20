"""Verifica *con evidenza*, non solo per dichiarazione, che ShieldDesk non apre
connessioni di rete durante il funzionamento normale (CLAUDE.md "Regole di
sicurezza": "nessuna dipendenza di rete in runtime; verificarlo con test dedicati").

Blocca `socket.socket.connect`/`connect_ex` a livello di libreria standard: se un
qualunque componente (diretto o transitivo) tentasse di aprire un socket verso
l'esterno durante il flusso completo (container → analisi → salvataggio →
report), il test fallisce immediatamente invece di lasciarlo passare inosservato.
"""

import socket
from pathlib import Path

import pytest

from shielddesk.application.commands.analyze_chat import AnalyzeChatCommand
from shielddesk.application.commands.export_professional_report import (
    ExportProfessionalReportCommand,
)
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.config.container import build_container


class _NetworkAccessAttempted(AssertionError):
    pass


@pytest.fixture
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: object, **kwargs: object) -> None:
        raise _NetworkAccessAttempted(
            f"tentativo di accesso alla rete bloccato: args={args!r} kwargs={kwargs!r}"
        )

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.mark.asyncio
async def test_full_vertical_slice_never_touches_the_network(
    block_network: None, tmp_path: Path
) -> None:
    container = build_container(vault_dir=tmp_path / "vault", analyzer=MockAnalyzer())

    export_text = (
        "[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?\n"
        "[24/07/26, 09:17:12] Sconosciuto: Stai attento perché ti ammazzo\n"
    )
    analyze_chat = AnalyzeChatCommand(analyzer=container.analyzer)
    entries = await analyze_chat.execute(export_text)
    assert len(entries) == 2

    for entry in entries:
        await container.evidence_repository.store(entry.message, entry.analysis)

    export_report = ExportProfessionalReportCommand()
    report_entries = [(entry.message, entry.analysis) for entry in entries]
    zip_path = await export_report.execute(
        report_entries, output_dir=tmp_path / "reports", zip_password="password-test"
    )
    assert zip_path.exists()
