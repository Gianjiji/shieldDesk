# Revisione del codice — correzioni post-roadmap

Dopo il completamento delle 10 fasi e del refactor `EvidenceRecord`
(`docs/evidence-record-refactor.md`), una revisione a freddo dell'intera codebase
staged ha cercato bug reali accumulati durante lo sviluppo rapido. Questo documento
registra l'esito.

## Bug corretto — fallback silenzioso che mascherava errori del vault

**Dove**: `infrastructure/config/container.py`, funzione `_build_evidence_repository`.

**Problema**: l'apertura di `SQLCipherEvidenceRepository(...)` era avvolta da un
`except Exception` che degradava a un repository AES-GCM fallback su un file nuovo e
vuoto. Ma `SQLCipherEvidenceRepository.__init__` solleva `sqlcipher3.DatabaseError`
anche quando la **chiave è corretta ma il database non si apre** — per esempio se
`keyvault.json` ed `evidence.db` sono disallineati dopo un ripristino parziale di un
backup. In quel caso l'`except` catturava l'errore e creava silenziosamente una
cassaforte fallback vuota.

**Impatto**: per un'applicazione la cui unica funzione è conservare prove, questo è
il fallimento peggiore possibile — silenzioso e ingannevole: l'utente vedrebbe una
cassaforte apparentemente vuota invece di un errore, credendo perse le prove già
salvate e correttamente cifrate su disco.

**Correzione**: rimosso il fallback automatico. Gli errori di SQLCipher si propagano
ora rumorosamente (crash esplicito invece di dato mancante silenzioso). Il fallback
applicativo `EncryptedSqliteRepository` (Fase 2) resta disponibile per iniezione
esplicita nei test, non scelto in automatico mascherando un problema reale. Rimossi
due import diventati inutilizzati (`VaultUnlockError`, `EncryptedSqliteRepository`).

**Nota**: `sqlcipher3` è comunque una dipendenza obbligatoria del progetto (verificata
installabile senza compilazione in Fase 5), quindi il vecchio ramo "SQLCipher non
disponibile → fallback" era in pratica irraggiungibile: un import fallito avrebbe già
fatto fallire l'avvio molto prima, all'import di modulo in `sqlcipher_repository.py`.

**Test di regressione**:
`tests/unit/infrastructure/test_container.py::test_build_container_raises_loudly_on_mismatched_vault_db`
— un `evidence.db` cifrato con una chiave diversa da quella del `keyvault.json` deve
sollevare `sqlcipher3.DatabaseError`, mai creare un vault vuoto.

## Bug corretto — il worker SLM poteva crashare il chiamante invece di degradare

**Dove**: `infrastructure/ai/slm/worker_client.py`, metodo `_send_request`.

**Problema**: il contratto fail-safe del client (dichiarato nel suo docstring: "None dai
metodi pubblici significa esito AMBIGUO/non analizzato: mai un crash", coerente con
ANALYSIS.md §H4) era violato da due percorsi di errore non coperti:
1. `line.decode("utf-8")` sull'output del worker non era gestito: byte non-UTF-8 sullo
   stdout (es. diagnostica nativa di llama.cpp interlacciata con la risposta JSON)
   sollevano `UnicodeDecodeError` — sottoclasse di `ValueError`, quindi NON catturata
   dall'`except (json.JSONDecodeError, KeyError)` — che si propagava fino al chiamante.
2. `readline()` di asyncio rilancia `ValueError` se una riga supera il limite di buffer
   (worker che emette output enorme senza newline): non era catturato nel blocco di lettura.

**Impatto**: in entrambi i casi il tier SLM, che dovrebbe degradare silenziosamente al
tier precedente restituendo `None`, propagava invece un'eccezione — trasformando un worker
che si comporta male in un crash dell'intera analisi.

**Correzione**: aggiunto `UnicodeDecodeError` alla tupla del blocco di parsing e un
handler `ValueError` dedicato nel blocco di lettura; entrambi degradano a `None` (worker
che ha risposto male → resta `READY`; worker impazzito sulla lunghezza → `kill` + `FAILED`).

**Test di regressione**:
`tests/unit/infrastructure/test_slm_worker_client.py::test_non_utf8_response_returns_none_without_crashing`
+ nuova modalità `bad_utf8` nel worker fittizio (`tests/fixtures/fake_slm_worker.py`).

## Esito complessivo

- 2 bug reali (confermati) trovati e corretti, ciascuno con test di regressione. Entrambi
  della stessa classe: una gestione degli errori troppo stretta che, invece di degradare
  come previsto dal design fail-safe, propagava un'eccezione al chiamante.
- Suite completa dopo le correzioni: 100 test verdi, `ruff` pulito, `mypy --strict`
  senza errori.
- Aree verificate a mano (i subagent di review erano falliti per limite di sessione):
  logica di fallback del container, refactor `EvidenceRecord`, hash chain, DTO round-trip,
  parser WhatsApp (regex su input esterno), worker SLM (IPC/timeout/decode). Il parser è
  risultato solido: l'unica limitazione (cutoff a 60 caratteri sul nome mittente) è un
  tradeoff best-effort già documentato in ANALYSIS.md §D, non un bug.
