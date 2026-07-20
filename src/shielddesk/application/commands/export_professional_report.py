"""Report professionale (Fase 8, ADR-010): PDF + JSON + manifest, tutti dentro
uno ZIP cifrato AES. Opera su coppie messaggio+analisi generiche: sia una
timeline appena analizzata (Fase 7, `ChatTimelineEntry`) sia prove storiche
dalla cassaforte (`EvidenceRecord`, Fase 10) le espongono nella stessa forma.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shielddesk.application.dto.analysis_result_v1 import to_dict
from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.services.redaction import RedactionService
from shielddesk.infrastructure.reporting.encrypted_zip import create_encrypted_zip
from shielddesk.infrastructure.reporting.manifest import write_manifest
from shielddesk.infrastructure.reporting.pdf_report import render_pdf
from shielddesk.infrastructure.reporting.report_row import ReportRow

REPORT_SCHEMA_VERSION = "1.0"

ReportEntry = tuple[IncomingMessage, AnalysisResult]


def _build_rows(entries: list[ReportEntry], redact: bool) -> list[ReportRow]:
    redaction = RedactionService()
    rows = []
    for message, analysis in entries:
        sender_label = redaction.pseudonym_for(message.sender) if redact else message.sender
        rows.append(
            ReportRow(
                sender_label=sender_label,
                text=message.text,
                timestamp=message.timestamp.isoformat(timespec="minutes"),
                risk_level=analysis.risk_level.name,
                tier=analysis.tier.value,
                model_id=analysis.model_id,
            )
        )
    return rows


def _build_json_payload(
    entries: list[ReportEntry], rows: list[ReportRow], redacted: bool
) -> dict[str, Any]:
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "redacted": redacted,
        "entry_count": len(entries),
        "entries": [
            {"sender": row.sender_label, "text": row.text, "analysis": to_dict(analysis)}
            for row, (_, analysis) in zip(rows, entries, strict=True)
        ],
    }


@dataclass(frozen=True, slots=True)
class ExportProfessionalReportCommand:
    async def execute(
        self,
        entries: list[ReportEntry],
        output_dir: Path,
        zip_password: str,
        redact: bool = True,
        title: str = "Report ShieldDesk",
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = _build_rows(entries, redact)

        pdf_path = render_pdf(rows, output_dir / "report.pdf", title, redacted=redact)
        json_path = output_dir / "report.json"
        json_path.write_text(
            json.dumps(_build_json_payload(entries, rows, redact), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        manifest_path = write_manifest([pdf_path, json_path], output_dir / "manifest.json")

        zip_path = create_encrypted_zip(
            [pdf_path, json_path, manifest_path],
            output_dir / "report.zip",
            zip_password,
        )

        # i file in chiaro sono serviti solo a costruire lo ZIP: non vanno lasciati
        # su disco fuori dal contenitore cifrato.
        pdf_path.unlink()
        json_path.unlink()
        manifest_path.unlink()

        return zip_path
