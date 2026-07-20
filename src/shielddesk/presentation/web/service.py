"""Servizio applicativo per il layer web.

Rimpiazza i tre ViewModel QML (Dashboard, Vault, ChatAnalysis) con un'unica
facciata async che i router FastAPI possono attendere direttamente, senza
`asyncio.run()` per chiamata (che nei ViewModel bloccava la UI a ogni azione).

Regole invariate rispetto alla UI precedente:
- nessuna business logic qui: si delega ai command applicativi;
- cosa salvare come prova o esportare resta una scelta esplicita dell'utente
  (ANALYSIS.md §H7): `analyze_chat` non salva nulla in automatico.

Lo stato della timeline chat (quali messaggi sono stati analizzati e quali
salvati) è tenuto in memoria in una singola istanza di servizio: l'app è
single-user e gira in locale, esattamente come lo era la sessione desktop.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from shielddesk.application.commands.analyze_chat import AnalyzeChatCommand, ChatTimelineEntry
from shielddesk.application.commands.analyze_message import AnalyzeMessageCommand
from shielddesk.application.commands.export_professional_report import (
    ExportProfessionalReportCommand,
)
from shielddesk.application.commands.export_report_minimal import ExportReportMinimalCommand
from shielddesk.application.commands.process_incoming_messages import (
    ProcessIncomingMessagesCommand,
)
from shielddesk.application.dto.analysis_result_v1 import to_dict as analysis_to_dict
from shielddesk.domain.entities.analysis_result import AnalysisResult
from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.infrastructure.config.container import Container


def _analysis_summary(analysis: AnalysisResult) -> dict[str, object]:
    """Vista sintetica di un'analisi per l'UI: livello di rischio leggibile più
    il dettaglio versionato (schema condiviso con Android) per chi lo vuole.
    """
    categories = [
        {"category": score.category.value, "confidence": round(score.confidence.value, 4)}
        for score in analysis.categories
    ]
    top = max(analysis.categories, key=lambda s: s.confidence.value, default=None)
    return {
        "riskLevel": analysis.risk_level.name,
        "riskLevelValue": int(analysis.risk_level),
        "tier": analysis.tier.value,
        "modelId": analysis.model_id,
        "topCategory": top.category.value if top is not None else None,
        "topConfidence": round(top.confidence.value, 4) if top is not None else None,
        "categories": categories,
        "detail": analysis_to_dict(analysis),
    }


class ShieldDeskService:
    """Facciata unica per l'app web: incapsula il container e lo stato di sessione."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._analyze_message = AnalyzeMessageCommand(
            analyzer=container.analyzer,
            evidence_repository=container.evidence_repository,
        )
        self._process_incoming = ProcessIncomingMessagesCommand(
            notification_source=container.notification_source,
            analyze_message=self._analyze_message,
        )
        self._export_minimal = ExportReportMinimalCommand(
            evidence_repository=container.evidence_repository,
        )
        self._export_professional = ExportProfessionalReportCommand()
        self._analyze_chat = AnalyzeChatCommand(
            analyzer=container.analyzer,
            refiner=container.contextual_refiner,
        )

        # Stato di sessione della schermata "Analisi chat".
        self._entries: list[ChatTimelineEntry] = []
        self._saved_indices: set[int] = set()
        # Serializza le operazioni che leggono/scrivono lo stato di sessione della
        # chat: l'app è single-user, ma due richieste sovrapposte (es. un upload
        # lento via SLM + un'altra analisi) si racchierebbero su self._entries, con
        # una che restituisce la timeline dell'altra. Il lock le mette in coda.
        self._chat_lock = asyncio.Lock()

    # ------------------------------------------------------------------ Dashboard
    def status(self) -> dict[str, object]:
        source = self._container.notification_source
        flags = (("rimozione", source.can_remove), ("risposta", source.can_reply))
        capabilities = [name for name, available in flags if available]
        caps = ", ".join(capabilities) if capabilities else "nessuna azione"
        return {
            "statusText": f"Adapter di sviluppo connesso — capability: {caps}",
            "canRemove": source.can_remove,
            "canReply": source.can_reply,
        }

    # ---------------------------------------------------------------------- Vault
    async def vault_evidence(self) -> dict[str, object]:
        records = await self._container.evidence_repository.list_all()
        items = [
            {
                "evidenceId": record.evidence_id,
                "sender": record.message.sender,
                "text": record.message.text,
                "storedAt": record.stored_at.isoformat(timespec="seconds"),
                "timestamp": record.message.timestamp.isoformat(timespec="minutes"),
                "analysis": _analysis_summary(record.analysis),
            }
            for record in records
        ]
        return {"count": len(items), "items": items}

    async def add_demo_evidence(self) -> dict[str, object]:
        message = IncomingMessage(
            message_id=str(uuid.uuid4()),
            source=MessageSource.MANUAL_PASTE,
            sender="demo",
            text="Messaggio di prova per la cassaforte",
            timestamp=datetime.now(UTC),
        )
        await self._analyze_message.execute(message)
        return await self.vault_evidence()

    async def process_simulated_messages(self) -> dict[str, object]:
        await self._process_incoming.execute()
        return await self.vault_evidence()

    async def export_vault_minimal(self, output_name: str) -> dict[str, str]:
        """L'input è trattato come un semplice NOME file, non un percorso: il client
        non può scegliere dove scrivere sul filesystem. Il file finisce sempre
        dentro ./reports, con estensione .json. Difesa da path traversal (un client
        forgiato, o una richiesta cross-site che superasse le altre difese, non deve
        poter scrivere un file arbitrario altrove).
        """
        reports_dir = (Path.cwd() / "reports").resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)
        # Rifiuto esplicito (non sanitizzazione silenziosa): qualunque separatore di
        # percorso, riferimento a parent o byte nullo è un input sospetto da bloccare.
        invalid = (
            not output_name
            or output_name in {".", ".."}
            or "/" in output_name
            or "\\" in output_name
            or ".." in output_name
            or "\x00" in output_name
            or output_name != Path(output_name).name
            or not output_name.endswith(".json")
        )
        if invalid:
            raise ValueError("Nome file non valido: usa un semplice nome che termina in .json.")
        target = (reports_dir / output_name).resolve()
        if target.parent != reports_dir:  # cintura e bretelle contro la traversal
            raise ValueError("Percorso di destinazione non consentito.")
        result_path = await self._export_minimal.execute(target)
        return {"path": str(result_path)}

    async def export_vault_report(self, zip_password: str, redact: bool) -> dict[str, str]:
        if not zip_password:
            raise ValueError("La password dello ZIP è obbligatoria.")
        records = await self._container.evidence_repository.list_all()
        if not records:
            raise ValueError("La cassaforte è vuota: niente da esportare.")
        report_entries = [(record.message, record.analysis) for record in records]
        output_dir = Path.cwd() / "reports"
        zip_path = await self._export_professional.execute(
            report_entries,
            output_dir=output_dir,
            zip_password=zip_password,
            redact=redact,
            title="Report ShieldDesk — Cassaforte",
        )
        return {"path": str(zip_path)}

    # -------------------------------------------------------------- Analisi chat
    def _timeline(self) -> list[dict[str, object]]:
        return [
            {
                "index": index,
                "sender": entry.message.sender,
                "text": entry.message.text,
                "timestamp": entry.message.timestamp.isoformat(timespec="minutes"),
                "analysis": _analysis_summary(entry.analysis),
                "saved": index in self._saved_indices,
            }
            for index, entry in enumerate(self._entries)
        ]

    def chat_timeline(self) -> dict[str, object]:
        return {"count": len(self._entries), "timeline": self._timeline()}

    # Limite di dimensione dell'incolla: evita che un input enorme generi lavoro
    # illimitato (molte inferenze ONNX + un passaggio SLM lento per ogni messaggio
    # segnalato). ~200k caratteri coprono chat molto lunghe restando ragionevoli.
    MAX_RAW_TEXT_CHARS = 200_000

    async def analyze_chat(self, raw_text: str) -> dict[str, object]:
        if len(raw_text) > self.MAX_RAW_TEXT_CHARS:
            raise ValueError(
                f"Testo troppo lungo (max {self.MAX_RAW_TEXT_CHARS} caratteri). "
                "Analizza la conversazione a blocchi."
            )
        async with self._chat_lock:
            self._entries = await self._analyze_chat.execute(
                raw_text, source=MessageSource.MANUAL_PASTE
            )
            self._saved_indices = set()
            return self.chat_timeline()

    # Limite in byte per l'upload di file: un file di chat testuale reale sta
    # ampiamente sotto; oltre, si rifiuta con un errore chiaro invece di caricare
    # in memoria un file enorme.
    MAX_UPLOAD_BYTES = 1_000_000

    async def analyze_chat_file(self, content: bytes) -> dict[str, object]:
        if len(content) > self.MAX_UPLOAD_BYTES:
            raise ValueError(
                f"File troppo grande (max {self.MAX_UPLOAD_BYTES // 1000} KB). "
                "Esporta o incolla la conversazione a blocchi."
            )
        # Gli export WhatsApp sono UTF-8 (a volte con BOM). Nessun altra codifica
        # "indovinata": meglio un errore chiaro che un testo corrotto.
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Il file non è un testo UTF-8 valido: esporta la chat come file di testo."
            ) from exc
        return await self.analyze_chat(text)

    async def save_chat_evidence(self, index: int) -> dict[str, object]:
        async with self._chat_lock:
            if index < 0 or index >= len(self._entries):
                raise ValueError("Indice del messaggio non valido.")
            entry = self._entries[index]
            await self._container.evidence_repository.store(entry.message, entry.analysis)
            self._saved_indices.add(index)
            return self.chat_timeline()

    async def export_chat_report(self, zip_password: str, redact: bool) -> dict[str, str]:
        async with self._chat_lock:
            if not self._entries:
                raise ValueError("Nessuna chat analizzata da esportare.")
            if not zip_password:
                raise ValueError("La password dello ZIP è obbligatoria.")
            output_dir = Path.cwd() / "reports"
            report_entries = [(entry.message, entry.analysis) for entry in self._entries]
            zip_path = await self._export_professional.execute(
                report_entries, output_dir=output_dir, zip_password=zip_password, redact=redact
            )
            return {"path": str(zip_path)}

    # ----------------------------------------------------------------- Risk meta
    @staticmethod
    def risk_levels() -> list[dict[str, object]]:
        return [{"name": level.name, "value": int(level)} for level in RiskLevel]
