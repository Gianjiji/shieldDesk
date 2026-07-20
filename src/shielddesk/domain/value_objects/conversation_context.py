from dataclasses import dataclass, field

from shielddesk.domain.entities.incoming_message import IncomingMessage


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Finestra dei messaggi che precedono quello da analizzare, nell'ordine in cui
    sono comparsi nella conversazione.

    Serve a valutare un messaggio *dentro* il thread invece che in isolamento: chi
    reagisce a chi, sarcasmo o battute tra pari, una frase offensiva *citata* per
    denunciarla, l'escalation progressiva. È proprio questo contesto che permette al
    tier SLM di ridurre i falsi positivi (es. la vittima che si difende) senza
    perdere le minacce che diventano chiare solo nella sequenza.
    """

    preceding: tuple[IncomingMessage, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return len(self.preceding) == 0
