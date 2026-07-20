"""Hash chain sugli EvidenceRecord (ADR-006): ogni record include l'hash del
precedente, così una manomissione o rimozione silenziosa di un record diventa
rilevabile ricalcolando la catena. Puro: nessuna dipendenza da crittografia o
persistenza, solo SHA-256 su byte canonici forniti dal chiamante.
"""

from __future__ import annotations

import hashlib

GENESIS_HASH = "0" * 64


def compute_record_hash(previous_hash: str, canonical_payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(previous_hash.encode("utf-8"))
    digest.update(canonical_payload)
    return digest.hexdigest()


def verify_chain(records: list[tuple[str, str, bytes]]) -> bool:
    """records: lista ordinata di (previous_hash, record_hash, canonical_payload).

    Restituisce False al primo anello rotto: previous_hash che non combacia con
    l'hash del record precedente, o record_hash che non ricalcola correttamente.
    """
    expected_previous = GENESIS_HASH
    for previous_hash, record_hash, canonical_payload in records:
        if previous_hash != expected_previous:
            return False
        if compute_record_hash(previous_hash, canonical_payload) != record_hash:
            return False
        expected_previous = record_hash
    return True
