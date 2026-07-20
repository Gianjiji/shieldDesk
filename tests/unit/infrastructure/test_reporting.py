from pathlib import Path

import pytest
import pyzipper

from shielddesk.infrastructure.reporting.encrypted_zip import create_encrypted_zip
from shielddesk.infrastructure.reporting.manifest import build_manifest, write_manifest
from shielddesk.infrastructure.reporting.pdf_report import render_pdf
from shielddesk.infrastructure.reporting.report_row import ReportRow

_ROWS = [
    ReportRow("09:15", "Persona 1", "Ciao come stai?", "SAFE", "rules", "mock-analyzer"),
    ReportRow(
        "09:17", "Persona 2", "Stai attento perché ti ammazzo", "HIGH", "rules", "mock-analyzer"
    ),
]


def test_render_pdf_creates_non_empty_file(tmp_path: Path) -> None:
    output_path = render_pdf(_ROWS, tmp_path / "report.pdf", "Titolo test", redacted=True)

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert output_path.read_bytes().startswith(b"%PDF")


def test_build_manifest_contains_correct_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"contenuto di prova")

    manifest = build_manifest([file_path])

    assert manifest["files"][0]["name"] == "sample.txt"
    assert len(manifest["files"][0]["sha256"]) == 64


def test_write_manifest_roundtrip(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"contenuto")

    manifest_path = write_manifest([file_path], tmp_path / "manifest.json")

    assert manifest_path.exists()
    assert "sha256" in manifest_path.read_text()


def test_encrypted_zip_opens_with_correct_password(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"contenuto sensibile")

    zip_path = create_encrypted_zip([file_path], tmp_path / "out.zip", "password-corretta")

    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-corretta")
        assert zf.read("sample.txt") == b"contenuto sensibile"


def test_encrypted_zip_rejects_wrong_password(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"contenuto sensibile")

    zip_path = create_encrypted_zip([file_path], tmp_path / "out.zip", "password-corretta")

    with pyzipper.AESZipFile(zip_path) as zf:
        zf.setpassword(b"password-sbagliata")
        with pytest.raises(RuntimeError):
            zf.read("sample.txt")


def test_zip_file_never_contains_plaintext_on_disk(tmp_path: Path) -> None:
    marker = b"contenuto-sensibile-da-non-esporre"
    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(marker)

    zip_path = create_encrypted_zip([file_path], tmp_path / "out.zip", "password-corretta")

    assert marker not in zip_path.read_bytes()
