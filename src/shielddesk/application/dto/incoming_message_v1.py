"""Serializzazione JSON di IncomingMessage (contratto interno a EvidenceRecord)."""

from datetime import datetime
from typing import Any

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource


def to_dict(message: IncomingMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "source": message.source.value,
        "sender": message.sender,
        "text": message.text,
        "timestamp": message.timestamp.isoformat(),
        "is_truncated": message.is_truncated,
    }


def from_dict(data: dict[str, Any]) -> IncomingMessage:
    return IncomingMessage(
        message_id=data["message_id"],
        source=MessageSource(data["source"]),
        sender=data["sender"],
        text=data["text"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        is_truncated=data["is_truncated"],
    )
