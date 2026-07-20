# Fase 8 — Report professionali: report di fine fase

Vedi `ANALYSIS.md` §H6/ADR-010/§M. Obiettivo: PDF, JSON, manifest, ZIP cifrato, redazione.

## Scelta di scope importante

Costruendo questa fase è emerso un vincolo reale nel modello dati: `AnalysisResult`,
l'unica cosa persistita nella cassaforte dalla Fase 2 in poi, **non porta con sé il
mittente né il testo originale del messaggio** — solo l'esito dell'analisi. Un report
"professionale" deve invece mostrare chi ha detto cosa. `ANALYSIS.md` §G aveva sempre
previsto un `EvidenceRecord` distinto (messaggio + risultato) come unità persistita, ma le
Fasi 2-7 hanno preso la scorciatoia di salvare `AnalysisResult` da solo.

Rifare da capo lo schema di persistenza (repository, DTO, hash chain, tutti i chiamanti)
in questa fase avrebbe ampliato molto lo scope. Ho scelto invece di costruire il report
professionale sui dati di una sessione di **Analisi chat** appena eseguita (Fase 7), che
ha già messaggio+analisi insieme in memoria (`ChatTimelineEntry`) — un flusso reale e
completo, senza toccare la persistenza esistente. **Il gap resta esplicito**: un "report
dalla cassaforte storica" con testo/mittente reali richiede prima quel refactor
(`EvidenceRecord`), pianificato come lavoro futuro, non nascosto.

## Changelog

- **`RedactionService`** (`domain/services/redaction.py`, dominio puro): pseudonimi
  coerenti per mittente ("Persona 1", "Persona 2", ...) in tutto il report — mai il
  contenuto dei messaggi, solo l'identità.
- **Rendering PDF** (`infrastructure/reporting/pdf_report.py`, ReportLab): tabella con
  orario/mittente/messaggio/rischio/livello di analisi, colori per livello di rischio,
  disclaimer esplicito in testa ("non è un accertamento legale... i livelli di rischio
  sono stime probabilistiche, non certezze") coerente con "non trattare il risultato AI
  come verità assoluta" di `ANALYSIS.md` §25.
- **Manifest** (`infrastructure/reporting/manifest.py`): hash SHA-256 di ogni file del
  bundle (stesso pattern già usato per i manifest dei modelli AI in Fase 3/4).
- **ZIP cifrato AES** (`infrastructure/reporting/encrypted_zip.py`, `pyzipper`): password
  separata dalla passphrase del vault, pensata per essere condivisa con chi riceve il
  report. Verificato che il file ZIP su disco non contenga mai il testo in chiaro.
- **`ExportProfessionalReportCommand`**: orchestra redazione → PDF → JSON → manifest →
  ZIP; **cancella i file intermedi in chiaro** dopo aver creato lo ZIP (solo il contenitore
  cifrato resta su disco).
- **UI**: la tab "Analisi chat" ha ora un campo password, una checkbox "Redigi i nomi" e
  un bottone "Esporta report professionale", che riusa la timeline appena analizzata.
- 20 test nuovi (82 totali): redazione (pseudonimi coerenti/distinti/mai il nome reale),
  rendering PDF/manifest/zip (incluso "password sbagliata rifiutata" e "nessun testo in
  chiaro su disco"), command end-to-end (zip con esattamente 3 file, file intermedi
  rimossi, redazione attiva/disattiva). `ruff` e `mypy --strict` puliti.

## Verifica manuale eseguita

Generato un report completo da riga di comando su un caso a due messaggi (uno neutro, uno
con minaccia esplicita): PDF valido (magic bytes `%PDF`), manifest con hash corretti, ZIP
apribile solo con la password giusta, contenuti correttamente redatti quando richiesto.

## Rischi residui

- **Report "dalla cassaforte" non disponibile**: come spiegato sopra, serve prima
  l'`EvidenceRecord` (messaggio+analisi come unità persistita) — oggi il report professionale
  funziona solo su una sessione di Analisi chat appena eseguita, non su prove storiche
  salvate in Fasi precedenti.
- **PDF minimale**: una tabella, non un documento con indice/copertina/firma digitale —
  sufficiente per un MVP, da arricchire se richiesto (Fase 9+).
- **Nessuna validazione password**: il campo password non impone lunghezza minima o
  robustezza — un vincolo da aggiungere se il report deve avere garanzie di sicurezza
  formali.
- **`ExportProfessionalReportCommand` non testato con `redact=True` su nomi ripetuti tra
  sessioni diverse**: ogni chiamata crea una nuova `RedactionService`, quindi lo stesso
  mittente riceverebbe pseudonimi diversi in report generati in momenti diversi — accettabile
  per un report singolo e autosufficiente, ma da tenere presente se in futuro si
  confrontano più report tra loro.
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q                       # 82 test devono passare
uv run ruff check src tests scripts
uv run mypy src

uv run python -m shielddesk.main
# Tab "Analisi chat": incolla un export, "Analizza", inserisci una password
# nel campo dedicato, clic su "Esporta report professionale".
# Il file reports/report.zip apparirà nella cwd, apribile solo con quella password.
```

## Definition of Done

- [x] Test verdi (82/82, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 9 — Hardening (threat model, dependency audit, SBOM, test privacy,
packaging, firma, installer), secondo `ANALYSIS.md` §M. Il packaging resta condizionato
dall'esito dello spike Windows non ancora eseguibile in questo ambiente (§L); le altre
attività (audit dipendenze, SBOM, test privacy, threat model) sono indipendenti da Windows.
