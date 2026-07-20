"""Parser per l'export testuale di WhatsApp (file .txt o testo incollato).

Fail-safe per design: una riga che non riconosce non fa fallire l'intero
parsing, viene semplicemente ignorata o accodata al messaggio precedente
(continuazione multi-riga) — mai un crash su un formato inatteso.

Copre i due formati di export noti (iOS a parentesi quadre, Android a
trattino) nella variante italiana della data (gg/mm/aa). Altri locale/versioni
dell'app possono produrre formati leggermente diversi: è un parser
best-effort, non una garanzia di copertura totale (ANALYSIS.md §D/§K). Non
contiene timezone: WhatsApp esporta l'ora locale del dispositivo senza offset,
quindi i timestamp restano "naive" — un limite noto, non un bug.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource

_IOS_PATTERN = re.compile(
    r"^\[(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<rest>.+)$"
)
_ANDROID_PATTERN = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),\s*"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<rest>.+)$"
)

_MEDIA_PLACEHOLDERS = ("<Media omessa>", "<Media omitted>", "immagine omessa", "audio omesso")
_DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y")
_TIME_FORMATS = ("%H:%M:%S", "%H:%M")
_MAX_SENDER_LENGTH = 60


@dataclass(slots=True)
class _PendingMessage:
    sender: str
    text: str
    timestamp: datetime


def _parse_timestamp(date_str: str, time_str: str) -> datetime | None:
    for date_fmt in _DATE_FORMATS:
        for time_fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(f"{date_str} {time_str}", f"{date_fmt} {time_fmt}")
            except ValueError:
                continue
    return None


def _split_sender_and_text(rest: str) -> tuple[str, str] | None:
    """None se la riga non ha la forma "Mittente: testo": probabile evento di
    sistema (es. cambio icona del gruppo) da scartare, non un messaggio reale.
    """
    if ": " not in rest:
        return None
    sender, _, text = rest.partition(": ")
    if not sender or len(sender) > _MAX_SENDER_LENGTH:
        return None
    return sender, text


def _finalize(pending: _PendingMessage, source: MessageSource) -> IncomingMessage:
    text = pending.text.strip()
    is_media_placeholder = any(placeholder in text for placeholder in _MEDIA_PLACEHOLDERS)
    return IncomingMessage(
        message_id=str(uuid.uuid4()),
        source=source,
        sender=pending.sender,
        text=text,
        timestamp=pending.timestamp,
        is_truncated=is_media_placeholder,
    )


def parse_whatsapp_export(
    raw_text: str, source: MessageSource = MessageSource.CHAT_IMPORT
) -> list[IncomingMessage]:
    messages: list[IncomingMessage] = []
    pending: _PendingMessage | None = None

    for line in raw_text.splitlines():
        match = _IOS_PATTERN.match(line) or _ANDROID_PATTERN.match(line)
        if match is not None:
            if pending is not None:
                messages.append(_finalize(pending, source))
                pending = None

            timestamp = _parse_timestamp(match.group("date"), match.group("time"))
            split = _split_sender_and_text(match.group("rest"))
            if timestamp is None or split is None:
                continue  # riga di sistema o data non riconosciuta: non un messaggio

            sender, text = split
            pending = _PendingMessage(sender=sender, text=text, timestamp=timestamp)
        elif pending is not None and line.strip():
            pending.text += "\n" + line  # continuazione di un messaggio multi-riga

    if pending is not None:
        messages.append(_finalize(pending, source))

    return messages
