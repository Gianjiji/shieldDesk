from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReportRow:
    """Forma minima e primitiva usata dal renderer: tiene infrastructure/reporting
    disaccoppiato dai DTO applicativi (es. ChatTimelineEntry)."""

    sender_label: str
    text: str
    timestamp: str
    risk_level: str
    tier: str
    model_id: str
