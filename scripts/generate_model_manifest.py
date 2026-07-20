"""Genera product/model_manifest.json con l'hash SHA-256 del modello ONNX esportato.

ADR-011 (ANALYSIS.md): ogni modello importato deve essere verificabile via hash
rispetto a un manifest, non semplicemente fidato perché presente su disco.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "toxic-xlm-roberta-onnx"
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "product" / "model_manifest.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    model_file = MODEL_DIR / "model.onnx"
    manifest = {
        "schema_version": "1.0",
        "model_id": "unitary/multilingual-toxic-xlm-roberta",
        "source_url": "https://huggingface.co/unitary/multilingual-toxic-xlm-roberta",
        "license": "apache-2.0",
        "license_verified_on": "2026-07-17",
        "tier": "fast",
        "labels": ["toxic"],
        "file": "model.onnx",
        "sha256": sha256_of(model_file),
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": (
            "Soglie di RiskLevel non calibrate (vedi infrastructure/ai/onnx_analyzer.py). "
            "Verificato su un piccolo smoke-set italiano, non su un benchmark statistico."
        ),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest scritto in {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
