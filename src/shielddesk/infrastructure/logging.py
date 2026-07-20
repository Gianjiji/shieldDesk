"""Logging redatto: nessun contenuto di messaggio finisce mai nei log.

Il processor `_redact_message_fields` rimuove per nome i campi che potrebbero
contenere testo dell'utente, indipendentemente da chi chiama il logger — questo
è l'unico punto della codebase che deve garantire la regola "niente testo in
chiaro nei log" (§17 di prompt.md), quindi non è delegabile ai singoli call site.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import structlog

_SENSITIVE_FIELD_NAMES = frozenset({"text", "message_text", "sender", "content", "body"})
_REDACTED = "[REDACTED]"


def _redact_message_fields(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in event_dict:
        if key.lower() in _SENSITIVE_FIELD_NAMES:
            event_dict[key] = _REDACTED
    return event_dict


def configure_logging() -> None:
    """Configura structlog con redazione obbligatoria. Chiamare una sola volta all'avvio."""
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_message_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
