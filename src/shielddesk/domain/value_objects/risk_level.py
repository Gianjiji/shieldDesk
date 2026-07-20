from enum import IntEnum


class RiskLevel(IntEnum):
    """Livello di rischio di un'analisi, dal più sicuro al più critico."""

    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
