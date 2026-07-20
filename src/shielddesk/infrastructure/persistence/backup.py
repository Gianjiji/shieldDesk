"""Backup del vault (Fase 5): copia sicura via API di backup nativa di SQLite/
SQLCipher (mai una copia file grezza, che rischierebbe uno stato incoerente su
un database aperto), con verifica post-copia che il conteggio righe combaci.
Il backup resta cifrato con la stessa chiave: nessun dato in chiaro su disco.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import sqlcipher3


class BackupIntegrityError(Exception):
    """Il backup risulta incompleto (conteggio righe diverso dalla sorgente)."""


def backup_database(source_path: Path, backup_dir: Path, key: bytes) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"shielddesk-backup-{timestamp}.db"

    source = sqlcipher3.connect(str(source_path))
    source.execute(f'PRAGMA key = "x\'{key.hex()}\'"')
    destination = sqlcipher3.connect(str(backup_path))
    destination.execute(f'PRAGMA key = "x\'{key.hex()}\'"')

    try:
        source.backup(destination)
        source_count = source.execute("SELECT count(*) FROM evidence").fetchone()[0]
        dest_count = destination.execute("SELECT count(*) FROM evidence").fetchone()[0]
    finally:
        source.close()
        destination.close()

    if source_count != dest_count:
        backup_path.unlink(missing_ok=True)
        raise BackupIntegrityError(
            f"righe sorgente={source_count} righe backup={dest_count}: backup scartato"
        )

    return backup_path
