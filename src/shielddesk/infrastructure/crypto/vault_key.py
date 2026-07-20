"""Key management del vault (ADR-007): passphrase obbligatoria + recovery key.

Schema a "envelope encryption": una master key casuale cifra davvero il database;
la master key stessa è avvolta (wrapped) due volte — una con una chiave derivata
dalla passphrase, una con una chiave derivata dalla recovery key — così l'utente
può sbloccare il vault con l'una o l'altra. Se entrambe vanno perse, i dati sono
irrecuperabili per progetto (nessuna backdoor): va comunicato onestamente
all'utente in fase di onboarding (fuori dallo scope di questa fase).
"""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidTag

from shielddesk.infrastructure.crypto.aes_gcm import EncryptedBlob, decrypt, encrypt
from shielddesk.infrastructure.crypto.key_derivation import (
    KEY_LENGTH_BYTES,
    SALT_LENGTH_BYTES,
    derive_key,
)

MASTER_KEY_LENGTH_BYTES = KEY_LENGTH_BYTES
_RECOVERY_KEY_GROUPS = 6
_RECOVERY_KEY_GROUP_LENGTH = 5


class VaultUnlockError(Exception):
    """Passphrase o recovery key errate: mai distinguere quale delle due nel messaggio,
    per non dare a un attaccante un oracolo su quale credenziale è quella sbagliata."""


def generate_recovery_key() -> str:
    """Genera una recovery key leggibile e stampabile, es. "XK3F9-7QRTL-...".

    Alfabeto senza caratteri ambigui (0/O, 1/I/L esclusi) pensato per la
    trascrizione a mano, coerente con l'uso previsto (stampare e conservare
    offline in fase di onboarding).
    """
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    groups = [
        "".join(secrets.choice(alphabet) for _ in range(_RECOVERY_KEY_GROUP_LENGTH))
        for _ in range(_RECOVERY_KEY_GROUPS)
    ]
    return "-".join(groups)


@dataclass(frozen=True, slots=True)
class _WrappedKey:
    salt: bytes
    nonce: bytes
    ciphertext: bytes

    def to_dict(self) -> dict[str, str]:
        return {
            "salt": self.salt.hex(),
            "nonce": self.nonce.hex(),
            "ciphertext": self.ciphertext.hex(),
        }

    @staticmethod
    def from_dict(data: dict[str, str]) -> _WrappedKey:
        return _WrappedKey(
            salt=bytes.fromhex(data["salt"]),
            nonce=bytes.fromhex(data["nonce"]),
            ciphertext=bytes.fromhex(data["ciphertext"]),
        )


def _wrap(master_key: bytes, unlock_secret: str) -> _WrappedKey:
    salt = os.urandom(SALT_LENGTH_BYTES)
    wrapping_key = derive_key(unlock_secret, salt)
    blob = encrypt(wrapping_key, master_key)
    return _WrappedKey(salt=salt, nonce=blob.nonce, ciphertext=blob.ciphertext)


def _unwrap(wrapped: _WrappedKey, unlock_secret: str) -> bytes:
    wrapping_key = derive_key(unlock_secret, wrapped.salt)
    blob = EncryptedBlob(nonce=wrapped.nonce, ciphertext=wrapped.ciphertext)
    try:
        return decrypt(wrapping_key, blob)
    except InvalidTag as exc:
        raise VaultUnlockError("passphrase o recovery key non valide") from exc


class VaultKeyService:
    """Gestisce il file di key-vault (blob avvolti, mai la master key in chiaro su disco)."""

    def __init__(self, key_vault_path: Path) -> None:
        self._path = key_vault_path

    @property
    def exists(self) -> bool:
        return self._path.exists()

    def setup(self, passphrase: str) -> tuple[bytes, str]:
        """Prima configurazione: genera master key + recovery key, scrive il file.

        Restituisce (master_key, recovery_key). La recovery key va mostrata
        all'utente UNA volta sola: non è recuperabile da questo servizio dopo.
        """
        master_key = os.urandom(MASTER_KEY_LENGTH_BYTES)
        recovery_key = generate_recovery_key()

        payload = {
            "schema_version": "1.0",
            "passphrase_wrap": _wrap(master_key, passphrase).to_dict(),
            "recovery_wrap": _wrap(master_key, recovery_key).to_dict(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return master_key, recovery_key

    def unlock_with_passphrase(self, passphrase: str) -> bytes:
        wrapped = self._load_wrap("passphrase_wrap")
        return _unwrap(wrapped, passphrase)

    def unlock_with_recovery_key(self, recovery_key: str) -> bytes:
        wrapped = self._load_wrap("recovery_wrap")
        return _unwrap(wrapped, recovery_key)

    def _load_wrap(self, field: str) -> _WrappedKey:
        if not self._path.exists():
            raise VaultUnlockError("nessun vault configurato: eseguire prima setup()")
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return _WrappedKey.from_dict(data[field])
