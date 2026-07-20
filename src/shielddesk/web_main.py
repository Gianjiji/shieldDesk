"""Entrypoint dell'applicazione web ShieldDesk.

Sostituisce `shielddesk.main` (UI QML/PySide6, mai verificata su un display
reale) con un server locale che espone la stessa app come web responsive,
utilizzabile dal browser di qualunque dispositivo.

Resta offline e locale: il server ascolta su 127.0.0.1 di default e non
effettua alcuna chiamata di rete in uscita. Il container, la cassaforte e i
command applicativi sono identici alla versione desktop.
"""

from __future__ import annotations

import os
import threading
import webbrowser

import uvicorn

from shielddesk.infrastructure.config.container import build_container
from shielddesk.infrastructure.logging import configure_logging, get_logger
from shielddesk.presentation.web.app import create_app


def _open_browser(url: str) -> None:
    """Apre il browser di default poco dopo l'avvio del server, senza bloccarlo.
    Disattivabile con SHIELDDESK_NO_BROWSER=1 (utile in ambienti headless/CI).
    """
    if os.environ.get("SHIELDDESK_NO_BROWSER"):
        return
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)

    host = os.environ.get("SHIELDDESK_HOST", "127.0.0.1")
    port = int(os.environ.get("SHIELDDESK_PORT", "8765"))

    # Difesa DNS-rebinding: accetta solo l'header Host corrispondente all'indirizzo
    # di bind (più gli alias locali). Se si sceglie 0.0.0.0 (esposizione a tutte le
    # interfacce, es. per aprire l'app dal telefono in LAN) la protezione non può
    # sapere quale host userà il client: la si disattiva, ma esplicitamente e con
    # un avviso, perché è una scelta consapevole di superficie d'attacco più ampia.
    if host == "0.0.0.0":  # noqa: S104 — opt-in esplicito all'esposizione LAN
        allowed_hosts: list[str] = ["*"]
        logger.warning("web_host_check_disabled", host=host, reason="bind_all_interfaces")
    else:
        allowed_hosts = sorted({host, "127.0.0.1", "localhost"})

    # Il container è costruito dal lifespan della app, nel thread dell'event loop,
    # perché la connessione SQLCipher è legata al thread che la crea.
    app = create_app(build_container, allowed_hosts=allowed_hosts)

    url = f"http://{host}:{port}/"
    logger.info("web_app_starting", url=url)
    print(f"\n  ShieldDesk è in esecuzione: {url}\n  (premi Ctrl+C per chiudere)\n")  # noqa: T201
    _open_browser(url)

    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
