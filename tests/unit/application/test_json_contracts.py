"""Verifica che i DTO Python siano conformi ai contratti JSON formali in
docs/schemas/ (Fase 10): questi schema sono ciò a cui il futuro porting
Kotlin/Android deve aderire, quindi devono restare sincronizzati con
l'implementazione reale, non solo con l'intenzione.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from shielddesk.application.dto.analysis_result_v1 import from_dict, to_dict
from shielddesk.domain.entities.analysis_result import AnalysisResult

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "schemas"
_VECTORS_DIR = Path(__file__).resolve().parent.parent.parent / "vectors"
_PRODUCT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "product"


def _build_registry() -> Registry:
    resources = []
    for schema_path in _SCHEMAS_DIR.glob("*.schema.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        resources.append((schema_path.name, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _validator_for(schema_filename: str) -> Draft202012Validator:
    schema = json.loads((_SCHEMAS_DIR / schema_filename).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=_build_registry())


def _load_vector_examples() -> list[tuple[str, dict[str, Any]]]:
    data = json.loads(
        (_VECTORS_DIR / "analysis_result_v1_examples.json").read_text(encoding="utf-8")
    )
    return [(example["name"], example["value"]) for example in data["examples"]]


@pytest.mark.parametrize("name,value", _load_vector_examples())
def test_analysis_result_vector_conforms_to_schema(name: str, value: dict[str, Any]) -> None:
    validator = _validator_for("analysis_result_v1.schema.json")
    errors = list(validator.iter_errors(value))
    assert not errors, f"{name}: {[e.message for e in errors]}"


@pytest.mark.parametrize("name,value", _load_vector_examples())
def test_analysis_result_vector_roundtrips_through_dto(name: str, value: dict[str, Any]) -> None:
    result: AnalysisResult = from_dict(value)
    assert to_dict(result) == value


def test_onnx_model_manifest_conforms_to_schema() -> None:
    manifest_path = _PRODUCT_DIR / "model_manifest.json"
    if not manifest_path.exists():
        pytest.skip("model_manifest.json assente (nessun modello ONNX importato)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    validator = _validator_for("model_manifest_v1.schema.json")
    errors = list(validator.iter_errors(manifest))
    assert not errors, [e.message for e in errors]


def test_slm_model_manifest_conforms_to_schema() -> None:
    manifest_path = _PRODUCT_DIR / "slm_model_manifest.json"
    if not manifest_path.exists():
        pytest.skip("slm_model_manifest.json assente (nessun modello SLM importato)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    validator = _validator_for("model_manifest_v1.schema.json")
    errors = list(validator.iter_errors(manifest))
    assert not errors, [e.message for e in errors]
