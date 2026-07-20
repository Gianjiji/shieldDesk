"""Manifest del report (ADR-010/ADR-011): hash SHA-256 di ogni file incluso,
per rendere l'integrità del bundle verificabile indipendentemente dallo ZIP."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPORT_MANIFEST_SCHEMA_VERSION = "1.0"


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(files: list[Path]) -> dict[str, Any]:
    return {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": [{"name": f.name, "sha256": _sha256_of(f)} for f in files],
    }


def write_manifest(files: list[Path], output_path: Path) -> Path:
    manifest = build_manifest(files)
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
