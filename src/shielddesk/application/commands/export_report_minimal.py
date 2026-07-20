import json
from dataclasses import dataclass
from pathlib import Path

from shielddesk.application.dto.evidence_record_v1 import to_dict
from shielddesk.domain.ports.evidence_repository import EvidenceRepositoryPort

REPORT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class ExportReportMinimalCommand:
    """Report minimale (JSON, senza PDF/ZIP): alternativa leggera al report
    professionale di Fase 8 quando basta un file JSON grezzo dalla cassaforte.
    """

    evidence_repository: EvidenceRepositoryPort

    async def execute(self, output_path: Path) -> Path:
        records = await self.evidence_repository.list_all()
        report = {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "entry_count": len(records),
            "entries": [to_dict(record) for record in records],
        }
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_path
