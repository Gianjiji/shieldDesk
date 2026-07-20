from dataclasses import dataclass

from shielddesk.application.commands.analyze_message import AnalyzeMessageCommand
from shielddesk.domain.ports.notification_source import NotificationSourcePort


@dataclass(frozen=True, slots=True)
class ProcessIncomingMessagesCommand:
    """Drena la sorgente di notifiche ed esegue analisi+salvataggio per ogni messaggio."""

    notification_source: NotificationSourcePort
    analyze_message: AnalyzeMessageCommand

    async def execute(self) -> list[str]:
        evidence_ids = []
        async for message in self.notification_source.listen():
            evidence_id = await self.analyze_message.execute(message)
            evidence_ids.append(evidence_id)
        return evidence_ids
