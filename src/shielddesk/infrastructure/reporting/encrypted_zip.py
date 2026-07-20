"""ZIP cifrato AES (ADR-010) per il bundle del report: password separata dalla
passphrase del vault, pensata per essere condivisa con chi deve ricevere il report."""

from __future__ import annotations

from pathlib import Path

import pyzipper


def create_encrypted_zip(files: list[Path], zip_path: Path, password: str) -> Path:
    with pyzipper.AESZipFile(
        zip_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zip_file:
        zip_file.setpassword(password.encode("utf-8"))
        for file_path in files:
            zip_file.write(file_path, arcname=file_path.name)
    return zip_path
