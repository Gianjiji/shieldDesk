from pathlib import Path

import pytest
import sqlcipher3

from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.config.container import build_container
from shielddesk.infrastructure.notifications.fake_adapter import FakeNotificationAdapter
from shielddesk.infrastructure.persistence.sqlcipher_repository import (
    SQLCipherEvidenceRepository,
)


def test_build_container_wires_fake_and_encrypted_implementations(tmp_path: Path) -> None:
    container = build_container(vault_dir=tmp_path, analyzer=MockAnalyzer())

    assert isinstance(container.notification_source, FakeNotificationAdapter)
    assert isinstance(container.analyzer, MockAnalyzer)
    assert isinstance(container.evidence_repository, SQLCipherEvidenceRepository)
    assert container.notification_source.can_remove is True
    assert container.notification_source.can_reply is False


def test_build_container_falls_back_to_mock_when_model_missing(tmp_path: Path) -> None:
    """Fail-safe (ANALYSIS.md §H4): niente modello ONNX → degrado esplicito, non un crash."""
    empty_model_dir = tmp_path / "no-model-here"

    container = build_container(vault_dir=tmp_path, model_dir=empty_model_dir)

    assert isinstance(container.analyzer, MockAnalyzer)


def test_build_container_reopens_existing_vault_with_same_passphrase(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHIELDDESK_DEV_PASSPHRASE", "passphrase-di-test-riapertura")

    first = build_container(vault_dir=tmp_path, analyzer=MockAnalyzer())
    second = build_container(vault_dir=tmp_path, analyzer=MockAnalyzer())

    assert isinstance(first.evidence_repository, SQLCipherEvidenceRepository)
    assert isinstance(second.evidence_repository, SQLCipherEvidenceRepository)


def test_build_container_raises_loudly_on_mismatched_vault_db(
    tmp_path: Path, monkeypatch
) -> None:
    """Regressione: un evidence.db che non si apre con la master key (es. keyvault.json
    ed evidence.db disallineati dopo un ripristino parziale di backup) deve propagare
    l'errore, MAI degradare in silenzio a un vault fallback vuoto — l'utente vedrebbe
    una cassaforte apparentemente vuota invece di un errore.
    """
    monkeypatch.setenv("SHIELDDESK_DEV_PASSPHRASE", "passphrase-di-test-mismatch")

    build_container(vault_dir=tmp_path, analyzer=MockAnalyzer())  # crea keyvault + db
    # simula il disallineamento: il DB viene sostituito da uno cifrato con un'altra chiave
    (tmp_path / "evidence.db").unlink()
    other = SQLCipherEvidenceRepository(tmp_path / "evidence.db", key=b"\x07" * 32)
    other.close()

    with pytest.raises(sqlcipher3.DatabaseError):
        build_container(vault_dir=tmp_path, analyzer=MockAnalyzer())
