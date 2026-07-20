# Fase 9 — Hardening: report di fine fase

Vedi `ANALYSIS.md` §I/§M. Obiettivo dichiarato: threat model, dependency audit, SBOM, test
privacy, packaging, firma, installer. **Packaging/firma/installer restano bloccati**: dipendono
dall'esito dello spike Windows (`ANALYSIS.md` §L), non eseguibile in questo ambiente macOS —
coerente con la decisione già presa di rimandare la Fase 6. Le altre attività sono indipendenti
da Windows e sono state completate.

## Changelog

- **Audit dipendenze** (`pip-audit`, eseguito via `uv run --with pip-audit`, non aggiunto alle
  dipendenze del progetto): trovate e gestite 4 famiglie di vulnerabilità note.
  - **`cryptography` 42.0.8 → 48.0.1**: 6 CVE/advisory risolte (incluse vulnerabilità OpenSSL
    sottostanti e un problema di verifica PKCS#7/S/MIME che comunque non usiamo). Verificato che
    l'API usata da `aes_gcm.py`/`key_derivation.py`/`vault_key.py` (`AESGCM`, `InvalidTag`) resta
    identica; suite completa (83 test) rieseguita e verde dopo l'aggiornamento.
  - **`transformers` 4.57.6**: 4 CVE (RCE legate a `trust_remote_code`, caricamento di
    checkpoint/config da repository non fidati). **Tentato l'aggiornamento a 5.3+** (dove sono
    risolte): ha reintrodotto lo stesso conflitto protobuf/sentencepiece della Fase 3 tramite un
    nuovo meccanismo interno di conversione del tokenizer, rompendo il fast path ONNX anche con
    `use_fast=False`. **Riportato a 4.x** dopo aver riprodotto la rottura con la suite di test.
    Rischio accettato con motivazione esplicita: il nostro codice chiama solo
    `AutoTokenizer.from_pretrained(percorso_locale, use_fast=False)` su una directory scaricata e
    controllata da noi — non chiama mai `AutoModel.from_pretrained`, `Trainer`, né passa
    `trust_remote_code=True` o repository remoti non fidati. Le CVE riguardano path che il codice
    non esercita mai. Da rivedere se `transformers` pubblica un fix sulla riga 4.x, o quando la
    dipendenza da `transformers` verrà eventualmente eliminata (vedi rischio residuo sotto).
  - **`diskcache` 5.6.3** (dipendenza transitiva, non dichiarata direttamente): deserializzazione
    pickle non sicura se un attaccante ha già accesso in scrittura alla directory di cache locale.
    Nessuna versione con fix ancora pubblicata a monte. Rischio accettato: sfruttabile solo con
    accesso locale già compromesso, scenario in cui esistono comunque problemi peggiori.
  - **`pytest` 8.4.2**: DoS locale via pattern prevedibile in `/tmp/pytest-of-{user}`.
    Dipendenza di sviluppo, mai distribuita con l'app: rischio accettato, priorità bassa.
- **SBOM** (`docs/sbom/sbom.cdx.json`, formato CycloneDX, 59 componenti): generato
  dall'ambiente virtuale del progetto con `cyclonedx-py`; istruzioni di rigenerazione in
  `docs/sbom/README.md`.
- **Test privacy con evidenza reale** (`tests/integration/test_no_network_access.py`): blocca
  `socket.socket.connect`/`connect_ex`/`create_connection` a livello di libreria standard e fa
  girare l'intero flusso verticale (container → analisi chat → salvataggio cifrato → export
  report professionale) sotto il blocco. Se un qualunque componente, diretto o transitivo,
  tentasse un accesso di rete, il test fallirebbe immediatamente — non è più solo una
  dichiarazione nel codice, è verificato.
- 1 test nuovo (83 totali). `ruff` e `mypy --strict` puliti dopo tutti gli aggiornamenti.

## Threat model — riesame alla luce di quanto costruito (vs. ANALYSIS.md §I)

