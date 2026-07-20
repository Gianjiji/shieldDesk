from enum import StrEnum


class ThreatCategory(StrEnum):
    """Categorie di minaccia riconosciute dalla pipeline di analisi."""

    INSULT = "insult"
    EXCLUSION = "exclusion"
    THREAT = "threat"
    BLACKMAIL = "blackmail"
    HATE = "hate"
    SELF_HARM = "self_harm"
