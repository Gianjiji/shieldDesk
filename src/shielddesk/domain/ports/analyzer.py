from typing import Protocol

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage


class AnalyzerPort(Protocol):
    """Analizza un messaggio e produce un AnalysisResult.

    Implementazioni reali (tier regole/ONNX/SLM) vivono in infrastructure/ai;
    i test usano sempre un analyzer fake/mock, mai il modello reale.
    """

    async def analyze(self, message: IncomingMessage) -> AnalysisResult: ...
