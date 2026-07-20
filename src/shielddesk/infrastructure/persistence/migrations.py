"""Migrazioni dello schema (Fase 5): applicate idempotentemente via `PRAGMA user_version`.

Ogni voce è (versione, sql): eseguita solo se la versione corrente del database
è inferiore. Aggiungere nuove migrazioni in coda, mai modificare quelle esistenti.
"""

from __future__ import annotations

from typing import Protocol


class _Cursor(Protocol):
    """Usato solo per `PRAGMA user_version`, che restituisce sempre un intero."""

    def fetchone(self) -> tuple[int] | None: ...


class _Connection(Protocol):
    """sqlcipher3.Connection non è una sottoclasse di sqlite3.Connection (è
    un'estensione C separata con API compatibile): un Protocol strutturale
    permette di tipizzare correttamente entrambe senza un cast.
    """

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor: ...
    def executescript(self, sql: str) -> object: ...
    def commit(self) -> None: ...


_MIGRATIONS: tuple[tuple[int, str], ...] = (
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS evidence (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT UNIQUE NOT NULL,
            payload TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """,
    ),
)

LATEST_VERSION = _MIGRATIONS[-1][0]


def apply_migrations(connection: _Connection) -> None:
    row = connection.execute("PRAGMA user_version").fetchone()
    current_version = row[0] if row is not None else 0
    for version, sql in _MIGRATIONS:
        if version > current_version:
            connection.executescript(sql)
            connection.execute(f"PRAGMA user_version = {version}")
    connection.commit()
