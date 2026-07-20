from datetime import UTC, datetime


class SystemClock:
    """Implementazione reale di ClockPort basata sull'orologio di sistema."""

    def now(self) -> datetime:
        return datetime.now(UTC)
