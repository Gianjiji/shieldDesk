"""Report PDF (ADR-010): leggibile per un adulto/tutore, non un documento legale.

Struttura (aggiornata): una prima parte NARRATIVA — relazione discorsiva che
riepiloga l'analisi ed evidenzia i messaggi di gravità critica e alta, pensata
per essere allegata a un'eventuale segnalazione — seguita, nelle ultime pagine,
dalla cronologia COMPLETA di tutti i messaggi.

Il testo narrativo è generato in modo deterministico dai dati reali (conteggi,
partecipanti, messaggi testuali): nessun contenuto inventato dal modello, scelta
voluta per un documento che può finire in una denuncia. Include sempre il
disclaimer (ANALYSIS.md §25): l'esito AI non va trattato come verità assoluta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from shielddesk.infrastructure.reporting.report_row import ReportRow

_BRAND = colors.HexColor("#5f6fb0")
_BRAND_ACCENT = colors.HexColor("#6b8cff")
_INK_SOFT = colors.HexColor("#8a90a0")


def _draw_shield(c: pdfcanvas.Canvas, x: float, y: float, s: float) -> None:
    """Piccolo scudo con spunta (lo stesso logo dell'app), disegnato vettorialmente.
    `x, y` = angolo in alto a sinistra; lo scudo si sviluppa verso il basso.
    """
    path = c.beginPath()
    path.moveTo(x, y)
    path.lineTo(x + s, y)
    path.lineTo(x + s, y - 0.5 * s)
    path.lineTo(x + 0.5 * s, y - 1.15 * s)
    path.lineTo(x, y - 0.5 * s)
    path.close()
    c.setFillColor(_BRAND_ACCENT)
    c.drawPath(path, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    c.setLineWidth(s * 0.13)
    c.setLineCap(1)
    c.setLineJoin(1)
    c.lines([
        (x + 0.27 * s, y - 0.55 * s, x + 0.44 * s, y - 0.72 * s),
        (x + 0.44 * s, y - 0.72 * s, x + 0.75 * s, y - 0.34 * s),
    ])


class _BrandedCanvas(pdfcanvas.Canvas):  # type: ignore[misc]  # reportlab non ha stub tipizzati
    """Aggiunge a ogni pagina un'intestazione (logo + wordmark) e un piè di pagina
    (documento riservato + "Pagina X di Y"). Il totale pagine si conosce solo a
    fine documento, quindi si differisce il disegno al momento del salvataggio.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict[str, object]] = []

    def showPage(self) -> None:
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total: int) -> None:
        width, height = A4
        # Intestazione: logo + wordmark
        _draw_shield(self, 2 * cm, height - 1.0 * cm, 0.42 * cm)
        self.setFillColor(_BRAND)
        self.setFont("Helvetica-Bold", 9.5)
        self.drawString(2 * cm + 0.62 * cm, height - 1.32 * cm, "ShieldDesk")
        # Piè di pagina: filetto + testo
        self.setStrokeColor(colors.HexColor("#d7dbe6"))
        self.setLineWidth(0.5)
        self.line(2 * cm, 1.45 * cm, width - 2 * cm, 1.45 * cm)
        self.setFillColor(_INK_SOFT)
        self.setFont("Helvetica", 8)
        self.drawString(2 * cm, 1.05 * cm, "ShieldDesk · documento riservato, generato in locale")
        self.drawRightString(
            width - 2 * cm, 1.05 * cm, f"Pagina {self._pageNumber} di {total}"
        )

_DISCLAIMER = (
    "Questo report è generato da un'analisi automatica e assistita da modelli AI locali. "
    "Non è un accertamento legale né una prova di colpevolezza: i livelli di rischio sono "
    "stime probabilistiche, non certezze. Va sempre valutato da una persona adulta prima "
    "di qualunque decisione o segnalazione."
)

_RISK_HEX = {
    "SAFE": "#2e7d32",
    "LOW": "#9e9d24",
    "MEDIUM": "#ef6c00",
    "HIGH": "#c62828",
    "CRITICAL": "#8e0000",
}
_RISK_COLORS = {name: colors.HexColor(value) for name, value in _RISK_HEX.items()}
_RISK_TINT = {"CRITICAL": colors.HexColor("#fdecea"), "HIGH": colors.HexColor("#fff4e5")}

# Ordine di gravità decrescente, per riepiloghi ed evidenziazioni.
_RISK_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE")
_HIGHLIGHT_LEVELS = ("CRITICAL", "HIGH")


def _esc(text: str) -> str:
    """Neutralizza `< > &` prima di passarli a Paragraph: reportlab interpreta un
    mini-markup, quindi un messaggio come "5 < 3 & tu" romperebbe il parsing. Vale
    per QUALSIASI testo dell'utente che finisce in un Paragraph.
    """
    return escape(text)


def risk_counts(rows: list[ReportRow]) -> dict[str, int]:
    counts = dict.fromkeys(_RISK_ORDER, 0)
    for row in rows:
        if row.risk_level in counts:
            counts[row.risk_level] += 1
    return counts


