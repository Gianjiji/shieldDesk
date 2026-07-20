"""Cifratura/decifratura simmetrica di singoli blob (fallback di ADR-005 a SQLCipher)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LENGTH_BYTES = 12


@dataclass(frozen=True, slots=True)
class EncryptedBlob:
    nonce: bytes
    ciphertext: bytes


def encrypt(key: bytes, plaintext: bytes) -> EncryptedBlob:
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data=None)
    return EncryptedBlob(nonce=nonce, ciphertext=ciphertext)


def decrypt(key: bytes, blob: EncryptedBlob) -> bytes:
    return AESGCM(key).decrypt(blob.nonce, blob.ciphertext, associated_data=None)
