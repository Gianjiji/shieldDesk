"""Composition root: unico punto della codebase che sa quali implementazioni concrete
esistono dietro ai port del dominio. I ViewModel ricevono il container già assemblato
e non istanziano mai direttamente un adapter o un repository.
"""

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shielddesk.domain.entities.incoming_message import IncomingMessage
from shielddesk.domain.ports.analyzer import AnalyzerPort
from shielddesk.domain.ports.clock import ClockPort
from shielddesk.domain.ports.contextual_refiner import ContextualRefinerPort
from shielddesk.domain.ports.evidence_repository import EvidenceRepositoryPort
from shielddesk.domain.ports.notification_source import NotificationSourcePort
from shielddesk.domain.value_objects.message_source import MessageSource
from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.ai.onnx_analyzer import OnnxToxicityAnalyzer
from shielddesk.infrastructure.ai.slm.worker_client import SlmWorkerClient
from shielddesk.infrastructure.ai.slm_analyzer import SlmAnalyzer, default_worker_command
from shielddesk.infrastructure.ai.slm_contextual_refiner import SlmContextualRefiner
from shielddesk.infrastructure.config.clock import SystemClock
from shielddesk.infrastructure.config.settings import resolve_dev_passphrase
from shielddesk.infrastructure.crypto.vault_key import VaultKeyService
from shielddesk.infrastructure.logging import get_logger
from shielddesk.infrastructure.notifications.fake_adapter import FakeNotificationAdapter
from shielddesk.infrastructure.persistence.sqlcipher_repository import (
    SQLCipherEvidenceRepository,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_VAULT_DIR = Path.cwd() / ".shielddesk_vault"
_DEFAULT_MODEL_DIR = _PROJECT_ROOT / "models" / "toxic-xlm-roberta-onnx"
_DEFAULT_SLM_MODEL_PATH = (
    _PROJECT_ROOT / "models" / "qwen2.5-1.5b-instruct-gguf" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Container:
    """Bundle immutabile delle dipendenze condivise dall'applicazione."""

    notification_source: NotificationSourcePort
    analyzer: AnalyzerPort
    evidence_repository: EvidenceRepositoryPort
    clock: ClockPort
    # Tier-3 contestuale (SLM): opzionale. None quando il modello GGUF non è
    # presente o è disabilitato — in quel caso l'analisi chat resta al solo tier
    # veloce, senza rivalutazione contestuale.
    contextual_refiner: ContextualRefinerPort | None = None


def _default_simulated_messages() -> list[IncomingMessage]:
    """Messaggi di demo per la vertical slice: uno sicuro, uno che il mock classifica a rischio."""
    now = datetime.now(UTC)
    return [
        IncomingMessage(
            message_id=str(uuid.uuid4()),
            source=MessageSource.WHATSAPP_NOTIFICATION,
            sender="Gruppo classe 3A",
            text="Ci vediamo domani per il compito di matematica?",
            timestamp=now,
        ),
        IncomingMessage(
            message_id=str(uuid.uuid4()),
            source=MessageSource.WHATSAPP_NOTIFICATION,
            sender="Sconosciuto",
            text="Stai attento perché ti ammazzo se lo dici a qualcuno",
            timestamp=now,
        ),
    ]


def _build_analyzer(model_dir: Path) -> AnalyzerPort:
    """Fail-safe (ANALYSIS.md §H4): se il modello ONNX manca o non carica, degrada
    al MockAnalyzer invece di far fallire l'avvio dell'app. Mai un crash silenzioso
    né un risultato inventato: il degrado è loggato esplicitamente.
    """
    if not (model_dir / "model.onnx").exists():
        logger.warning("onnx_model_missing", model_dir=str(model_dir), fallback="mock_analyzer")
        return MockAnalyzer()
    try:
        return OnnxToxicityAnalyzer(model_dir)
    except Exception:
        logger.exception("onnx_model_load_failed", fallback="mock_analyzer")
        return MockAnalyzer()


def _build_contextual_refiner(model_path: Path) -> ContextualRefinerPort | None:
    """Costruisce il refiner SLM tier-3 se il modello GGUF è presente, altrimenti None.

    Costruire il client NON avvia il processo worker né importa `llama_cpp` nel
    processo genitore: l'avvio è pigro, alla prima richiesta, e avviene in un
    sottoprocesso (ADR-004). Quindi è sicuro anche se il modello è enorme o
    `llama-cpp-python` non fosse caricabile qui.

    Disattivabile con SHIELDDESK_DISABLE_SLM=1 (utile su macchine deboli, dove il
    passaggio SLM per messaggio segnalato è troppo lento).
    """
    if os.environ.get("SHIELDDESK_DISABLE_SLM"):
        logger.info("slm_refiner_disabled", reason="SHIELDDESK_DISABLE_SLM")
        return None
    if not model_path.exists():
        logger.info("slm_model_missing", model_path=str(model_path), fallback="fast_tier_only")
        return None
    worker_client = SlmWorkerClient(default_worker_command(model_path))
    return SlmContextualRefiner(SlmAnalyzer(worker_client))


def _build_evidence_repository(vault_dir: Path, passphrase: str) -> EvidenceRepositoryPort:
    """`sqlcipher3` è una dipendenza obbligatoria del progetto (verificata installabile
    senza compilazione in Fase 5): un suo import fallito farebbe già fallire l'avvio
    dell'app molto prima di arrivare qui (import a livello di modulo in
    sqlcipher_repository.py), quindi non tentiamo un fallback "silenzioso" per quel
    caso — sarebbe irraggiungibile in pratica.

    Un errore da SQLCipherEvidenceRepository() (chiave sbagliata, file corrotto,
    keyvault.json ed evidence.db disallineati dopo un ripristino parziale) NON va
    mai assorbito in un fallback che crea un vault nuovo vuoto: l'utente vedrebbe
    una cassaforte apparentemente vuota invece di un errore, il che è peggio di un
    crash esplicito. L'unico fallback applicativo resta l'EncryptedSqliteRepository
    di Fase 2, disponibile per iniezione esplicita nei test, non scelto qui in automatico.
    """
    vault_dir.mkdir(parents=True, exist_ok=True)
    key_service = VaultKeyService(vault_dir / "keyvault.json")

    if key_service.exists:
        master_key = key_service.unlock_with_passphrase(passphrase)
    else:
        master_key, recovery_key = key_service.setup(passphrase)
        print(  # noqa: T201 — sostituto dev della schermata di onboarding (non ancora costruita)
            "\n=== ShieldDesk: nuova cassaforte creata ===\n"
            "Conserva questa recovery key: e' l'UNICO modo per recuperare i dati se "
            "dimentichi la passphrase. Non verra' mostrata di nuovo.\n"
            f"Recovery key: {recovery_key}\n"
            "============================================\n"
        )

    return SQLCipherEvidenceRepository(vault_dir / "evidence.db", key=master_key)


def build_container(
    seed_messages: list[IncomingMessage] | None = None,
    vault_dir: Path | None = None,
    model_dir: Path | None = None,
    analyzer: AnalyzerPort | None = None,
    contextual_refiner: ContextualRefinerPort | None = None,
    slm_model_path: Path | None = None,
) -> Container:
    """Assembla il container per la Fase 5: persistenza SQLCipher con hash chain e
    key management a doppio sblocco (passphrase o recovery key), fast path ONNX
    reale quando disponibile, notifiche fake, SLM disponibile come componente
    standalone (non ancora instradato automaticamente — vedi docs/phase-4-report.md).
    """
    passphrase, is_ephemeral = resolve_dev_passphrase()
    if is_ephemeral:
        logger.warning(
            "dev_passphrase_ephemeral",
            hint="imposta SHIELDDESK_DEV_PASSPHRASE per persistere i dati tra esecuzioni",
        )

    resolved_messages = (
        seed_messages if seed_messages is not None else _default_simulated_messages()
    )
    resolved_analyzer = analyzer if analyzer is not None else _build_analyzer(
        model_dir or _DEFAULT_MODEL_DIR
    )
    resolved_refiner = (
        contextual_refiner
        if contextual_refiner is not None
        else _build_contextual_refiner(slm_model_path or _DEFAULT_SLM_MODEL_PATH)
    )

    return Container(
        notification_source=FakeNotificationAdapter(resolved_messages),
        analyzer=resolved_analyzer,
        evidence_repository=_build_evidence_repository(
            vault_dir or _DEFAULT_VAULT_DIR, passphrase
        ),
        clock=SystemClock(),
        contextual_refiner=resolved_refiner,
    )
