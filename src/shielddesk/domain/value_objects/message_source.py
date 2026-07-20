from enum import StrEnum


class MessageSource(StrEnum):
    """Origine di un IncomingMessage."""

    WHATSAPP_NOTIFICATION = "whatsapp_notification"
    MANUAL_PASTE = "manual_paste"
    CHAT_IMPORT = "chat_import"
