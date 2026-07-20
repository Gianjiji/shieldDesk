from pathlib import Path

import pytest

from shielddesk.infrastructure.crypto.vault_key import (
    VaultKeyService,
    VaultUnlockError,
    generate_recovery_key,
)


def test_generate_recovery_key_format() -> None:
    key = generate_recovery_key()
    groups = key.split("-")
    assert len(groups) == 6
    assert all(len(g) == 5 for g in groups)
    assert all(c not in key for c in "0O1IL")  # alfabeto senza caratteri ambigui


def test_generate_recovery_key_is_random() -> None:
    assert generate_recovery_key() != generate_recovery_key()


def test_setup_and_unlock_with_passphrase(tmp_path: Path) -> None:
    service = VaultKeyService(tmp_path / "keyvault.json")

    master_key, recovery_key = service.setup(passphrase="una-passphrase-robusta")
    unlocked = service.unlock_with_passphrase("una-passphrase-robusta")

    assert unlocked == master_key
    assert len(master_key) == 32


def test_setup_and_unlock_with_recovery_key(tmp_path: Path) -> None:
    service = VaultKeyService(tmp_path / "keyvault.json")

    master_key, recovery_key = service.setup(passphrase="una-passphrase-robusta")
    unlocked = service.unlock_with_recovery_key(recovery_key)

    assert unlocked == master_key


def test_wrong_passphrase_raises_vault_unlock_error(tmp_path: Path) -> None:
    service = VaultKeyService(tmp_path / "keyvault.json")
    service.setup(passphrase="passphrase-corretta")

    with pytest.raises(VaultUnlockError):
        service.unlock_with_passphrase("passphrase-sbagliata")


def test_wrong_recovery_key_raises_vault_unlock_error(tmp_path: Path) -> None:
    service = VaultKeyService(tmp_path / "keyvault.json")
    service.setup(passphrase="passphrase-corretta")

    with pytest.raises(VaultUnlockError):
        service.unlock_with_recovery_key("XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-XXXXX")


def test_unlock_without_setup_raises(tmp_path: Path) -> None:
    service = VaultKeyService(tmp_path / "keyvault.json")

    with pytest.raises(VaultUnlockError, match="eseguire prima setup"):
        service.unlock_with_passphrase("qualsiasi")
