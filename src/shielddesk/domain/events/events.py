from dataclasses import dataclass
from datetime import datetime

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage


@dataclass(frozen=True, slots=True)
class MessageReceived:
    message: IncomingMessage
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisCompleted:
    result: AnalysisResult
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class HighRiskDetected:
    result: AnalysisResult
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ModelFailed:
    message_id: str
    reason: str
    occurred_at: datetime
