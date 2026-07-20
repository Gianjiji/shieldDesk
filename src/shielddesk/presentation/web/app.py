"""FastAPI app factory per la UI web di ShieldDesk.

Serve una SPA responsive statica (nessuna build, nessuna dipendenza CDN: tutto
offline) e un'API REST che avvolge i command applicativi tramite
`ShieldDeskService`. Il binding di default è 127.0.0.1: l'app resta locale e
offline come la versione desktop (cfr. tests/integration/test_no_network_access.py).

Il container (e quindi la connessione SQLCipher, legata al thread che la crea)
viene costruito nella fase di *startup* del lifespan, cioè nello stesso thread
dell'event loop che poi serve le richieste. Così l'affinità di thread della
connessione sqlite è sempre rispettata, sia sotto uvicorn sia nei test
(`TestClient(app)` usato come context manager).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from shielddesk.infrastructure.config.container import Container
from shielddesk.infrastructure.logging import get_logger
from shielddesk.presentation.web.service import ShieldDeskService

logger = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# Solo host locali per default. Non è autenticazione (l'app è single-user in
# locale) ma difesa da DNS-rebinding: un sito malevolo aperto nel browser non può
# rebindare il proprio dominio su 127.0.0.1 e leggere le prove del minore, perché
# l'header Host non sarebbe tra questi. Le prove in cassaforte sono l'asset più
# sensibile: vanno protette anche dal browser stesso.
_DEFAULT_ALLOWED_HOSTS = ("127.0.0.1", "localhost")


class AnalyzeChatRequest(BaseModel):
    rawText: str


class SaveEvidenceRequest(BaseModel):
    index: int


class ExportRequest(BaseModel):
    zipPassword: str
    redact: bool = True


class ExportMinimalRequest(BaseModel):
    outputPath: str


def create_app(
    container_factory: Callable[[], Container],
    allowed_hosts: list[str] | None = None,
) -> FastAPI:
    """`container_factory` viene invocata una sola volta, allo startup, nel thread
    dell'event loop: non passare un container già costruito altrove, o la
    connessione sqlite finirebbe legata a un thread diverso da quello che serve
    le richieste.

    `allowed_hosts` limita l'header Host accettato (difesa DNS-rebinding). Default:
    solo host locali. Se si espone l'app in LAN (SHIELDDESK_HOST diverso da
    localhost) l'entrypoint deve passare qui l'host consentito.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.service = ShieldDeskService(container_factory())
        logger.info("web_app_ready")
        yield

    app = FastAPI(title="ShieldDesk", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=list(allowed_hosts) if allowed_hosts else list(_DEFAULT_ALLOWED_HOSTS),
    )

    def svc() -> ShieldDeskService:
        return cast(ShieldDeskService, app.state.service)

    # ------------------------------------------------------------------ Dashboard
    @app.get("/api/status")
    def status() -> dict[str, object]:
        return svc().status()

    @app.get("/api/risk-levels")
    def risk_levels() -> dict[str, object]:
        return {"levels": ShieldDeskService.risk_levels()}

    # ---------------------------------------------------------------------- Vault
    @app.get("/api/vault/evidence")
    async def vault_evidence() -> dict[str, object]:
        return await svc().vault_evidence()

    @app.post("/api/vault/demo-evidence")
    async def add_demo_evidence() -> dict[str, object]:
        return await svc().add_demo_evidence()

    @app.post("/api/vault/process-simulated")
    async def process_simulated() -> dict[str, object]:
        return await svc().process_simulated_messages()

    @app.post("/api/vault/export")
    async def export_vault(req: ExportRequest) -> dict[str, str]:
        try:
            return await svc().export_vault_report(req.zipPassword, req.redact)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/vault/export-minimal")
    async def export_vault_minimal(req: ExportMinimalRequest) -> dict[str, str]:
        try:
            return await svc().export_vault_minimal(req.outputPath)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # -------------------------------------------------------------- Analisi chat
    @app.get("/api/chat/timeline")
    def chat_timeline() -> dict[str, object]:
        return svc().chat_timeline()

    @app.post("/api/chat/analyze")
    async def analyze_chat(req: AnalyzeChatRequest) -> dict[str, object]:
        try:
            return await svc().analyze_chat(req.rawText)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/chat/analyze-file")
    async def analyze_chat_file(file: Annotated[UploadFile, File()]) -> dict[str, object]:
        content = await file.read()
        try:
            return await svc().analyze_chat_file(content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/chat/save-evidence")
    async def save_chat_evidence(req: SaveEvidenceRequest) -> dict[str, object]:
        try:
            return await svc().save_chat_evidence(req.index)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/chat/export")
    async def export_chat(req: ExportRequest) -> dict[str, str]:
        try:
            return await svc().export_chat_report(req.zipPassword, req.redact)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------- Statici
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    logger.info("web_app_created")
    return app
