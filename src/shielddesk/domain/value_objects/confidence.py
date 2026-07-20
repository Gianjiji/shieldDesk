from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Confidence:
    """Punteggio di confidenza calibrato in [0.0, 1.0]. Mai presentato come certezza."""

    value: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(f"Confidence deve essere in [0.0, 1.0], ricevuto: {self.value}")