def participants(rows: list[ReportRow]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows:
        if row.sender_label not in seen:
            seen.add(row.sender_label)
            ordered.append(row.sender_label)
    return ordered


def select_highlights(rows: list[ReportRow]) -> list[ReportRow]:
    """Messaggi di gravità critica e alta, in ordine cronologico (l'ordine di `rows`)."""
    return [row for row in rows if row.risk_level in _HIGHLIGHT_LEVELS]


def narrative_intro(rows: list[ReportRow]) -> str:
    """Paragrafo introduttivo, deterministico e fattuale."""
    counts = risk_counts(rows)
    people = participants(rows)
    total = len(rows)
    critical, high = counts["CRITICAL"], counts["HIGH"]

    who = ""
    if len(people) == 1:
        who = f" del mittente «{people[0]}»"
    elif len(people) > 1:
        who = f" tra {len(people)} partecipanti ({', '.join(people)})"

    when = ""
    if rows:
        first, last = rows[0].timestamp, rows[-1].timestamp
        when = f", nel periodo dal {first} al {last}" if first != last else f", del {first}"

    if critical or high:
        finding = (
            f"L'analisi ha evidenziato {critical} messaggio/i di gravità CRITICA e "
            f"{high} di gravità ALTA, riportati per esteso nella sezione seguente."
        )
    else:
        finding = "L'analisi non ha evidenziato messaggi di gravità critica o alta."

    return (
        f"La presente relazione documenta l'analisi automatica di {total} messaggio/i"
        f"{who}{when}. È destinata a offrire a un adulto una lettura sintetica dei "
        f"contenuti potenzialmente riconducibili a cyberbullismo e può essere allegata "
        f"a un'eventuale segnalazione. {finding} I livelli di rischio sono stime "
        f"automatiche e vanno sempre valutati da una persona."
    )


def _summary_table(rows: list[ReportRow], cell_style: ParagraphStyle) -> Table:
    counts = risk_counts(rows)
    data = [["Gravità", "Messaggi"]]
    for level in _RISK_ORDER:
        data.append([Paragraph(level, cell_style), Paragraph(str(counts[level]), cell_style)])
    table = Table(data, colWidths=[4 * cm, 3 * cm])
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#37474f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for index, level in enumerate(_RISK_ORDER, start=1):
        commands.append(("TEXTCOLOR", (0, index), (0, index), _RISK_COLORS[level]))
    table.setStyle(TableStyle(commands))
    return table


def _highlight_paragraphs(rows: list[ReportRow], body_style: ParagraphStyle) -> list[object]:
    highlights = select_highlights(rows)
    if not highlights:
        return [
            Paragraph("Non sono stati rilevati messaggi di gravità critica o alta.", body_style)
        ]
    story: list[object] = []
    for row in highlights:
        tint = _RISK_TINT.get(row.risk_level, colors.HexColor("#f5f5f5"))
        style = ParagraphStyle(
            f"hl_{row.risk_level}",
            parent=body_style,
            backColor=tint,
            borderColor=_RISK_COLORS[row.risk_level],
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=8,
        )
        story.append(
            Paragraph(
                f"<b>{_esc(row.timestamp)} — {_esc(row.sender_label)}</b> "
                f'<font color="{_RISK_HEX[row.risk_level]}"><b>[{row.risk_level}]</b></font>'
                f"<br/>«{_esc(row.text)}»",
                style,
            )
        )
    return story


def render_pdf(rows: list[ReportRow], output_path: Path, title: str, redacted: bool) -> Path:
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=9, leading=11)
    body_style = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    # Titolo e intestazioni nel colore del brand, per un aspetto coerente con l'app.
    styles["Title"].textColor = _BRAND
    styles["Title"].fontSize = 20
    for name in ("Heading2", "Heading3"):
        styles[name].textColor = _BRAND
        styles[name].spaceBefore = 6

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        title=title,
        author="ShieldDesk",
    )
    story: list[object] = [
        Paragraph(_esc(title), styles["Title"]),
        Paragraph(
            f"Generato il {datetime.now(UTC).strftime('%d/%m/%Y %H:%M UTC')}"
            f" — nomi {'redatti' if redacted else 'non redatti'}",
            styles["Normal"],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(_DISCLAIMER, cell_style),
        Spacer(1, 0.5 * cm),
    ]

    # --- Parte narrativa (relazione) ---
    story.append(Paragraph("Relazione di sintesi", styles["Heading2"]))
    # narrative_intro è testo semplice (contiene i nomi dei mittenti): va escapato
    # prima di darlo a Paragraph, che altrimenti interpreta un eventuale "<" come tag.
    story.append(Paragraph(_esc(narrative_intro(rows)), body_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Riepilogo per gravità", styles["Heading3"]))
    story.append(_summary_table(rows, cell_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Messaggi di gravità critica e alta", styles["Heading2"]))
    story.extend(_highlight_paragraphs(rows, body_style))

    # --- Cronologia completa: nelle ultime pagine ---
    story.append(PageBreak())
    story.append(Paragraph("Cronologia completa dei messaggi", styles["Heading2"]))
    story.append(Spacer(1, 0.2 * cm))

    table_data = [["Orario", "Mittente", "Messaggio", "Rischio", "Livello analisi"]]
    for row in rows:
        table_data.append(
            [
                Paragraph(_esc(row.timestamp), cell_style),
                Paragraph(_esc(row.sender_label), cell_style),
                Paragraph(_esc(row.text), cell_style),
                Paragraph(_esc(row.risk_level), cell_style),
                Paragraph(f"{_esc(row.tier)} ({_esc(row.model_id)})", cell_style),
            ]
        )

    col_widths = [2.6 * cm, 3 * cm, 6.5 * cm, 2 * cm, 3.5 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#37474f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for index, row in enumerate(rows, start=1):
        risk_color = _RISK_COLORS.get(row.risk_level)
        if risk_color is not None:
            style_commands.append(("TEXTCOLOR", (3, index), (3, index), risk_color))
    table.setStyle(TableStyle(style_commands))
    story.append(table)

    doc.build(story, canvasmaker=_BrandedCanvas)
    return output_path
