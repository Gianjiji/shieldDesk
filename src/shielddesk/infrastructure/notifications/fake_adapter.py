from collections.abc import AsyncIterator

from shielddesk.domain.entities.incoming_message import IncomingMessage


class FakeNotificationAdapter:
    """Adapter di test: espone una coda di messaggi predisposta invece di leggere da WinRT.

    Implementa NotificationSourcePort per struttura, senza ereditarne direttamente
    (i port sono Protocol strutturali: nessun import di infrastruttura nel dominio).
    """

    def __init__(self, messages: list[IncomingMessage] | None = None) -> None:
        self._messages = messages or []
        self._removed_ids: set[str] = set()

    @property
    def can_remove(self) -> bool:
        return True

    @property
    def can_reply(self) -> bool:
        return False

    async def listen(self) -> AsyncIterator[IncomingMessage]:
        """Drena la coda una volta sola, come un vero stream di notifiche non ripete la storia."""
        while self._messages:
            yield self._messages.pop(0)

    async def remove_notification(self, message_id: str) -> bool:
        self._removed_ids.add(message_id)
        return True

    @property
    def removed_ids(self) -> frozenset[str]:
        return frozenset(self._removed_ids)
