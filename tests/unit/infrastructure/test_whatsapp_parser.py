from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.infrastructure.chat_import.whatsapp_parser import parse_whatsapp_export

_IOS_EXPORT = """\
[24/07/26, 09:15:03] I messaggi e le chiamate in questa chat sono crittografati end-to-end.
[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?
[24/07/26, 09:16:40] Giulia Bianchi: Tutto bene grazie, e tu?
[24/07/26, 09:17:12] Mario Rossi: Bene! Ci vediamo domani per il compito di matematica?
"""

_ANDROID_EXPORT = """\
24/07/26, 09:15 - I messaggi e le chiamate in questa chat sono crittografati end-to-end.
24/07/26, 09:15 - Mario Rossi: Ciao come stai?
24/07/26, 09:16 - Giulia Bianchi: Tutto bene grazie, e tu?
24/07/26, 09:20 - Mario Rossi ha cambiato l'icona del gruppo
"""

_MULTILINE_EXPORT = """\
[24/07/26, 09:15:03] Mario Rossi: Prima riga
seconda riga dello stesso messaggio
terza riga
[24/07/26, 09:16:00] Giulia Bianchi: Un altro messaggio
"""

_MEDIA_EXPORT = """\
[24/07/26, 09:15:03] Mario Rossi: <Media omessa>
"""


def test_parses_ios_export_skipping_encryption_notice() -> None:
    messages = parse_whatsapp_export(_IOS_EXPORT)

    assert len(messages) == 3
    assert messages[0].sender == "Mario Rossi"
    assert messages[0].text == "Ciao come stai?"
    assert messages[1].sender == "Giulia Bianchi"
    assert messages[2].text == "Bene! Ci vediamo domani per il compito di matematica?"


def test_parses_android_export_skipping_system_events() -> None:
    messages = parse_whatsapp_export(_ANDROID_EXPORT)

    assert len(messages) == 2  # la riga "ha cambiato l'icona" non è un messaggio
    assert messages[0].sender == "Mario Rossi"
    assert messages[1].sender == "Giulia Bianchi"


def test_handles_multiline_messages() -> None:
    messages = parse_whatsapp_export(_MULTILINE_EXPORT)

    assert len(messages) == 2
    assert messages[0].text == "Prima riga\nseconda riga dello stesso messaggio\nterza riga"
    assert messages[1].text == "Un altro messaggio"


def test_flags_media_placeholder_as_truncated() -> None:
    messages = parse_whatsapp_export(_MEDIA_EXPORT)

    assert len(messages) == 1
    assert messages[0].is_truncated is True


def test_uses_requested_source() -> None:
    messages = parse_whatsapp_export(_IOS_EXPORT, source=MessageSource.MANUAL_PASTE)

    assert all(m.source == MessageSource.MANUAL_PASTE for m in messages)


def test_empty_input_returns_empty_list() -> None:
    assert parse_whatsapp_export("") == []


def test_garbage_input_does_not_crash() -> None:
    messages = parse_whatsapp_export("questo non è un export di whatsapp\ncon più righe a caso\n")
    assert messages == []


def test_messages_are_chronologically_ordered() -> None:
    messages = parse_whatsapp_export(_IOS_EXPORT)
    timestamps = [m.timestamp for m in messages]
    assert timestamps == sorted(timestamps)
