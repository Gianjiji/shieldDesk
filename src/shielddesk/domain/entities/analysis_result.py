from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from shielddesk.domain.value_objects.confidence import Confidence
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.domain.value_objects.threat_category import ThreatCategory


class AnalysisTier(StrEnum):
    """Livello della pipeline che ha prodotto il risultato."""

    RULES = "rules"
    FAST = "fast"
    SLM = "slm"


@dataclass(frozen=True, slots=True)
class CategoryScore:
    """Confidenza per una singola categoria di minaccia."""

    category: ThreatCategory
    confidence: Confidence


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Esito dell'analisi di un IncomingMessage.

    Schema versionato per compatibilità cross-platform.
    """

    schema_version: str
    message_id: str
    tier: AnalysisTier
    model_id: str
    model_version: str
    prompt_version: str
    timestamp: datetime
    risk_level: RiskLevel
    categories: tuple[CategoryScore, ...] = field(default_factory=tuple)
    latency_ms: float = 0.0
