"""Cascata contestuale di AnalyzeChatCommand (ANALYSIS.md §K): il tier veloce
classifica riga per riga, il refiner rivaluta nel contesto SOLO i messaggi
segnalati, riducendo i falsi positivi. Coperto con stub deterministici, senza il
modello reale.
"""

from dataclasses import dataclass, field

import pytest

from shielddesk.application.commands.analyze_chat import AnalyzeChatCommand
from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.conversation_context import ConversationContext
from shielddesk.domain.value_objects.risk_level import RiskLevel

# Chat: uno sconosciuto minaccia, la vittima (Mario) reagisce difendendosi. Un
# classificatore riga-per-riga segnala ENTRAMBI; il contesto deve declassare la
# reazione della vittima.
CHAT = (
    "[12/03/24, 21:04] Mario: Ciao raga, ci vediamo domani?\n"
    "[12/03/24, 21:07] Sconosciuto: Stai attento perche ti ammazzo se lo dici\n"
    "[12/03/24, 21:09] Mario: Ma sei scemo? Smettila e lasciami in pace\n"
)


def _result(message: IncomingMessage, risk: RiskLevel, tier: AnalysisTier) -> AnalysisResult:
    return AnalysisResult(
        schema_version="1.0",
        message_id=message.message_id,
        tier=tier,
        model_id="stub",
        model_version="stub",
        prompt_version="stub",
        timestamp=message.timestamp,
        risk_level=risk,
        categories=(),
        latency_ms=0.0,
    )


@dataclass
class _FastTierStub:
    """Tier veloce: segnala (MEDIUM) ogni messaggio che contiene una parola dura,
    in isolamento — quindi anche la difesa della vittima ("scemo").
    """

    async def analyze(self, message: IncomingMessage) -> AnalysisResult:
        flagged = any(w in message.text.lower() for w in ("ammazzo", "scemo"))
        risk = RiskLevel.MEDIUM if flagged else RiskLevel.SAFE
        return _result(message, risk, AnalysisTier.FAST)


@dataclass
class _RefinerSpy:
    """Refiner contestuale finto: declassa a SAFE la difesa della vittima, tiene
    la minaccia. Registra le chiamate ricevute per verificare cosa viene escalato.
    """

    calls: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    async def refine(
        self,
        message: IncomingMessage,
        base: AnalysisResult,
        context: ConversationContext,
    ) -> AnalysisResult | None:
        self.calls.append((message.text, tuple(m.text for m in context.preceding)))
        if "scemo" in message.text.lower():  # vittima che si difende → falso positivo
            return _result(message, RiskLevel.SAFE, AnalysisTier.SLM)
        return _result(message, base.risk_level, AnalysisTier.SLM)  # minaccia confermata


@pytest.mark.asyncio
async def test_context_downgrades_victim_self_defense_false_positive() -> None:
    spy = _RefinerSpy()
    command = AnalyzeChatCommand(analyzer=_FastTierStub(), refiner=spy)

    entries = await command.execute(CHAT)
    by_sender_text = {(e.message.sender, e.message.text): e.analysis for e in entries}

    threat = by_sender_text[("Sconosciuto", "Stai attento perche ti ammazzo se lo dici")]
    defense = by_sender_text[("Mario", "Ma sei scemo? Smettila e lasciami in pace")]

    # Il tier veloce aveva segnalato entrambi; il contesto declassa solo la difesa.
    assert threat.risk_level is RiskLevel.MEDIUM
    assert threat.tier is AnalysisTier.SLM  # rivalutato ma confermato
    assert defense.risk_level is RiskLevel.SAFE  # falso positivo rimosso
    assert defense.tier is AnalysisTier.SLM


@pytest.mark.asyncio
async def test_safe_messages_are_not_escalated() -> None:
    spy = _RefinerSpy()
    command = AnalyzeChatCommand(analyzer=_FastTierStub(), refiner=spy)

    await command.execute(CHAT)

    # Il saluto benigno di Mario non è mai passato al refiner (nessun costo SLM).
    escalated_texts = {text for text, _ in spy.calls}
    assert "Ciao raga, ci vediamo domani?" not in escalated_texts
    assert escalated_texts == {
        "Stai attento perche ti ammazzo se lo dici",
        "Ma sei scemo? Smettila e lasciami in pace",
    }


@pytest.mark.asyncio
async def test_context_window_contains_preceding_messages() -> None:
    spy = _RefinerSpy()
    command = AnalyzeChatCommand(analyzer=_FastTierStub(), refiner=spy)

    await command.execute(CHAT)

    # La difesa di Mario (terzo messaggio) è stata rivalutata avendo davanti i due
    # messaggi precedenti, inclusa la minaccia.
    defense_call = next(c for c in spy.calls if "scemo" in c[0].lower())
    assert defense_call[1] == (
        "Ciao raga, ci vediamo domani?",
        "Stai attento perche ti ammazzo se lo dici",
    )


@pytest.mark.asyncio
async def test_refiner_none_keeps_fast_tier_result() -> None:
    """Fail-safe §H4: se il refiner non è disponibile (None) si tiene il tier veloce."""

    @dataclass
    class _UnavailableRefiner:
        async def refine(self, message, base, context):  # type: ignore[no-untyped-def]
            return None

    command = AnalyzeChatCommand(analyzer=_FastTierStub(), refiner=_UnavailableRefiner())
    entries = await command.execute(CHAT)
    threat = next(e for e in entries if "ammazzo" in e.message.text)

    assert threat.analysis.risk_level is RiskLevel.MEDIUM
    assert threat.analysis.tier is AnalysisTier.FAST  # non rivalutato


@pytest.mark.asyncio
async def test_no_refiner_behaves_like_before() -> None:
    command = AnalyzeChatCommand(analyzer=_FastTierStub())  # refiner=None (default)
    entries = await command.execute(CHAT)

    assert all(e.analysis.tier is AnalysisTier.FAST for e in entries)
