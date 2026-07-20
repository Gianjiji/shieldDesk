from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Astrae l'orario corrente per rendere il dominio testabile deterministicamente."""

    def now(self) -> datetime: ...
