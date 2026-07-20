"""Derivazione della chiave di cifratura da una passphrase (ADR-006/007).

Nessuna passphrase o chiave è mai hard-coded: questo modulo si limita a
trasformare una passphrase fornita a runtime in una chiave a lunghezza fissa.
"""

from __future__ import annotations

from argon2.low_level import Type, hash_secret_raw

KEY_LENGTH_BYTES = 32  # AES-256
SALT_LENGTH_BYTES = 16

# Parametri Argon2id: punto di partenza ragionevole per un uso desktop
# single-user; da ricalibrare (§16.4 ADR-006) con un benchmark hardware reale
# prima del rilascio.
_TIME_COST = 3
_MEMORY_COST_KIB = 64 * 1024
_PARALLELISM = 2


def derive_key(passphrase: str, salt: bytes) -> bytes:
    if len(salt) != SALT_LENGTH_BYTES:
        raise ValueError(f"Il salt deve essere lungo {SALT_LENGTH_BYTES} byte")
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=_TIME_COST,
        memory_cost=_MEMORY_COST_KIB,
        parallelism=_PARALLELISM,
        hash_len=KEY_LENGTH_BYTES,
        type=Type.ID,
    )
