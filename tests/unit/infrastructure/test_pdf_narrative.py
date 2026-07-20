"""Report narrativo (relazione): la parte discorsiva mette in risalto i messaggi
critici/alti; la cronologia completa resta, nelle ultime pagine. Test sulle
funzioni pure (deterministiche) + smoke che il PDF si generi anche con caratteri
insidiosi (`<`, `&`) che romperebbero il parser di reportlab senza escaping.
"""

from pathlib import Path

from shielddesk.infrastructure.reporting.pdf_report import (
    narrative_intro,
    participants,
    render_pdf,
    risk_counts,
    select_highlights,
)
from shielddesk.infrastructure.reporting.report_row import ReportRow


def _row(sender: str, text: str, ts: str, risk: str) -> ReportRow:
    return ReportRow(
        sender_label=sender, text=text, timestamp=ts, risk_level=risk, tier="fast", model_id="m"
    )


_ROWS = [
    _row("Mario", "ciao a tutti", "2024-03-12T21:04", "SAFE"),
    _row("Ignoto", "ti ammazzo se parli", "2024-03-12T21:07", "CRITICAL"),
    _row("Ignoto", "sei un idiota", "2024-03-12T21:08", "HIGH"),
    _row("Mario", "smettila", "2024-03-12T21:09", "MEDIUM"),
]


def test_risk_counts() -> None:
    counts = risk_counts(_ROWS)
    assert counts == {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 1, "LOW": 0, "SAFE": 1}


def test_participants_unique_in_order() -> None:
    assert participants(_ROWS) == ["Mario", "Ignoto"]


def test_select_highlights_only_critical_and_high_in_order() -> None:
    highlights = select_highlights(_ROWS)
    assert [h.risk_level for h in highlights] == ["CRITICAL", "HIGH"]
    assert [h.text for h in highlights] == ["ti ammazzo se parli", "sei un idiota"]


def test_narrative_intro_mentions_counts_and_participants() -> None:
    intro = narrative_intro(_ROWS)
    assert "4 messaggio/i" in intro
    assert "1 messaggio/i di gravità CRITICA" in intro
    assert "1 di gravità ALTA" in intro
    assert "Mario" in intro and "Ignoto" in intro


def test_narrative_intro_no_highlights() -> None:
    safe_only = [_row("Mario", "ciao", "2024-03-12T21:04", "SAFE")]
    intro = narrative_intro(safe_only)
    assert "non ha evidenziato messaggi di gravità critica o alta" in intro


def test_render_pdf_survives_special_characters(tmp_path: Path) -> None:
    tricky = [
        _row("a<b", "5 < 3 & tu > me", "2024-03-12T21:04", "CRITICAL"),
        _row("normale", "testo «con» virgolette", "2024-03-12T21:05", "SAFE"),
    ]
    out = tmp_path / "report.pdf"
    result = render_pdf(tricky, out, title="Report <test> & Co", redacted=False)
    assert result == out
    assert out.exists() and out.stat().st_size > 0
    assert out.read_bytes().startswith(b"%PDF")


def test_render_pdf_empty_rows(tmp_path: Path) -> None:
    out = tmp_path / "empty.pdf"
    render_pdf([], out, title="Vuoto", redacted=True)
    assert out.exists() and out.stat().st_size > 0
