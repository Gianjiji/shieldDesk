# Mapping Python → Kotlin

Fase 10. Traduzione concreta, tipo per tipo, degli elementi del dominio elencati come
portabili in `docs/android/portable-spec.md`. Pensato come riferimento diretto per chi
inizierà il porting, non come codice già scritto.

## Value object ed enum

| Python (`domain/value_objects/`) | Kotlin | Note |
|---|---|---|
| `RiskLevel(IntEnum)` — `SAFE=0 … CRITICAL=4` | `enum class RiskLevel(val value: Int) { SAFE(0), LOW(1), MEDIUM(2), HIGH(3), CRITICAL(4) }` | Mantenere il valore intero esplicito per la (de)serializzazione JSON, non l'ordinale implicito di Kotlin |
| `ThreatCategory(StrEnum)` — `"insult"`, `"exclusion"`, ... | `enum class ThreatCategory(val value: String) { INSULT("insult"), EXCLUSION("exclusion"), ... }` | Stesso motivo: valore stringa esplicito, non il nome dell'enum |
| `MessageSource(StrEnum)` | `enum class MessageSource(val value: String) { ... }` | Idem |
| `Confidence` (`@dataclass(frozen=True)`, valida `0.0 ≤ value ≤ 1.0`) | `@JvmInline value class Confidence(val value: Double) { init { require(value in 0.0..1.0) } }` | Kotlin `value class` evita l'overhead di un wrapper a runtime pur mantenendo la validazione |

## Entità

| Python (`domain/entities/`) | Kotlin | Note |
|---|---|---|
| `IncomingMessage` (`@dataclass(frozen=True, slots=True)`) | `data class IncomingMessage(val messageId: String, val source: MessageSource, val sender: String, val text: String, val timestamp: Instant, val isTruncated: Boolean = false)` | `datetime` → `kotlinx.datetime.Instant` (non `java.util.Date`, per coerenza con seriali ISO 8601) |
| `AnalysisResult` | `data class AnalysisResult(val schemaVersion: String, val messageId: String, val tier: AnalysisTier, val modelId: String, val modelVersion: String, val promptVersion: String, val timestamp: Instant, val riskLevel: RiskLevel, val categories: List<CategoryScore> = emptyList(), val latencyMs: Double = 0.0)` | `tuple[CategoryScore, ...]` → `List<CategoryScore>` (immutabile per convenzione, non imposta dal tipo come in Python) |
| `CategoryScore` | `data class CategoryScore(val category: ThreatCategory, val confidence: Confidence)` | 1:1 |
| `AnalysisTier(StrEnum)` | `enum class AnalysisTier(val value: String) { RULES("rules"), FAST("fast"), SLM("slm") }` | 1:1 |

## Eventi di dominio

| Python (`domain/events/events.py`) | Kotlin |
|---|---|
| `MessageReceived`, `AnalysisCompleted`, `HighRiskDetected`, `ModelFailed` (`@dataclass(frozen=True)`) | `sealed interface DomainEvent` con una `data class` per variante, o quattro `data class` indipendenti — da decidere in base a come verranno consumati (bus di eventi vs callback diretti) |

## Port → interface

| Python (`domain/ports/*.py`, `Protocol`) | Kotlin |
|---|---|
| `NotificationSourcePort` (proprietà `can_remove`/`can_reply`, `listen()` async generator, `remove_notification()`) | `interface NotificationSource { val canRemove: Boolean; val canReply: Boolean; fun listen(): Flow<IncomingMessage>; suspend fun removeNotification(messageId: String): Boolean }` — `AsyncIterator` → `Flow` (Kotlin coroutines) |
| `AnalyzerPort` (`analyze()` async) | `interface Analyzer { suspend fun analyze(message: IncomingMessage): AnalysisResult }` |
| `EvidenceRepositoryPort` (`store`/`get`/`list_all` async) | `interface EvidenceRepository { suspend fun store(result: AnalysisResult): String; suspend fun get(evidenceId: String): AnalysisResult?; suspend fun listAll(): List<AnalysisResult> }` |
| `ClockPort` (`now()`) | `interface Clock { fun now(): Instant }` |

## Domain service

| Python (`domain/services/`) | Kotlin | Note |
|---|---|---|
| `hash_chain.compute_record_hash(previous_hash, canonical_payload: bytes) -> str` | `fun computeRecordHash(previousHash: String, canonicalPayload: ByteArray): String` | Usare `java.security.MessageDigest.getInstance("SHA-256")`; **la canonicalizzazione del payload JSON deve produrre byte identici** a quella Python (`json.dumps(..., sort_keys=True)`) — punto delicato, va testato contro i test vector condivisi |
| `hash_chain.verify_chain(records)` | `fun verifyChain(records: List<Triple<String, String, ByteArray>>): Boolean` | 1:1 |
| `redaction.RedactionService` | `class RedactionService { private val mapping = mutableMapOf<String, String>(); fun pseudonymFor(sender: String): String { ... } }` | 1:1, stateful per istanza come in Python |

## DTO / contratti JSON

| Python (`application/dto/analysis_result_v1.py`) | Kotlin |
|---|---|
| `to_dict()`/`from_dict()` (manuali, coppie di funzioni) | `kotlinx.serialization.Serializable` su `AnalysisResult` con `@SerialName` per i nomi snake_case (`schema_version`, `message_id`, ...) — Kotlin idiomatico usa camelCase nei nomi dei campi ma serializza in snake_case per restare conforme allo schema JSON condiviso |

## Test vector condivisi

I file in `tests/vectors/*.json` (es. `analysis_result_v1_examples.json`) vanno eseguiti da
**entrambe** le suite di test (Python: `tests/unit/application/test_json_contracts.py`; Kotlin:
un equivalente JUnit/Kotest da scrivere) contro gli stessi `docs/schemas/*.schema.json` — così
un cambiamento di formato che rompe la compatibilità viene rilevato su entrambe le piattaforme.
