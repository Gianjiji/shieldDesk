"""Analisi di una chat incollata o importata (Fase 7): produce una timeline con
l'esito per ogni messaggio, senza salvare nulla in automatico — la selezione di
quali messaggi diventano prova resta una decisione esplicita dell'utente
(ANALYSIS.md §H7).

Cascata a due tier (ANALYSIS.md §K):
1. il tier veloce (`analyzer`) classifica ogni messaggio in isolamento;
2. per i soli messaggi segnalati (rischio > SAFE) — cioè i candidati falso
   positivo — un refiner contestuale opzionale li rivaluta DENTRO la
   conversazione (finestra dei messaggi precedenti). Se il refiner non è
   configurato o non è disponibile a runtime, si tiene il risultato del tier
   veloce (fail-safe §H4). L'SLM non è mai il primo passaggio.
"""

from dataclasses import dataclass

from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.ports.analyzer import AnalyzerPort
from shielddesk.domain.ports.contextual_refiner import ContextualRefinerPort
from shielddesk.domain.value_objects.conversation_context import ConversationContext
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.chat_import.whatsapp_parser import parse_whatsapp_export

DEFAULT_CONTEXT_WINDOW = 6


@dataclass(frozen=True, slots=True)
class ChatTimelineEntry:
    message: IncomingMessage
    analysis: AnalysisResult


@dataclass(frozen=True, slots=True)
class AnalyzeChatCommand:
    analyzer: AnalyzerPort
    refiner: ContextualRefinerPort | None = None
    context_window: int = DEFAULT_CONTEXT_WINDOW

    async def execute(
        self, raw_text: str, source: MessageSource = MessageSource.CHAT_IMPORT
    ) -> list[ChatTimelineEntry]:
        messages = parse_whatsapp_export(raw_text, source=source)
        entries = []
        for index, message in enumerate(messages):
            analysis = await self.analyzer.analyze(message)
            analysis = await self._maybe_refine(analysis, messages, index)
            entries.append(ChatTimelineEntry(message=message, analysis=analysis))
        return entries

    async def _maybe_refine(
        self,
        base: AnalysisResult,
        messages: list[IncomingMessage],
        index: int,
    ) -> AnalysisResult:
        """Rivaluta nel contesto solo i messaggi già segnalati dal tier veloce:
        sono quelli su cui un falso positivo è possibile. I SAFE non si toccano
        (nessun costo SLM) e non si può creare un falso negativo declassando un
        messaggio che il tier veloce non aveva segnalato.
        """
        if self.refiner is None or base.risk_level <= RiskLevel.SAFE:
            return base
        window = messages[max(0, index - self.context_window) : index]
        context = ConversationContext(preceding=tuple(window))
        refined = await self.refiner.refine(messages[index], base, context)
        return refined if refined is not None else base
