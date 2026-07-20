from typing import Protocol

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.conversation_context import ConversationContext


class ContextualRefinerPort(Protocol):
    """Secondo passaggio *contestuale* dell'analisi (tier SLM, ANALYSIS.md §K).

    Rivaluta un messaggio già segnalato dal tier veloce, questa volta leggendolo
    dentro la conversazione (`ConversationContext`), per correggere i falsi
    positivi che un classificatore riga-per-riga non può vedere.

    Contratto fail-safe (ANALYSIS.md §H3/§H4): se il modello non è disponibile o
    non produce un risultato valido, il metodo restituisce `None` — significa
    "tieni il risultato del tier precedente", mai un'eccezione da propagare né un
    risultato inventato.
    """

    async def refine(
        self,
        message: IncomingMessage,
        base: AnalysisResult,
        context: ConversationContext,
    ) -> AnalysisResult | None:
        ...
