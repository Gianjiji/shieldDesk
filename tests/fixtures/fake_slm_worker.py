"""Worker SLM fittizio per testare SlmWorkerClient senza il modello reale (~1GB).

Modalità (primo argomento):
  normal   — READY, poi risponde a ogni richiesta con un JSON valido fisso.
  hang     — READY, poi non risponde mai (per testare il timeout di richiesta).
  no_ready — non stampa mai READY_SENTINEL (per testare il timeout di avvio).
  garbage  — READY, poi risponde con testo non-JSON.
  bad_utf8 — READY, poi risponde con byte non-UTF-8 (diagnostica nativa simulata).
  crash    — READY, poi esce immediatamente alla prima richiesta.
"""

import sys

from shielddesk.infrastructure.ai.slm.protocol import READY_SENTINEL, SlmRequest, SlmResponse


def main(mode: str) -> None:
    if mode == "no_ready":
        sys.stdin.readline()  # resta in vita senza mai annunciarsi pronto
        return

    print(READY_SENTINEL, flush=True)

    if mode == "hang":
        sys.stdin.readline()  # legge la richiesta ma non risponde mai
        import time

        time.sleep(3600)
        return

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        request = SlmRequest.from_json_line(line)

        if mode == "crash":
            sys.exit(1)
        elif mode == "garbage":
            print("questo non è JSON valido", flush=True)
        elif mode == "bad_utf8":
            # byte grezzi non decodificabili come UTF-8, seguiti da newline
            sys.stdout.buffer.write(b"\xff\xfe non-utf8\n")
            sys.stdout.buffer.flush()
        else:  # normal
            response = SlmResponse(
                request_id=request.request_id,
                risk_level="HIGH",
                category="threat",
                confidence=0.83,
            )
            print(response.to_json_line(), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
