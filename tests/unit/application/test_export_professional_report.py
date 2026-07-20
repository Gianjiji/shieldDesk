import json
from pathlib import Path

import pytest
import pyzipper
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from shielddesk.application.commands.analyze_chat import AnalyzeChatCommand
from shielddesk.application.commands.export_professional_report import (
    ExportProfessionalReportCommand,
)
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer

_EXPORT = """\
[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?
[24/07/26, 09:17:12] Giulia Bianchi: Stai attento perché ti ammazzo se lo dici a qualcuno
"""
_SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "schemas"


def _report_schema_validator() -> Draft202012Validator:
    resources = []
    for schema_path in _SCHEMAS_DIR.glob("*.schema.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        resources.append((schema_path.name, Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    schema = json.loads((_SCHEMAS_DIR / "report_v1.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=registry)


async def _make_entries() -> list:
    analyze = AnalyzeChatCommand(analyzer=MockAnalyzer())
    timeline = await analyze.execute(_EXPORT)
    return [(entry.message, entry.analysis) for entry in timeline]


@pytest.mark.asyncio
async def test_export_creates_password_protected_zip_with_three_files(tmp_path: Path) -> None:
    entries = await _make_entries()
    command = ExportProfessionalReportCommand()

    zip_path = await command.execute(
        entries, output_dir=tmp_path / "reports", zip_password="password-report", redact=True
    )

    assert zip_path.exists()
    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-report")
        names = set(zf.namelist())
        assert names == {"report.pdf", "report.json", "manifest.json"}
        zf.testzip()


@pytest.mark.asyncio
async def test_intermediate_plaintext_files_are_removed_after_zipping(tmp_path: Path) -> None:
    entries = await _make_entries()
    command = ExportProfessionalReportCommand()
    output_dir = tmp_path / "reports"

    await command.execute(entries, output_dir=output_dir, zip_password="password-report")

    assert not (output_dir / "report.pdf").exists()
    assert not (output_dir / "report.json").exists()
    assert not (output_dir / "manifest.json").exists()
    assert (output_dir / "report.zip").exists()


@pytest.mark.asyncio
async def test_redact_true_hides_real_sender_names(tmp_path: Path) -> None:
    entries = await _make_entries()
    command = ExportProfessionalReportCommand()

    zip_path = await command.execute(
        entries, output_dir=tmp_path / "reports", zip_password="password-report", redact=True
    )

    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-report")
        report_json = json.loads(zf.read("report.json"))

    senders = {entry["sender"] for entry in report_json["entries"]}
    assert "Mario Rossi" not in senders
    assert "Giulia Bianchi" not in senders
    assert report_json["redacted"] is True


@pytest.mark.asyncio
async def test_redact_false_keeps_real_sender_names(tmp_path: Path) -> None:
    entries = await _make_entries()
    command = ExportProfessionalReportCommand()

    zip_path = await command.execute(
        entries, output_dir=tmp_path / "reports", zip_password="password-report", redact=False
    )

    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-report")
        report_json = json.loads(zf.read("report.json"))

    senders = {entry["sender"] for entry in report_json["entries"]}
    assert senders == {"Mario Rossi", "Giulia Bianchi"}


@pytest.mark.asyncio
async def test_report_json_conforms_to_schema(tmp_path: Path) -> None:
    entries = await _make_entries()
    command = ExportProfessionalReportCommand()

    zip_path = await command.execute(
        entries, output_dir=tmp_path / "reports", zip_password="password-report"
    )

    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-report")
        report_json = json.loads(zf.read("report.json"))

    errors = list(_report_schema_validator().iter_errors(report_json))
    assert not errors, [e.message for e in errors]