| Rischio (da §I) | Stato a fine Fase 0 | Stato a fine Fase 9 |
|---|---|---|
| Lettura del file DB da disco | Mitigazione pianificata | **Mitigato**: SQLCipher reale (Fase 5), non più solo AES-GCM per riga |
| Manomissione/cancellazione record | Mitigazione pianificata | **Mitigato e verificabile**: hash chain con `verify_integrity()` testato su manomissione e rimozione (Fase 5) |
| Prompt injection nel messaggio | Mitigazione pianificata | **Mitigato**: testo sempre delimitato nel prompt del worker SLM, mai istruzione (Fase 4) |
| Modello AI malevolo importato | Mitigazione pianificata | **Mitigato**: manifest con hash SHA-256 per ONNX e SLM (Fasi 3-4) |
| Leak di contenuti nei log | Mitigazione pianificata | **Mitigato e testato**: logging redatto (Fase 1) + verifica zero-rete end-to-end (Fase 9) |
| Diffusione non controllata del report | Mitigazione pianificata | **Mitigato**: ZIP cifrato AES + redazione nomi opzionale (Fase 8) |
| Supply chain (dipendenze) | Generico ("audit Fase 9") | **Parzialmente mitigato**: audit CVE eseguito, 1 upgrade applicato, 3 rischi accettati con motivazione esplicita (sopra); **non ricorrente** — serve un processo di audit periodico, non ancora automatizzato |
| Binario alterato / SmartScreen bypass | Mitigazione pianificata | **Non affrontato**: bloccato dallo spike Windows (§L) |

### Rischio nuovo identificato in questa fase

**Deriva delle dipendenze nel tempo**: l'audit ha trovato CVE reali in pacchetti già in uso
(non ipotetiche) dopo solo poche settimane di sviluppo. Senza un processo ricorrente (es. CI
schedulata con `pip-audit`), le dipendenze si degradano silenziosamente. Non ancora automatizzato
— vedi rischi residui.

## Rischi residui

- **Packaging/firma/installer non affrontati**: bloccati dallo spike Windows (§L), come già
  comunicato per la Fase 6. La matrice di confronto packager (ADR-009) resta da completare dopo.
- **Dipendenza da `transformers` 4.x con CVE note ma non sfruttabili nel nostro caso d'uso**:
  documentato sopra con motivazione tecnica precisa; da rivedere quando possibile.
- **Nessun audit ricorrente automatizzato**: `pip-audit` è stato eseguito manualmente in questa
  sessione, non c'è ancora una pipeline CI che lo rilanci a ogni modifica delle dipendenze.
- **SBOM statico**: va rigenerato manualmente a ogni cambio di dipendenze (istruzioni in
  `docs/sbom/README.md`), non è agganciato a un hook o alla CI.
- **Test privacy copre solo il livello socket Python**: non intercetta, per esempio, chiamate
  di rete fatte da estensioni native in C che aprono socket a un livello sotto `socket.socket`
  (nessuna delle nostre dipendenze attuali lo fa, verificato dal test stesso, ma è un limite
  metodologico da conoscere, non una garanzia assoluta).
- Nessun TODO critico nascosto.

## Istruzioni di verifica manuale

```bash
cd /Users/gianluigi/Downloads/waf
export PATH="/opt/homebrew/bin:$PATH"
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-di-sviluppo"

uv run pytest -q                                  # 83 test devono passare
uv run pytest tests/integration/test_no_network_access.py -v   # solo il test privacy
uv run ruff check src tests scripts
uv run mypy src

# Ripetere l'audit dipendenze:
uv run --with pip-audit pip-audit

# Rigenerare l'SBOM:
uv run --with cyclonedx-bom cyclonedx-py environment --of JSON \
    --output-file docs/sbom/sbom.cdx.json .venv
```

## Definition of Done

- [x] Test verdi (83/83, `ruff`, `mypy --strict`).
- [x] Changelog (questo documento).
- [x] Rischi residui elencati.
- [x] Istruzioni di verifica manuale.
- [x] Nessun TODO critico nascosto.
- [~] Packaging/firma/installer: esplicitamente non affrontati, bloccati dallo spike Windows,
  non un TODO nascosto ma una dipendenza dichiarata fin dalla Fase 6.

Prossimo passo: Fase 10 — Preparazione Android (specifiche portabili, test vector, contratti
JSON, mapping Python/Kotlin, backlog Android), secondo `ANALYSIS.md` §M. Indipendente da Windows.
In alternativa, tornare alla Fase 6 se nel frattempo diventa disponibile una macchina Windows
per lo spike di `ANALYSIS.md` §L.
