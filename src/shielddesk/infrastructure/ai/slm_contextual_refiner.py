"""Adapter che espone il tier-3 SLM come `ContextualRefinerPort`.

Traduce il contratto dell'SlmAnalyzer (che *solleva* `SlmAnalysisUnavailable` quando
il modello non è disponibile) in quello della porta di dominio (che *restituisce
None* per dire "tieni il tier precedente"). Così l'applicazione dipende solo dalla
porta e non conosce le eccezioni dell'infrastruttura, e il contratto fail-safe
(ANALYSIS.md §H4) resta rispettato: un problema del modello non fa mai crashare
l'analisi della chat, al massimo la lascia al risultato del tier veloce.
"""

from __future__ import annotations

from dataclasses import dataclass

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.conversation_context import ConversationContext
from shielddesk.infrastructure.ai.slm_analyzer import SlmAnalysisUnavailable, SlmAnalyzer
from shielddesk.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SlmContextualRefiner:
    analyzer: SlmAnalyzer

    async def refine(
        self,
        message: IncomingMessage,
        base: AnalysisResult,
        context: ConversationContext,
    ) -> AnalysisResult | None:
        try:
            return await self.analyzer.analyze(message, context=context)
        except SlmAnalysisUnavailable:
            logger.warning(
                "slm_refine_unavailable",
                message_id=message.message_id,
                fallback_tier=base.tier.value,
            )
            return None
