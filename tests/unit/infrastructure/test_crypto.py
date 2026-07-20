import os

import pytest
from cryptography.exceptions import InvalidTag

from shielddesk.infrastructure.crypto.aes_gcm import decrypt, encrypt
from shielddesk.infrastructure.crypto.key_derivation import SALT_LENGTH_BYTES, derive_key


def test_derive_key_is_deterministic_for_same_passphrase_and_salt() -> None:
    salt = os.urandom(SALT_LENGTH_BYTES)
    key_a = derive_key("passphrase-di-test", salt)
    key_b = derive_key("passphrase-di-test", salt)
    assert key_a == key_b
    assert len(key_a) == 32


def test_derive_key_differs_for_different_salt() -> None:
    key_a = derive_key("passphrase-di-test", os.urandom(SALT_LENGTH_BYTES))
    key_b = derive_key("passphrase-di-test", os.urandom(SALT_LENGTH_BYTES))
    assert key_a != key_b


def test_derive_key_rejects_wrong_salt_length() -> None:
    with pytest.raises(ValueError, match="salt deve essere lungo"):
        derive_key("passphrase", b"troppo-corto")


def test_encrypt_decrypt_roundtrip() -> None:
    key = derive_key("passphrase-di-test", os.urandom(SALT_LENGTH_BYTES))
    plaintext = b"contenuto sensibile del messaggio"

    blob = encrypt(key, plaintext)

    assert plaintext not in blob.ciphertext
    assert decrypt(key, blob) == plaintext


def test_decrypt_fails_with_wrong_key() -> None:
    salt = os.urandom(SALT_LENGTH_BYTES)
    key = derive_key("passphrase-corretta", salt)
    wrong_key = derive_key("passphrase-sbagliata", salt)
    blob = encrypt(key, b"segreto")

    with pytest.raises(InvalidTag):
        decrypt(wrong_key, blob)
