"""Protocollo JSON su stdin/stdout tra il processo genitore e il worker SLM (ADR-004)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class WorkerState(StrEnum):
    """Stati del ciclo di vita del worker process (ANALYSIS.md §6.3/ADR-004).

    UNLOADED è lo stato iniziale/finale naturale (processo mai avviato o
    terminato per inattività): un'aggiunta rispetto alle sole transizioni
    intermedie elencate in ANALYSIS.md, necessaria per rappresentare "nessun
    processo in esecuzione" senza sovraccaricare il significato di FAILED.
    """

    UNLOADED = "unloaded"
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    UNLOADING = "unloading"
    FAILED = "failed"


READY_SENTINEL = "__WORKER_READY__"


@dataclass(frozen=True, slots=True)
class ContextTurn:
    """Un messaggio precedente della conversazione, passato al worker come contesto.

    È un dato da leggere, mai un'istruzione da eseguire: il worker lo delimita e lo
    tratta come tale (difesa da prompt-injection, cfr. worker_main.SYSTEM_PROMPT).
    """

    sender: str
    text: str


@dataclass(frozen=True, slots=True)
class SlmRequest:
    request_id: str
    text: str
    # Contesto opzionale: mittente del messaggio target e turni precedenti. I campi
    # hanno default vuoti così le richieste "riga singola" (tier senza contesto) e i
    # payload JSON delle versioni precedenti restano validi.
    sender: str = ""
    context: tuple[ContextTurn, ...] = ()

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "request_id": self.request_id,
                "text": self.text,
                "sender": self.sender,
                "context": [{"sender": t.sender, "text": t.text} for t in self.context],
            }
        )

    @staticmethod
    def from_json_line(line: str) -> SlmRequest:
        data = json.loads(line)
        context = tuple(
            ContextTurn(sender=turn.get("sender", ""), text=turn["text"])
            for turn in data.get("context", [])
        )
        return SlmRequest(
            request_id=data["request_id"],
            text=data["text"],
            sender=data.get("sender", ""),
            context=context,
        )


@dataclass(frozen=True, slots=True)
class SlmResponse:
    request_id: str
    risk_level: str
    category: str
    confidence: float
    error: str | None = None

    def to_json_line(self) -> str:
        payload: dict[str, Any] = {
            "request_id": self.request_id,
            "risk_level": self.risk_level,
            "category": self.category,
            "confidence": self.confidence,
            "error": self.error,
        }
        return json.dumps(payload)

    @staticmethod
    def from_json_line(line: str) -> SlmResponse:
        data = json.loads(line)
        return SlmResponse(
            request_id=data["request_id"],
            risk_level=data["risk_level"],
            category=data["category"],
            confidence=data["confidence"],
            error=data.get("error"),
        )
