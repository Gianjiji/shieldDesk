# Fase 1 — Foundation: report di fine fase

Vedi `ANALYSIS.md` §M per la roadmap completa e `CLAUDE.md` per le convenzioni.

## Changelog

- Ambiente: Python 3.12.13 (Homebrew) + `uv` 0.11.29; `pyproject.toml` con PySide6, pydantic,
  structlog (runtime) e pytest/pytest-qt/pytest-asyncio/ruff/mypy/hypothesis (dev).
- Struttura del progetto creata secondo `ANALYSIS.md` §F (domain/application/infrastructure/presentation).
- Dominio puro (zero import Qt/WinRT/SQL): `IncomingMessage`, `AnalysisResult`, value object
  (`RiskLevel`, `ThreatCategory`, `Confidence`, `MessageSource`), eventi, port (`Protocol`) per
  notifiche/analyzer/repository/clock.
- Infrastruttura fake/mock: `FakeNotificationAdapter`, `MockAnalyzer` (regole su parole chiave
  esplicite), `InMemoryEvidenceRepository`, `SystemClock`.
- Logging redatto (`structlog`) con processor che oscura i campi testuali sensibili per nome,
  indipendentemente dal chiamante.
- DI container (`infrastructure/config/container.py`) come unico punto che conosce i binding
  concreti; nessun singleton globale non controllato.
- Use case minimo `AnalyzeMessageCommand` (application layer) per validare l'attraversamento
  dei layer senza anticipare la vertical slice completa di Fase 2.
- UI PySide6/QML minimale: due schermate (`Dashboard`, `Vault`) con navigazione a `TabBar` +
  `StackLayout`; i ViewModel (`DashboardViewModel`, `VaultViewModel`) non contengono business
  logic ed espongono solo stato/comandi.
- 12 test (unit dominio/applicazione/infrastruttura + smoke test headless dell'app) tutti verdi;
  `ruff check` e `mypy --strict` puliti.
- Git repository inizializzato.

## Rischio tecnico scoperto e risolto

`ApplicationWindow` (QtQuick Controls) causava un `TypeError: Cannot read property 'X' of null`
al primo binding su una context property, specificamente per componenti caricati da file esterni
via `import "screens"` — una race di timing tra la creazione del componente e la propagazione
del contesto radice, riproducibile anche in un caso minimo isolato. Non è un bug del nostro codice
applicativo ma un'interazione nota tra `QQmlApplicationEngine`, Controls e import di directory.

**Fix adottato**: `Window` (QtQuick.Window) invece di `ApplicationWindow`, e passaggio esplicito
del ViewModel come proprietà QML (`Dashboard { viewModel: dashboardViewModel }`) invece
dell'accesso implicito alla context property globale dentro le schermate. Pattern più esplicito
e testabile, da mantenere per le schermate future.

## Rischi residui

- **Non ancora validato su un display reale**: tutte le verifiche sono state eseguite in modalità
  `QT_QPA_PLATFORM=offscreen` (l'ambiente di sviluppo non ha un display grafico raggiungibile da
  qui). Va confermato a schermo che `TabBar`/`StackLayout` navighino visivamente come atteso.
- **`asyncio.run()` per chiamata** in `VaultViewModel.addDemoEvidence`: accettabile finché i
  comandi restano in-memory e istantanei; da rivedere (event loop persistente o thread dedicato)
  quando arriveranno I/O reali (Fase 5+) o il worker SLM (Fase 4).
- **Licenza del progetto**: `LICENSE` è un placeholder "tutti i diritti riservati" in attesa della
  decisione bloccante di `ANALYSIS.md` §O.2.
- Nessun TODO critico nascosto: il codice di Fase 1 è deliberatamente minimo (fake/mock ovunque)
  e non finge funzionalità non ancora costruite.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"   # per trovare uv, se non già nel PATH

uv run pytest            # 12 test devono passare
uv run ruff check src tests
uv run mypy src

# Avvio con UI reale (richiede un display):
uv run python -m shielddesk.main
# Atteso: finestra "ShieldDesk" con due tab, "Dashboard" mostra lo stato
# dell'adapter fake, "Cassaforte" mostra un contatore e un bottone che,
# premuto, incrementa "Prove salvate".

# Avvio headless (nessun display disponibile):
QT_QPA_PLATFORM=offscreen uv run python -m shielddesk.main
```

## Definition of Done

- [x] Test verdi (`pytest`, `ruff`, `mypy`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.

Prossimo passo: Fase 2 — vertical slice locale completa (messaggio simulato → normalizzazione →
analisi mock → risultato → salvataggio cifrato → visualizzazione cassaforte → report minimale),
secondo `ANALYSIS.md` §M.
