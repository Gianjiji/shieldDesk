"""Test di sicurezza del layer web (non solo funzionali):

- difesa DNS-rebinding via validazione dell'header Host: un sito malevolo aperto
  nel browser non deve poter leggere le prove del minore rebindando su 127.0.0.1;
- path traversal su export-minimal: il client non deve poter scrivere file fuori
  dalla cartella reports.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from shielddesk.infrastructure.ai.mock_analyzer import MockAnalyzer
from shielddesk.infrastructure.config.container import build_container
from shielddesk.presentation.web.app import create_app


def _client(tmp_path: Path) -> TestClient:
    def factory() -> object:
        return build_container(vault_dir=tmp_path / "vault", analyzer=MockAnalyzer())

    return TestClient(create_app(factory), base_url="http://127.0.0.1")  # type: ignore[arg-type]


def test_local_host_header_is_accepted(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        assert client.get("/api/status", headers={"host": "localhost"}).status_code == 200
        assert client.get("/api/status", headers={"host": "127.0.0.1"}).status_code == 200


def test_forged_host_header_is_rejected(tmp_path: Path) -> None:
    """Richiesta con Host di un dominio d'attacco (scenario DNS-rebinding): 400.

    Senza questa difesa un sito esterno potrebbe leggere /api/vault/evidence.
    """
    with _client(tmp_path) as client:
        evidence = client.get("/api/vault/evidence", headers={"host": "evil.example.com"})
        assert evidence.status_code == 400
        status = client.get("/api/status", headers={"host": "attacker.test"})
        assert status.status_code == 400


def test_export_minimal_rejects_path_traversal(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        client.post("/api/vault/demo-evidence")
        for evil in ("../../etc/evil.json", "/tmp/evil.json", "..\\..\\evil.json", "evil.txt"):
            resp = client.post("/api/vault/export-minimal", json={"outputPath": evil})
            assert resp.status_code == 400, f"non rifiutato: {evil}"

        # Il file NON deve esistere fuori dalla cartella reports.
        assert not Path("/tmp/evil.json").exists()


def test_export_minimal_accepts_plain_filename(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    with _client(tmp_path) as client:
        client.post("/api/vault/demo-evidence")
        resp = client.post("/api/vault/export-minimal", json={"outputPath": "report.json"})
        assert resp.status_code == 200
        written = Path(resp.json()["path"]).resolve()
        assert written.parent == (tmp_path / "reports").resolve()


def test_analyze_chat_rejects_oversized_input(tmp_path: Path) -> None:
    # Difesa da self-DoS: un incolla enorme non deve avviare lavoro illimitato.
    with _client(tmp_path) as client:
        huge = "[12/03/24, 21:04] x: ciao\n" * 20000  # ~500k caratteri
        resp = client.post("/api/chat/analyze", json={"rawText": huge})
        assert resp.status_code == 400
