"""Genera product/slm_model_manifest.json con l'hash SHA-256 del modello GGUF (ADR-011).

Stesso schema di scripts/generate_model_manifest.py (campo `tier` differente:
"slm" invece di "fast"), formalizzato qui invece di restare uno script inline
usato una tantum in Fase 4 — necessario per rigenerare il manifest in modo
riproducibile se il modello viene ri-scaricato.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

MODEL_FILE = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "qwen2.5-1.5b-instruct-gguf"
    / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)
MANIFEST_PATH = Path(__file__).resolve().parent.parent / "product" / "slm_model_manifest.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    manifest = {
        "schema_version": "1.0",
        "model_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "source_url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "license": "apache-2.0",
        "license_verified_on": "2026-07-17",
        "tier": "slm",
        "quantization": "Q4_K_M",
        "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "sha256": sha256_of(MODEL_FILE),
        "generated_at": datetime.now(UTC).isoformat(),
        "notes": "Modello ufficiale Qwen, non una quantizzazione di terze parti.",
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest scritto in {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
