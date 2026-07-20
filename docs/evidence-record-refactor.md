# Refactor: EvidenceRecord (post Fase 10)

Colma il gap identificato in `docs/phase-8-report.md` e riconfermato in `docs/phase-10-report.md`:
`AnalysisResult`, l'unica cosa persistita dalle Fasi 2-9, non portava con sé il messaggio
originale (mittente/testo) — impedendo di ricostruire "chi ha detto cosa" da una prova salvata
in precedenza. `ANALYSIS.md` §G aveva sempre previsto un `EvidenceRecord` distinto; questo
refactor allinea finalmente l'implementazione a quella decisione.

## Changelog

- **`domain/entities/evidence_record.py`**: nuova entità `EvidenceRecord` (evidence_id,
  message, analysis, stored_at, user_annotation) — l'unità realmente persistita nella cassaforte.
- **`application/dto/incoming_message_v1.py`** e **`evidence_record_v1.py`**: nuovi DTO JSON
  versionati.
- **`EvidenceRepositoryPort`**: `store()` ora richiede `(message, analysis)` invece del solo
  `analysis`; `get()`/`list_all()` restituiscono `EvidenceRecord`, non più `AnalysisResult`.
  Aggiornate tutte e tre le implementazioni (`SQLCipherEvidenceRepository`,
  `EncryptedSqliteRepository`, `InMemoryEvidenceRepository`).
- **Hash chain**: ora calcolata sul payload canonico dell'intero `EvidenceRecord`, non più
  del solo `AnalysisResult` — coerente con ADR-006 ("hash chain sugli EvidenceRecord", non
  sui soli risultati).
- **Report professionale dalla cassaforte storica** (sblocca il gap di Fase 8):
  `ExportProfessionalReportCommand` ora accetta coppie generiche `(IncomingMessage,
  AnalysisResult)` invece del solo `ChatTimelineEntry` — funziona identicamente sia per una
  sessione di analisi chat appena fatta sia per prove storiche lette dal vault.
  `VaultViewModel.exportProfessionalReport()` (nuovo) espone questa capacità nella UI.
- **`VaultViewModel`**: la lista delle prove ora mostra anche il mittente, non solo livello di
  rischio e timestamp.
- Aggiornati tutti i test esistenti che chiamavano `.store()` con la vecchia firma; 15 test
  nuovi (98 totali). `ruff` e `mypy --strict` puliti.

## Verifica end-to-end eseguita

Flusso manuale completo: creazione cassaforte (con stampa recovery key), analisi di due
messaggi, salvataggio come prove, **rilettura dalla cassaforte** (simulando una riapertura
dell'app), generazione di un report professionale redatto dai record recuperati — non dalla
sessione di analisi originale. Funziona.

## Compatibilità con dati esistenti

**Rottura intenzionale, non nascosta**: un database SQLCipher creato prima di questo refactor
conteneva `payload` = solo `AnalysisResult` serializzato; dopo il refactor `payload` = intero
`EvidenceRecord`. Un vecchio database non si decodifica più correttamente (il campo
`schema_version` dentro il payload distingue i due formati, ma non è stata scritta logica di
migrazione dei dati). Accettabile: nessun dato reale di utenti in gioco in questa fase di
sviluppo, solo dati di test locali. Da affrontare con una migrazione dati vera se necessario
prima di un rilascio.

## Rischi residui

- Nessuna migrazione automatica dei vecchi record (vedi sopra).
- `user_annotation` esiste nell'entità/DTO ma non ha ancora un punto d'ingresso nella UI
  (nessun campo per annotare una prova) — capacità pronta, non esposta.
- Nessun TODO critico nascosto.

## Verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q            # 98 test devono passare
uv run ruff check src tests scripts
uv run mypy src

uv run python -m shielddesk.main
# Tab "Cassaforte": dopo aver salvato alcune prove, il nuovo bottone
# "Esporta report professionale (cassaforte)" genera un report dalle prove
# storiche, non solo dalla sessione di analisi corrente.
```
