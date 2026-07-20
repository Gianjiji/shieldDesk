from shielddesk.infrastructure.logging import _REDACTED, _redact_message_fields


def test_redacts_known_sensitive_fields() -> None:
    event_dict = {
        "event": "message_received",
        "text": "contenuto sensibile del messaggio",
        "sender": "Mario Rossi",
        "message_id": "msg-1",
    }

    redacted = _redact_message_fields(None, "info", event_dict)

    assert redacted["text"] == _REDACTED
    assert redacted["sender"] == _REDACTED
    assert redacted["message_id"] == "msg-1"
    assert redacted["event"] == "message_received"


def test_redaction_is_case_insensitive_on_field_name() -> None:
    event_dict = {"TEXT": "contenuto"}

    redacted = _redact_message_fields(None, "info", event_dict)

    assert redacted["TEXT"] == _REDACTED
