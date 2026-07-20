import asyncio
import sys
from pathlib import Path

import pytest

from shielddesk.infrastructure.ai.slm.protocol import SlmRequest, WorkerState
from shielddesk.infrastructure.ai.slm.worker_client import SlmWorkerClient

_FIXTURE = Path(__file__).resolve().parent.parent.parent / "fixtures" / "fake_slm_worker.py"


def _command(mode: str) -> list[str]:
    return [sys.executable, str(_FIXTURE), mode]


@pytest.mark.asyncio
async def test_analyze_normal_roundtrip() -> None:
    client = SlmWorkerClient(command=_command("normal"))
    assert client.state == WorkerState.UNLOADED

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is not None
    assert response.request_id == "r1"
    assert response.risk_level == "HIGH"
    assert client.state == WorkerState.READY

    await client.unload()
    assert client.state == WorkerState.UNLOADED


@pytest.mark.asyncio
async def test_request_timeout_kills_process_and_sets_failed() -> None:
    client = SlmWorkerClient(command=_command("hang"), request_timeout_s=0.5)

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is None
    assert client.state == WorkerState.FAILED


@pytest.mark.asyncio
async def test_startup_timeout_sets_failed() -> None:
    client = SlmWorkerClient(command=_command("no_ready"), startup_timeout_s=0.5)

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is None
    assert client.state == WorkerState.FAILED


@pytest.mark.asyncio
async def test_invalid_json_response_returns_none_but_worker_stays_ready() -> None:
    client = SlmWorkerClient(command=_command("garbage"))

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is None
    # il worker stesso è vivo e ha risposto (male): non è un crash di processo,
    # quindi resta READY invece di essere considerato FAILED.
    assert client.state == WorkerState.READY

    await client.unload()


@pytest.mark.asyncio
async def test_non_utf8_response_returns_none_without_crashing() -> None:
    """Regressione: byte non-UTF-8 sullo stdout del worker (es. diagnostica nativa
    di llama.cpp) devono degradare a None, non far propagare UnicodeDecodeError al
    chiamante — contratto fail-safe §H4 ('mai un crash')."""
    client = SlmWorkerClient(command=_command("bad_utf8"))

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is None
    assert client.state == WorkerState.READY

    await client.unload()


@pytest.mark.asyncio
async def test_worker_crash_returns_none_and_sets_failed() -> None:
    client = SlmWorkerClient(command=_command("crash"))

    response = await client.analyze(SlmRequest(request_id="r1", text="ciao"))

    assert response is None
    assert client.state == WorkerState.FAILED


@pytest.mark.asyncio
async def test_idle_timeout_triggers_unload_before_next_request() -> None:
    client = SlmWorkerClient(command=_command("normal"), idle_timeout_s=0.0)

    first = await client.analyze(SlmRequest(request_id="r1", text="ciao"))
    assert first is not None
    first_state_after = client.state
    assert first_state_after == WorkerState.READY

    # idle_timeout_s=0.0: qualunque intervallo supera la soglia, quindi la
    # prossima chiamata deve scaricare e riavviare il processo da zero.
    second = await client.analyze(SlmRequest(request_id="r2", text="ciao ancora"))
    assert second is not None
    assert client.state == WorkerState.READY

    await client.unload()


@pytest.mark.asyncio
async def test_concurrent_requests_are_serialized_not_colliding() -> None:
    """Regressione: due o più richieste concorrenti sullo stesso worker non devono
    collidere sulla pipe condivisa ('readuntil() called while another coroutine is
    already waiting'). Il lock le serializza e ognuna riceve la propria risposta.

    Senza il lock questa gather() solleva RuntimeError o mescola le risposte.
    """
    client = SlmWorkerClient(command=_command("normal"))
    requests = [SlmRequest(request_id=f"r{i}", text="ciao") for i in range(5)]

    results = await asyncio.gather(*(client.analyze(req) for req in requests))

    assert all(r is not None for r in results)
    assert sorted(r.request_id for r in results if r is not None) == [
        "r0", "r1", "r2", "r3", "r4",
    ]
    await client.unload()
