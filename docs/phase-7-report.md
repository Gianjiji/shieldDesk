# Fase 7 — Analisi chat: report di fine fase

Vedi `ANALYSIS.md` §H7/§M. Obiettivo: paste, import, parser WhatsApp, contesto, timeline.
Fase saltata la Fase 6 (Integrazione Windows) su decisione esplicita dell'utente: richiede
lo spike Windows di §L su hardware reale, non eseguibile in questo ambiente macOS.

## Changelog

- **Parser WhatsApp** (`infrastructure/chat_import/whatsapp_parser.py`): copre entrambi i
  formati di export noti (iOS a parentesi quadre, Android a trattino) in variante italiana
  della data. Gestisce: continuazione multi-riga dello stesso messaggio, notizia di
  crittografia end-to-end (scartata come non-messaggio), eventi di sistema senza mittente
  reale (es. "ha cambiato l'icona del gruppo", scartati), placeholder media (`<Media
  omessa>`, marcato con `is_truncated=True`). **Fail-safe by design**: una riga non
  riconosciuta viene ignorata, mai un'eccezione che interrompe l'intero parsing — coerente
  con "non inventare/non bloccare" di ANALYSIS.md §25.
- **`AnalyzeChatCommand`** (`application/commands/analyze_chat.py`): parsing + analisi di
  ogni messaggio tramite l'`AnalyzerPort` corrente (Mock/ONNX a seconda del container),
  produce una `ChatTimelineEntry` per messaggio (coppia messaggio+risultato). **Non salva
  nulla in automatico**: la persistenza resta un'azione esplicita, coerente con "Selezione
  messaggi -> EvidenceRecord" del flusso H7.
- **`ChatAnalysisViewModel`** + **schermata `ChatAnalysis.qml`** (terza tab dell'app): area
  di testo per incollare l'export, bottone "Analizza", timeline con badge di rischio per
  messaggio e bottone "Salva come prova" per riga (che chiama direttamente
  `evidence_repository.store()`, riusando la persistenza cifrata di Fase 5 senza modifiche).
- 13 test nuovi (81 totali): parser (formati iOS/Android, multi-riga, media, input vuoto/
  spazzatura, ordine cronologico), `AnalyzeChatCommand` (timeline ordinata, sorgente
  richiesta, input vuoto), smoke test dell'app esteso alla nuova tab. `ruff` e
  `mypy --strict` puliti.

## Verifica manuale eseguita

Flusso end-to-end con un export realistico a tre messaggi (uno neutro, uno con minaccia
esplicita, uno neutro) più la notizia di crittografia in testa: la notizia è stata
correttamente scartata, i tre messaggi classificati SAFE/HIGH/SAFE come atteso.

## Rischi residui

- **Copertura limitata dei formati export**: il parser copre solo la variante italiana
  (gg/mm/aa) dei due formati noti (iOS/Android). Altri locale, altre versioni dell'app, o
  export con formattazione leggermente diversa potrebbero non essere riconosciuti — righe
  non riconosciute vengono silenziosamente scartate invece di produrre un errore visibile
  all'utente: potenziale fonte di falsi negativi silenziosi (messaggi persi dal parsing),
  non testati con dati reali (solo esempi scritti a mano per questo progetto).
- **Timestamp senza timezone**: WhatsApp esporta l'ora locale del dispositivo senza offset;
  i timestamp restano "naive". Non un bug, ma un limite noto da comunicare se il timing
  esatto conta (es. correlazione con altre fonti).
- **Nessun "contesto" nel senso di finestra AI**: la timeline mostra ogni messaggio con il
  proprio esito di analisi indipendente; non c'è ancora passaggio di contesto conversazionale
  all'analyzer (quello pianificato in ANALYSIS.md §K per l'SLM). "Contesto" qui è inteso come
  visualizzazione dell'intera conversazione in sequenza, non come arricchimento del prompt.
- **Nessun rilevamento automatico del formato/locale**: l'utente deve incollare un export
  compatibile; non c'è messaggio d'errore esplicito se il parsing produce zero messaggi
  (l'utente vede semplicemente "Messaggi analizzati: 0").
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q                       # 81 test devono passare
uv run ruff check src tests scripts
uv run mypy src

uv run python -m shielddesk.main
# Tab "Analisi chat": incolla un export WhatsApp (o alcune righe nel formato
# "[gg/mm/aa, hh:mm:ss] Mittente: testo"), clic su "Analizza", verifica la
# timeline con i badge di rischio, clic su "Salva come prova" su una riga.
```

## Definition of Done

- [x] Test verdi (81/81, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 8 — Report professionali (PDF, JSON, manifest, ZIP cifrato,
redazione), secondo `ANALYSIS.md` §M. Non richiede Windows né nuovi modelli.
