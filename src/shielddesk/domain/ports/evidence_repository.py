from typing import Protocol

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.evidence_record import EvidenceRecord
from shielddesk.domain.entities.incoming_message import IncomingMessage


class EvidenceRepositoryPort(Protocol):
    """Persistenza delle prove. L'implementazione reale cifra sempre i dati a riposo.

    Salva sia il messaggio originale sia l'esito dell'analisi (EvidenceRecord),
    non il solo risultato: senza il messaggio non si può ricostruire un report
    leggibile ("chi ha detto cosa").
    """

    async def store(self, message: IncomingMessage, analysis: AnalysisResult) -> str:
        """Salva messaggio+analisi e restituisce l'evidence_id assegnato."""
        ...

    async def get(self, evidence_id: str) -> EvidenceRecord | None: ...

    async def list_all(self) -> list[EvidenceRecord]: ...
