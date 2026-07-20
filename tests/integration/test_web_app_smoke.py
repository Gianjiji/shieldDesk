"""Smoke test dell'applicazione web: verifica che le rotte REST espongano lo
stesso flusso della vecchia UI QML (dashboard, cassaforte, analisi chat) e che
la SPA statica sia servita.

Analogo di test_app_smoke.py ma per il nuovo entrypoint web (FastAPI), che
sostituisce la UI QML/PySide6.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.config.container import build_container
from shielddesk.presentation.web.app import create_app


def _client(tmp_path: Path) -> TestClient:
    # analyzer=MockAnalyzer(): lo smoke test verifica l'attraversamento dei layer, non il modello.
    # Va usato come context manager (`with _client(...) as client:`) perché il
    # container — e con esso la connessione SQLCipher — è creato nello startup del
    # lifespan, che TestClient esegue solo dentro il `with`.
    def factory() -> object:
        return build_container(vault_dir=tmp_path / "vault", analyzer=MockAnalyzer())

    # base_url con Host locale: TrustedHostMiddleware rifiuta il default "testserver".
    return TestClient(create_app(factory), base_url="http://127.0.0.1")  # type: ignore[arg-type]


def test_static_spa_is_served(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        index = client.get("/")
        assert index.status_code == 200
        assert "ShieldDesk" in index.text
        assert client.get("/app.js").status_code == 200
        assert client.get("/styles.css").status_code == 200


def test_dashboard_status(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        body = client.get("/api/status").json()
        assert "connesso" in body["statusText"]


def test_vault_demo_and_process(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/vault/evidence").json()["count"] == 0

        demo = client.post("/api/vault/demo-evidence").json()
        assert demo["count"] == 1

        processed = client.post("/api/vault/process-simulated").json()
        assert processed["count"] >= 2


def test_chat_analyze_and_save_evidence(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.post(
            "/api/chat/analyze",
            json={
                "rawText": (
                    "[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?\n"
                    "[24/07/26, 09:17:12] Sconosciuto: Stai attento perché ti ammazzo\n"
                )
            },
        )
        data = resp.json()
        assert data["count"] == 2

        saved = client.post("/api/chat/save-evidence", json={"index": 0}).json()
        assert saved["timeline"][0]["saved"] is True

        # Il salvataggio è arrivato fino alla cassaforte cifrata.
        assert client.get("/api/vault/evidence").json()["count"] == 1


def test_analyze_chat_via_file_upload(tmp_path: Path) -> None:
    export = (
        "[24/07/26, 09:15:03] Mario Rossi: Ciao come stai?\n"
        "[24/07/26, 09:17:12] Sconosciuto: Stai attento perché ti ammazzo\n"
    ).encode()
    with _client(tmp_path) as client:
        resp = client.post(
            "/api/chat/analyze-file",
            files={"file": ("whatsapp.txt", export, "text/plain")},
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


def test_analyze_chat_file_rejects_non_utf8(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        resp = client.post(
            "/api/chat/analyze-file",
            files={"file": ("bad.txt", b"\xff\xfe\x00rubbish", "application/octet-stream")},
        )
        assert resp.status_code == 400


def test_export_requires_password(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        client.post("/api/vault/demo-evidence")
        resp = client.post("/api/vault/export", json={"zipPassword": "", "redact": True})
        assert resp.status_code == 400
