from shielddesk.domain.services.redaction import RedactionService


def test_pseudonym_is_consistent_for_same_sender() -> None:
    service = RedactionService()

    first = service.pseudonym_for("Mario Rossi")
    second = service.pseudonym_for("Mario Rossi")

    assert first == second


def test_different_senders_get_different_pseudonyms() -> None:
    service = RedactionService()

    a = service.pseudonym_for("Mario Rossi")
    b = service.pseudonym_for("Giulia Bianchi")

    assert a != b


def test_pseudonyms_never_contain_original_name() -> None:
    service = RedactionService()

    pseudonym = service.pseudonym_for("Mario Rossi")

    assert "Mario" not in pseudonym
    assert "Rossi" not in pseudonym


def test_mapping_exposes_assigned_pseudonyms() -> None:
    service = RedactionService()
    service.pseudonym_for("Mario Rossi")
    service.pseudonym_for("Giulia Bianchi")

    assert service.mapping == {"Mario Rossi": "Persona 1", "Giulia Bianchi": "Persona 2"}
