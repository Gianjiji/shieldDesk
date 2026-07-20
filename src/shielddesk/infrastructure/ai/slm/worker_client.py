"""Gestore lato genitore del worker SLM: avvio, richieste con timeout, unload per
inattività (ADR-004). Parametrizzato sul comando da lanciare così i test di
lifecycle possono usare un worker fittizio, senza il modello reale da ~1GB.
"""

from __future__ import annotations

import asyncio
import json
import time

from shielddesk.infrastructure.ai.slm.protocol import (
    READY_SENTINEL,
    SlmRequest,
    SlmResponse,
    WorkerState,
)
from shielddesk.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SlmWorkerClient:
    """None dai metodi pubblici significa esito AMBIGUO/non analizzato: mai un
    risultato inventato (ANALYSIS.md §H3/§H4). Il chiamante deve trattarlo come
    "torna al tier precedente", non come un errore da propagare.
    """

    def __init__(
        self,
        command: list[str],
        startup_timeout_s: float = 60.0,
        request_timeout_s: float = 20.0,
        idle_timeout_s: float = 300.0,
    ) -> None:
        self._command = command
        self._startup_timeout_s = startup_timeout_s
        self._request_timeout_s = request_timeout_s
        self._idle_timeout_s = idle_timeout_s
        self._process: asyncio.subprocess.Process | None = None
        self._state = WorkerState.UNLOADED
        self._last_used = 0.0
        # Il worker è un unico sottoprocesso con una sola pipe stdin/stdout: può
        # servire una richiesta per volta. Senza serializzazione, due richieste
        # HTTP che escalano all'SLM in parallelo farebbero due readline()
        # concorrenti sullo stesso stream ("readuntil() called while another
        # coroutine is already waiting"). Il lock le mette in coda.
        self._lock = asyncio.Lock()

    @property
    def state(self) -> WorkerState:
        return self._state

    async def analyze(self, request: SlmRequest) -> SlmResponse | None:
        async with self._lock:
            if self._should_unload_for_inactivity():
                await self._unload_locked()

            if self._state in (WorkerState.UNLOADED, WorkerState.FAILED):
                started = await self._start()
                if not started:
                    return None

            return await self._send_request(request)

    async def unload(self) -> None:
        async with self._lock:
            await self._unload_locked()

    async def _unload_locked(self) -> None:
        """Corpo di unload SENZA acquisire il lock: chiamato o dall'interno di
        analyze() (che il lock lo tiene già) o da unload() (che lo acquisisce).
        `asyncio.Lock` non è rientrante, quindi separare i due casi evita il deadlock.
        """
        if self._process is None:
            self._state = WorkerState.UNLOADED
            return
        self._state = WorkerState.UNLOADING
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except TimeoutError:
            self._process.kill()
            await self._process.wait()
        self._process = None
        self._state = WorkerState.UNLOADED

    def _should_unload_for_inactivity(self) -> bool:
        return (
            self._state == WorkerState.READY
            and (time.monotonic() - self._last_used) > self._idle_timeout_s
        )

    async def _start(self) -> bool:
        self._state = WorkerState.STARTING
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            logger.exception("slm_worker_spawn_failed")
            self._state = WorkerState.FAILED
            return False

        assert self._process.stdout is not None
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self._startup_timeout_s
            )
        except TimeoutError:
            logger.warning("slm_worker_startup_timeout")
            await self._kill()
            return False

        if line.decode("utf-8").strip() != READY_SENTINEL:
            logger.warning("slm_worker_startup_unexpected_output")
            await self._kill()
            return False

        self._state = WorkerState.READY
        self._last_used = time.monotonic()
        return True

    async def _send_request(self, request: SlmRequest) -> SlmResponse | None:
        assert self._process is not None
        assert self._process.stdin is not None
        assert self._process.stdout is not None

        self._state = WorkerState.BUSY
        try:
            self._process.stdin.write((request.to_json_line() + "\n").encode("utf-8"))
            await self._process.stdin.drain()
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self._request_timeout_s
            )
        except TimeoutError:
            logger.warning("slm_request_timeout", request_id=request.request_id)
            await self._kill()
            return None
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("slm_worker_pipe_broken", request_id=request.request_id)
            await self._kill()
            return None
        except ValueError:
            # readline() rilancia ValueError se una riga supera il limite di buffer
            # di asyncio (worker che emette un output enorme senza newline): trattalo
            # come un worker impazzito, non lasciar propagare l'eccezione al chiamante.
            logger.warning("slm_worker_line_too_long", request_id=request.request_id)
            await self._kill()
            return None

        if not line:
            logger.warning("slm_worker_closed_unexpectedly", request_id=request.request_id)
            await self._kill()
            return None

        try:
            response = SlmResponse.from_json_line(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError):
            # UnicodeDecodeError: byte non-UTF-8 sullo stdout del worker (es.
            # diagnostica nativa di llama.cpp interlacciata). Contratto fail-safe
            # (§H4): il tier SLM non deve mai crashare il chiamante — None significa
            # "torna al tier precedente", non un'eccezione da propagare.
            logger.warning("slm_invalid_response", request_id=request.request_id)
            self._state = WorkerState.READY
            self._last_used = time.monotonic()
            return None

        if response.error is not None:
            logger.warning("slm_worker_reported_error", request_id=request.request_id)
            self._state = WorkerState.READY
            self._last_used = time.monotonic()
            return None

        self._state = WorkerState.READY
        self._last_used = time.monotonic()
        return response

    async def _kill(self) -> None:
        if self._process is not None:
            try:
                self._process.kill()
            except ProcessLookupError:
                pass  # già terminato da solo (es. crash): nulla da uccidere
            else:
                await self._process.wait()
            self._process = None
        self._state = WorkerState.FAILED
