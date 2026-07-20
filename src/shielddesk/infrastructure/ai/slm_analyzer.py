"""Tier 3 (ANALYSIS.md §K): SLM locale per i casi ambigui, mai come primo passaggio."""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier, CategoryScore
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.confidence import Confidence
from shielddesk.domain.value_objects.conversation_context import ConversationContext
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.domain.value_objects.threat_category import ThreatCategory
from shielddesk.infrastructure.ai.slm.protocol import ContextTurn, SlmRequest
from shielddesk.infrastructure.ai.slm.worker_client import SlmWorkerClient

SCHEMA_VERSION = "1.0"
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
PROMPT_VERSION = "1.0"


class SlmAnalysisUnavailable(Exception):
    """Nessun risultato valido dall'SLM (timeout/crash/JSON invalido/RiskLevel sconosciuto).

    Il chiamante deve tornare al tier precedente (ANALYSIS.md §H3/§H4), mai
    ignorarla in silenzio né inventare un risultato al suo posto.
    """


def default_worker_command(model_path: Path) -> list[str]:
    return [sys.executable, "-m", "shielddesk.infrastructure.ai.slm.worker_main", str(model_path)]


class SlmAnalyzer:
    def __init__(self, worker_client: SlmWorkerClient) -> None:
        self._worker_client = worker_client

    async def analyze(
        self, message: IncomingMessage, context: ConversationContext | None = None
    ) -> AnalysisResult:
        start = time.perf_counter()
        context_turns = (
            tuple(ContextTurn(sender=m.sender, text=m.text) for m in context.preceding)
            if context is not None
            else ()
        )
        request = SlmRequest(
            request_id=str(uuid.uuid4()),
            text=message.text,
            sender=message.sender,
            context=context_turns,
        )
        response = await self._worker_client.analyze(request)
        if response is None:
            raise SlmAnalysisUnavailable(f"nessuna risposta valida per {message.message_id}")

        try:
            risk_level = RiskLevel[response.risk_level]
        except KeyError as exc:
            raise SlmAnalysisUnavailable(
                f"risk_level sconosciuto: {response.risk_level!r}"
            ) from exc

        categories: tuple[CategoryScore, ...] = ()
        if response.category != "none":
            try:
                categories = (
                    CategoryScore(
                        category=ThreatCategory(response.category),
                        confidence=Confidence(response.confidence),
                    ),
                )
            except ValueError as exc:
                raise SlmAnalysisUnavailable(
                    f"category/confidence non validi: {response.category!r}"
                ) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        return AnalysisResult(
            schema_version=SCHEMA_VERSION,
            message_id=message.message_id,
            tier=AnalysisTier.SLM,
            model_id=MODEL_ID,
            model_version="Q4_K_M",
            prompt_version=PROMPT_VERSION,
            timestamp=message.timestamp,
            risk_level=risk_level,
            categories=categories,
            latency_ms=latency_ms,
        )
