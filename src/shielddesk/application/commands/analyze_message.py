from dataclasses import dataclass

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.ports.analyzer import AnalyzerPort
from shielddesk.domain.ports.evidence_repository import EvidenceRepositoryPort


@dataclass(frozen=True, slots=True)
class AnalyzeMessageCommand:
    """Use case minimo di Fase 1: analizza un messaggio e salva il risultato.

    Il flusso completo (normalizzazione da notifica reale, cifratura, report)
    arriva in Fase 2+; qui si esercita solo l'attraversamento dei layer con
    adapter fake, per validare che dominio/applicazione/infrastruttura si
    compongano correttamente.
    """

    analyzer: AnalyzerPort
    evidence_repository: EvidenceRepositoryPort

    async def execute(self, message: IncomingMessage) -> str:
        result = await self.analyzer.analyze(message)
        return await self.evidence_repository.store(message, result)
