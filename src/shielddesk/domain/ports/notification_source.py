from collections.abc import AsyncIterator
from typing import Protocol

from shielddesk.domain.entities.incoming_message import IncomingMessage


class NotificationSourcePort(Protocol):
    """Sorgente di messaggi in arrivo (notifiche di sistema, o adapter fake per i test).

    Le capability variano per piattaforma: un adapter che non supporta la rimozione
    deve dichiararlo tramite ``can_remove`` invece di sollevare un'eccezione.
    """

    @property
    def can_remove(self) -> bool: ...

    @property
    def can_reply(self) -> bool: ...

    def listen(self) -> AsyncIterator[IncomingMessage]: ...

    async def remove_notification(self, message_id: str) -> bool: ...
