from dataclasses import dataclass
from datetime import datetime

from shielddesk.domain.value_objects.message_source import MessageSource


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    """Messaggio normalizzato indipendente dalla sorgente (notifica, paste, import)."""

    message_id: str
    source: MessageSource
    sender: str
    text: str
    timestamp: datetime
    is_truncated: bool = False
