"""Script una tantum per Fase 3: converte unitary/multilingual-toxic-xlm-roberta in ONNX.

Non fa parte del runtime dell'app (torch/optimum non sono dipendenze di ShieldDesk):
va eseguito con dipendenze effimere, es.
    uv run --with torch --with "optimum[exporters]" --with transformers \
        python scripts/convert_toxicity_model_to_onnx.py

Licenza del modello sorgente: Apache-2.0 (verificato su
https://huggingface.co/unitary/multilingual-toxic-xlm-roberta il 2026-07-17).
"""

from pathlib import Path

MODEL_ID = "unitary/multilingual-toxic-xlm-roberta"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "models" / "toxic-xlm-roberta-onnx"


def main() -> None:
    from optimum.exporters.onnx import main_export

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    main_export(
        model_name_or_path=MODEL_ID,
        output=OUTPUT_DIR,
        task="text-classification",
    )
    print(f"Esportato in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
