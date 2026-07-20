"""Serializzazione JSON versionata di AnalysisResult (contratto condiviso con Android)."""

from datetime import datetime
from typing import Any

from shielddesk.domain.entities.analysis_result import AnalysisResult, AnalysisTier, CategoryScore
from shielddesk.domain.value_objects.confidence import Confidence
from shielddesk.domain.value_objects.risk_level import RiskLevel
from shielddesk.domain.value_objects.threat_category import ThreatCategory


def to_dict(result: AnalysisResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "message_id": result.message_id,
        "tier": result.tier.value,
        "model_id": result.model_id,
        "model_version": result.model_version,
        "prompt_version": result.prompt_version,
        "timestamp": result.timestamp.isoformat(),
        "risk_level": int(result.risk_level),
        "categories": [
            {"category": score.category.value, "confidence": score.confidence.value}
            for score in result.categories
        ],
        "latency_ms": result.latency_ms,
    }


def from_dict(data: dict[str, Any]) -> AnalysisResult:
    return AnalysisResult(
        schema_version=data["schema_version"],
        message_id=data["message_id"],
        tier=AnalysisTier(data["tier"]),
        model_id=data["model_id"],
        model_version=data["model_version"],
        prompt_version=data["prompt_version"],
        timestamp=datetime.fromisoformat(data["timestamp"]),
        risk_level=RiskLevel(data["risk_level"]),
        categories=tuple(
            CategoryScore(
                category=ThreatCategory(entry["category"]),
                confidence=Confidence(entry["confidence"]),
            )
            for entry in data["categories"]
        ),
        latency_ms=data["latency_ms"],
    )
