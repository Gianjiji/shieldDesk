# ShieldDesk

Applicazione web locale, **completamente offline**, che aiuta un genitore o tutore a riconoscere segnali di cyberbullismo nei messaggi ricevuti da un minore, a conservare le prove in una cassaforte cifrata a prova di manomissione e a produrre report professionali condivisibili (scuola, avvocato, forze dell'ordine).

Nessuna funzionalità dipende da rete, cloud o telemetria: l'assenza di accessi di rete non è una dichiarazione ma un fatto verificato da un test automatico dedicato (`tests/integration/test_no_network_access.py`).

> **Disclaimer**: ShieldDesk non fornisce accertamenti legali. I livelli di rischio prodotti dall'analisi AI sono stime probabilistiche, mai certezze. La liceità del monitoraggio di un minore (consenso, GDPR) è responsabilità dell'utente.

---

## Indice

1. [Cosa fa l'applicazione](#cosa-fa-lapplicazione)
2. [Requisiti](#requisiti)
3. [Installazione e primo avvio](#installazione-e-primo-avvio)
4. [Passphrase e recovery key](#passphrase-e-recovery-key)
5. [Guida alle funzionalità](#guida-alle-funzionalità)
6. [Modelli AI (opzionali)](#modelli-ai-opzionali)
7. [Architettura in breve](#architettura-in-breve)
8. [Test, lint e type checking](#test-lint-e-type-checking)
9. [Sicurezza e privacy](#sicurezza-e-privacy)
10. [Stato del progetto e limiti noti](#stato-del-progetto-e-limiti-noti)
11. [Mappa della documentazione](#mappa-della-documentazione)
12. [Licenza](#licenza)

---

## Cosa fa l'applicazione

- **Analizza messaggi** con una pipeline AI locale a più livelli (tier): regole deterministiche, classificatore di tossicità ONNX (fast path) e, per i casi ambigui, un piccolo modello linguistico (SLM) eseguito in un processo separato. Ogni risultato indica livello di rischio (SAFE / LOW / MEDIUM / HIGH), categoria di minaccia e confidenza.
- **Importa conversazioni WhatsApp** tramite incolla o file di export ufficiale (`.txt`), con parser per i formati iOS e Android in variante italiana, e mostra una timeline con un badge di rischio per ogni messaggio.
- **Conserva le prove** in una cassaforte SQLCipher cifrata full-file, protetta da passphrase con envelope encryption e recovery key. Ogni prova (`EvidenceRecord` = messaggio originale + esito dell'analisi) entra in una hash chain SHA-256 che rende rilevabile qualsiasi manomissione o rimozione di record.
- **Esporta report professionali**: PDF con tabella orario/mittente/messaggio/rischio, payload JSON conforme a schema formale, manifest con hash SHA-256 di ogni file, il tutto in uno ZIP cifrato AES con password dedicata (separata da quella del vault). Redazione opzionale dei nomi con pseudonimi coerenti ("Persona 1", "Persona 2", ...).
- **Degrada sempre in modo esplicito, mai silenzioso**: se un modello AI manca o fallisce, l'app passa al tier precedente (fino al `MockAnalyzer` a regole) loggando l'evento; non crasha e non inventa mai un risultato.

**Cosa NON fa (per scelta o per vincolo)**: non legge i dati interni di WhatsApp (solo notifiche di sistema — non ancora integrate, vedi [Stato del progetto](#stato-del-progetto-e-limiti-noti) — e import/incolla manuali), non risponde automaticamente ai messaggi, non invia nulla in rete.

---

## Requisiti

- **Python 3.12** (esattamente: `>=3.12,<3.13`)
- **[uv](https://docs.astral.sh/uv/)** come gestore di dipendenze
- CPU x64 con almeno 8 GB di RAM; nessuna GPU richiesta (inferenza CPU-only)
- Sviluppato e verificato su macOS; il target MVP dichiarato è Windows 11 x64, ma l'integrazione nativa Windows non è ancora stata realizzata (vedi limiti noti)

Le dipendenze principali (FastAPI, uvicorn, onnxruntime, llama-cpp-python, sqlcipher3, reportlab, pyzipper, cryptography, argon2-cffi) vengono installate automaticamente da `uv sync` e sono elencate in `pyproject.toml`; l'SBOM completo è in `docs/sbom/sbom.cdx.json`.

---

## Installazione e primo avvio

```bash
# 1. Installa le dipendenze
uv sync

# 2. Imposta la passphrase del vault (consigliato)
#    Senza questa variabile viene generata una passphrase EFFIMERA valida solo
#    per il processo corrente: alla chiusura i dati cifrati diventano illeggibili.
export SHIELDDESK_DEV_PASSPHRASE="una-passphrase-robusta"

# 3. Avvia l'applicazione (interfaccia web, si apre nel browser)
uv run python -m shielddesk.web_main
```

L'interfaccia gira come **applicazione web locale**: il server ascolta solo su
`127.0.0.1:8765` (configurabile con `SHIELDDESK_HOST`/`SHIELDDESK_PORT`) e si apre
automaticamente nel browser di default — utilizzabile da desktop, tablet o
telefono, con layout responsive. Nessun dato lascia il dispositivo. In ambienti
headless imposta `SHIELDDESK_NO_BROWSER=1` per non tentare l'apertura del browser.

Al **primo avvio** l'app crea la cassaforte nella directory `.shielddesk_vault/` (relativa alla directory di lavoro corrente), contenente:

- `evidence.db` — il database SQLCipher cifrato con le prove;
- `keyvault.json` — la master key del vault, avvolta (mai in chiaro) sia dalla passphrase sia dalla recovery key.

Sempre al primo avvio viene **stampata una sola volta la recovery key**: trascrivila e conservala offline (vedi sezione successiva).

Senza modelli AI installati l'app funziona comunque, degradando esplicitamente al `MockAnalyzer` (regole su parole chiave): utile per provare tutti i flussi. Per l'analisi reale vedi [Modelli AI](#modelli-ai-opzionali).

---

## Passphrase e recovery key

Il modello di chiavi (ADR-006/007 in `ANALYSIS.md`) funziona così:

- una **master key casuale da 32 byte** cifra realmente il database;
- la master key è avvolta due volte con AES-GCM: una con una chiave derivata dalla **passphrase** (Argon2id), una con una chiave derivata dalla **recovery key** generata al primo avvio (formato a gruppi leggibili, es. `XK3F9-7QRTL-...`, senza caratteri ambigui);
- lo sblocco funziona indifferentemente con l'una o con l'altra;
- **se si perdono entrambe, le prove sono irrecuperabili per progetto**: non esistono backdoor.

Una passphrase sbagliata contro un vault esistente **ferma l'avvio con un errore esplicito** (`VaultUnlockError` / errore SQLCipher): l'app non crea mai silenziosamente un vault vuoto al posto di uno esistente, per non far credere che le prove siano andate perse.

---

## Guida alle funzionalità

L'interfaccia è organizzata in tre schede.

### 1. Dashboard

Schermata di stato generale dell'applicazione e punto di ingresso della navigazione.

### 2. Cassaforte (Vault)

La vista delle prove conservate. Per ogni prova mostra mittente, livello di rischio e timestamp. Azioni disponibili:

- **Elabora messaggi simulati** — esegue la pipeline completa sui messaggi demo seminati dal container (uno neutro, uno a rischio HIGH): utile per una dimostrazione end-to-end senza input manuale.
- **Aggiungi prova demo** — inserisce una prova di esempio nella cassaforte cifrata.
- **Esporta report** — genera un report JSON minimale (conteggio e voci) dal contenuto della cassaforte.
- **Esporta report professionale** — genera il bundle completo (PDF + JSON + manifest in ZIP cifrato) **dalle prove storiche del vault**, non solo da una sessione di analisi corrente (capacità aggiunta dal refactor `EvidenceRecord`, vedi `docs/evidence-record-refactor.md`).

### 3. Analisi chat

Il flusso principale per l'uso reale:

1. **Incolla** il testo di una conversazione **oppure carica un file `.txt`** (trascinamento nell'area apposita o selezione dal disco) — ad esempio l'export ufficiale di WhatsApp. Il parser riconosce i formati iOS (parentesi quadre) e Android (trattino) in variante italiana della data, gestisce messaggi multi-riga, scarta l'avviso di crittografia end-to-end e gli eventi di sistema, e marca i media omessi come troncati. L'upload è validato (dimensione massima, solo testo UTF-8).
2. Premi **Analizza**: ogni messaggio viene analizzato con l'analyzer attivo (ONNX se il modello è installato, altrimenti mock) e il risultato compare **in stile dashboard**: riquadri di sintesi (totale messaggi, partecipanti, conteggio critici/alti), una barra di distribuzione per gravità e la timeline con i badge di rischio. **Filtri rapidi** per livello mostrano al volo solo i messaggi di una data gravità; il pulsante **Contesto** su un messaggio apre i **5 messaggi precedenti e i 5 successivi** per leggerlo nel suo contesto. Le righe non riconosciute dal parser vengono ignorate senza interrompere l'analisi.
3. **Salva come prova** i singoli messaggi rilevanti: la persistenza è sempre un'azione esplicita dell'utente, nulla viene salvato in automatico. Ogni prova salvata entra nella hash chain della cassaforte.
4. **Esporta report professionale**: imposta una password per lo ZIP (da condividere con il destinatario del report, separata dalla passphrase del vault), scegli se attivare **"Redigi i nomi"** (pseudonimi coerenti al posto dei mittenti reali) e premi il bottone di export. I file intermedi in chiaro vengono cancellati: su disco resta solo il contenitore cifrato.

Il PDF del report è strutturato come una **relazione**, pensata per essere allegata a un'eventuale segnalazione: apre con un disclaimer esplicito sulla natura probabilistica dei livelli di rischio, seguito da una **parte narrativa** (riepilogo dell'analisi ed evidenziazione dei messaggi di gravità CRITICA e ALTA); la **cronologia completa** di tutti i messaggi resta presente ma nelle **ultime pagine**. Il testo narrativo è generato in modo deterministico dai dati reali (conteggi, partecipanti, testi): nessun contenuto inventato dal modello, scelta voluta per un documento che può finire in una denuncia.

### Integrità e backup (funzioni di infrastruttura)

- `SQLCipherEvidenceRepository.verify_integrity()` ricalcola l'intera hash chain e rileva sia la modifica di un record sia la rimozione silenziosa di un record intermedio.
- `infrastructure/persistence/backup.py` esegue backup sicuri con l'API nativa SQLite/SQLCipher (mai una copia file grezza), verifica il conteggio righe post-copia e scarta i backup incompleti. Il backup resta cifrato con la stessa chiave.

---

## Modelli AI (opzionali)

I modelli **non sono versionati nel repository** e vanno generati/scaricati manualmente (coerente con ADR-011: import solo da file locale con verifica hash da manifest). Senza modelli, l'app degrada in modo esplicito al `MockAnalyzer`.

### Tier 1 — Fast path ONNX

- Modello: `unitary/multilingual-toxic-xlm-roberta` (Apache-2.0, italiano supportato)
- Posizione attesa: `models/toxic-xlm-roberta-onnx/` (nella radice del progetto)
- Conversione: `scripts/convert_toxicity_model_to_onnx.py`, da eseguire con dipendenze effimere (torch e optimum-onnx non sono dipendenze del progetto):

```bash
uv run --with torch --with "optimum-onnx[onnxruntime]" --with transformers \
  python scripts/convert_toxicity_model_to_onnx.py
```

- Manifest con hash SHA-256: `product/model_manifest.json`, rigenerabile con `scripts/generate_model_manifest.py`. Dettagli completi in `docs/phase-3-report.md`.
- Nota dichiarata: le soglie di mappatura punteggio-rischio **non sono calibrate** statisticamente (placeholder verificato solo su uno smoke-set italiano di 10 frasi).

### Tier SLM — Casi ambigui

- Modello: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, quantizzazione Q4_K_M (~1.06 GB), repository ufficiale Qwen, Apache-2.0
- Posizione attesa: `models/qwen2.5-1.5b-instruct-gguf/`
- Manifest: `product/slm_model_manifest.json` (script `scripts/generate_slm_model_manifest.py`)
- **Download**: al primo avvio i launcher (`shielddesk.command` / `shielddesk.ps1`) propongono di scaricarlo (opzionale, saltabile), verificando l'integrità con lo **SHA-256** del manifest prima di installarlo; se declinato o non scaricato, l'app funziona con la sola analisi veloce.
- Esecuzione in **worker process separato** con protocollo JSON-line su stdin/stdout, grammatica GBNF che vincola l'output a JSON valido, timeout con kill del processo, unload automatico per inattività. Ogni percorso di errore restituisce esito "non analizzato", mai un risultato inventato. Dettagli in `docs/phase-4-report.md`.
- **Analisi contestuale (cascata ONNX → SLM)**: nell'analisi chat il tier veloce ONNX classifica ogni messaggio in isolamento; per i soli messaggi segnalati (rischio > SAFE) un refiner SLM li **rivaluta dentro la conversazione** (finestra dei messaggi precedenti + mittente), riducendo i falsi positivi che un classificatore riga-per-riga non può vedere. La grammatica GBNF impone al modello un campo `reason` **prima** del verdetto: il ragionamento sul contesto precede l'etichetta, indispensabile perché un modello da 1.5B usi davvero il contesto. Verificato end-to-end: lo stesso messaggio "ti ammazzo" è `HIGH/threat` da solo e `SAFE` dopo un contesto scherzoso tra amici. Il refiner si attiva automaticamente se il modello GGUF è presente; fail-safe (§H4): se manca o non è disponibile a runtime si tiene il risultato ONNX. Disattivabile con `SHIELDDESK_DISABLE_SLM=1` su macchine deboli (il passaggio SLM è più lento).

---

## Architettura in breve

Clean Architecture a 4 layer con MVVM, pensata per il futuro porting Android (Kotlin/Compose):

```text
src/shielddesk/
  domain/           # Entita, value object, port (Protocol), eventi, servizi puri
                    # (hash_chain, redaction) - zero import di Qt, ONNX, SQL, WinRT
  application/      # Use case (commands) e DTO JSON versionati
  infrastructure/   # Adapter concreti: crypto (Argon2id, AES-GCM, envelope),
                    # persistenza (SQLCipher + fallback AES-GCM + in-memory),
                    # AI (mock, ONNX, SLM worker), chat_import, reporting, config/DI
  presentation/     # web/ : app FastAPI (API REST) + SPA statica responsive
```

Regole chiave: le dipendenze puntano sempre verso l'interno; ogni integrazione esterna passa da un port nel dominio; il DI container (`infrastructure/config/container.py`) è l'unico punto che conosce i binding concreti; i test usano sempre fake/mock, mai gli adapter reali.

I contratti dati sono formalizzati come JSON Schema Draft 2020-12 in `docs/schemas/` (fonte di verità language-agnostic, condivisa con il futuro porting Android insieme ai test vector in `tests/vectors/`).

Le 11 decisioni architetturali (ADR-001..011) con contesto, alternative e criteri di revisione sono in `ANALYSIS.md` §E.

---

## Test, lint e type checking

```bash
uv run pytest                        # intera suite (98 test)
uv run pytest tests/unit             # solo unit
uv run pytest -k <pattern>           # test specifici
uv run ruff check src tests scripts  # lint
uv run mypy src                      # type checking (strict)
```

Note sulla suite:

- I test dell'SLM usano un **worker fittizio** (`tests/fixtures/fake_slm_worker.py` con modalita normal/hang/no_ready/garbage/crash): veloci, deterministici, senza bisogno del modello da 1 GB.
- Gli smoke test end-to-end con i modelli reali (ONNX e SLM) vengono **skippati automaticamente** se i modelli non sono installati.
- Test notevoli: assenza di testo in chiaro su disco (ispezione byte-per-byte del `.db` e dello ZIP), rifiuto di chiave/password sbagliata, integrita della hash chain su manomissione e rimozione, **blocco totale della rete** durante l'intero flusso verticale, conformita dei DTO agli schemi JSON formali.

---

## Sicurezza e privacy

- **Zero rete**: nessun socket in uscita, nessun download automatico, nessuna telemetria — verificato da test.
- **Zero plaintext su disco**: il testo dei messaggi vive solo dentro il database cifrato; i file intermedi dei report vengono cancellati dopo la creazione dello ZIP cifrato.
- **Logging redatto**: il logger (`infrastructure/logging.py`) oscura per nome i campi testuali sensibili, indipendentemente dal chiamante; l'uso di `print` o logger non filtrati e vietato dalle convenzioni.
- **Chiavi**: derivazione Argon2id con parametri versionati; nessuna chiave hard-coded; envelope encryption con recovery key.
- **Modelli AI**: import solo da file locale con verifica hash rispetto ai manifest.
- **Audit dipendenze**: eseguito in Fase 9 con `pip-audit`; `cryptography` aggiornata a 48.x; i rischi residui accettati (in particolare `transformers` 4.x) sono motivati caso per caso in `docs/phase-9-report.md`.
- **Threat model**: iniziale in `ANALYSIS.md` §I, riesaminato a fine Fase 9 con lo stato reale delle mitigazioni.

---

## Stato del progetto e limiti noti

Tutte le fasi della roadmap originale (`ANALYSIS.md` §M, Fasi 0-10) sono state eseguite o esplicitamente rimandate, ciascuna con un report di fine fase. Limiti dichiarati:

- **Fase 6 (integrazione notifiche Windows) non eseguita**: richiede lo spike su hardware Windows reale descritto in `ANALYSIS.md` §L (l'API WinRT `UserNotificationListener` da processo Python non pacchettizzato e il potenziale blocker principale del progetto). Oggi l'unica sorgente notifiche e il `FakeNotificationAdapter`; l'ingresso reale dei dati e l'analisi chat manuale.
- **Packaging, firma e installer (parte di Fase 9) rimandati**: la scelta del packager dipende dall'esito dello stesso spike Windows (ADR-009 vieta di scegliere PyInstaller per default).
- **Refinement contestuale SLM sui casi "insulto reale"**: la cascata ONNX → SLM contestuale è cablata e riduce i falsi positivi (es. minaccia scherzosa tra amici → SAFE), ma su un messaggio che contiene un insulto esplicito (es. "sei scemo") il modello da 1.5B lo segnala comunque, a prescindere dal contesto. Le soglie ONNX restano non calibrate (§K).
- **Soglie del classificatore ONNX non calibrate** e smoke-set italiano minuscolo (10 frasi): serve un benchmark statistico vero.
- **Parser WhatsApp limitato alla variante italiana** dei formati iOS/Android; righe non riconosciute vengono scartate silenziosamente (possibile fonte di falsi negativi di parsing).
- **Nessuna migrazione dati** per i vault creati prima del refactor `EvidenceRecord`: un database precedente non e piu decodificabile (rottura intenzionale e documentata, nessun dato reale in gioco).
- **UI web responsive**: l'interfaccia è ora un'applicazione web servita in locale (FastAPI + SPA statica, nessuna dipendenza CDN), utilizzabile dal browser di qualunque dispositivo. Sostituisce — e **rimuove** — la precedente UI QML/PySide6, che era stata verificata solo headless (`QT_QPA_PLATFORM=offscreen`) e mai su un display reale; con essa è stata tolta anche la dipendenza `pyside6`. **Sicurezza**: il server ascolta solo su host locali e valida l'header `Host` (difesa da DNS-rebinding: un sito malevolo aperto nel browser non può leggere le prove rebindando su 127.0.0.1); l'export minimale tratta l'input come nome file confinato in `reports/` (niente path traversal). Il tier SLM riceve testo non fidato ma la grammatica GBNF ne vincola l'output all'enum e il system prompt lo tratta come dato: un test di prompt-injection col modello reale verifica che una minaccia con iniezione non venga declassata a SAFE.
- **Auto-reply impossibile su desktop** per assenza di API: il fallback previsto e la risposta suggerita da copiare; l'auto-reply reale arrivera con il porting Android.
- **Porting Android**: solo specifiche, mapping Kotlin e backlog (`docs/android/`), nessun codice Kotlin scritto; tre domande aperte richiedono uno spike Android.
- **Licenza**: placeholder "tutti i diritti riservati" in attesa della decisione bloccante di `ANALYSIS.md` §O.2.

---

## Mappa della documentazione

| Documento | Contenuto |
|---|---|
| `docs/phase-1-report.md` ... `phase-10-report.md` | Report di fine fase: changelog, bug trovati e risolti, rischi residui, istruzioni di verifica manuale (la cronologia reale del progetto) |
| `docs/evidence-record-refactor.md` | Refactor post-Fase 10 che introduce `EvidenceRecord` come unita persistita e sblocca il report professionale dalla cassaforte storica |
| `docs/code-review-fixes.md` | Revisione a freddo finale: bug reali trovati (fallback silenzioso del vault, crash del client SLM) e corretti con test di regressione |
| `docs/schemas/` | Contratti JSON formali (Draft 2020-12): analysis result, report, model manifest |
| `docs/android/` | Specifiche portabili, mapping Python-Kotlin tipo per tipo, backlog del porting |
| `docs/sbom/` | Software Bill of Materials (CycloneDX) con istruzioni di rigenerazione |
| `docs/adr/`, `docs/spikes/` | Placeholder vuoti per scelta: le ADR vivono in `ANALYSIS.md` §E; i report di spike non esistono perche gli spike (Windows/Android) sono bloccati dall'assenza di hardware dedicato |

---

## Licenza

Placeholder proprietario ("tutti i diritti riservati") in attesa di decisione esplicita — vedi `LICENSE` e la domanda aperta in `ANALYSIS.md` §O.2.
