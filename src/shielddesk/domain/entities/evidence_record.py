from dataclasses import dataclass
from datetime import datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Unità persistita nella cassaforte: messaggio originale + esito dell'analisi.

    Introdotta per correggere un gap tra ANALYSIS.md §G (che prevedeva sempre
    questa entità) e l'implementazione delle Fasi 2-8, che salvava solo
    AnalysisResult — impedendo di sapere, a posteriori, chi avesse detto cosa.
    """

    evidence_id: str
    message: IncomingMessage
    analysis: AnalysisResult
    stored_at: datetime
    user_annotation: str | None = None
