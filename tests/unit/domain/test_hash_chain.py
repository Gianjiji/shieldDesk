from shielddesk.domain.services.hash_chain import (
    GENESIS_HASH,
    compute_record_hash,
    verify_chain,
)


def test_compute_record_hash_is_deterministic() -> None:
    h1 = compute_record_hash(GENESIS_HASH, b"payload-a")
    h2 = compute_record_hash(GENESIS_HASH, b"payload-a")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_record_hash_differs_for_different_payload() -> None:
    h1 = compute_record_hash(GENESIS_HASH, b"payload-a")
    h2 = compute_record_hash(GENESIS_HASH, b"payload-b")
    assert h1 != h2


def test_verify_chain_accepts_empty_list() -> None:
    assert verify_chain([]) is True


def test_verify_chain_accepts_valid_chain() -> None:
    hash1 = compute_record_hash(GENESIS_HASH, b"payload-1")
    hash2 = compute_record_hash(hash1, b"payload-2")
    records = [
        (GENESIS_HASH, hash1, b"payload-1"),
        (hash1, hash2, b"payload-2"),
    ]
    assert verify_chain(records) is True


def test_verify_chain_detects_tampered_payload() -> None:
    hash1 = compute_record_hash(GENESIS_HASH, b"payload-1")
    records = [(GENESIS_HASH, hash1, b"payload-1-manomesso")]
    assert verify_chain(records) is False


def test_verify_chain_detects_removed_record() -> None:
    hash1 = compute_record_hash(GENESIS_HASH, b"payload-1")
    hash2 = compute_record_hash(hash1, b"payload-2")
    hash3 = compute_record_hash(hash2, b"payload-3")
    # il record centrale è stato rimosso: previous_hash del terzo non combacia più
    records = [
        (GENESIS_HASH, hash1, b"payload-1"),
        (hash1, hash3, b"payload-3"),
    ]
    assert verify_chain(records) is False


def test_verify_chain_detects_wrong_genesis() -> None:
    records = [("hash-non-genesis", compute_record_hash("hash-non-genesis", b"x"), b"x")]
    assert verify_chain(records) is False
