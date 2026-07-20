"""Redazione dei nomi nel report (ANALYSIS.md §G/§H6): sostituisce i mittenti
con pseudonimi coerenti in tutto il report. Non tocca mai il contenuto dei
messaggi — la redazione riguarda l'identità, non le prove in sé.
"""

from __future__ import annotations


class RedactionService:
    def __init__(self) -> None:
        self._mapping: dict[str, str] = {}

    def pseudonym_for(self, sender: str) -> str:
        if sender not in self._mapping:
            self._mapping[sender] = f"Persona {len(self._mapping) + 1}"
        return self._mapping[sender]

    @property
    def mapping(self) -> dict[str, str]:
        """Copia della mappa nome reale → pseudonimo, utile per un log di audit
        separato (mai incluso nel report esportato)."""
        return dict(self._mapping)
