#!/bin/bash
#
# ShieldDesk launcher for macOS and Linux.
# Double-click from Finder (macOS) or run from a terminal.
# On first run it installs everything needed. The vault passphrase is
# asked at every launch and is never stored on disk.

set -euo pipefail

MODEL_DIR="models/toxic-xlm-roberta-onnx"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==================================="
echo "  ShieldDesk"
echo "==================================="
echo ""

# Detect the operating system
case "$(uname -s)" in
    Darwin) OS_NAME="macOS" ;;
    Linux)  OS_NAME="Linux" ;;
    *)      OS_NAME="sconosciuto" ;;
esac
echo "Sistema operativo rilevato - $OS_NAME"
echo ""

# Must run from the project root
if [ ! -f "pyproject.toml" ]; then
    echo "ERRORE - questo file non e' nella cartella del progetto."
    echo "Spostalo nella cartella che contiene pyproject.toml e riprova."
    read -r -p "Premi Invio per chiudere."
    exit 1
fi

# Make uv reachable if it was installed in this user session but not yet on PATH
if ! command -v uv >/dev/null 2>&1 && [ -f "$HOME/.local/bin/env" ]; then
    source "$HOME/.local/bin/env"
fi

# Install uv automatically if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "uv non trovato. Installazione automatica in corso..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    fi
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "ERRORE - installazione di uv non riuscita. Controlla la connessione e riprova."
    read -r -p "Premi Invio per chiudere."
    exit 1
fi

# uv downloads Python 3.12 and all dependencies into a local .venv
echo "Preparazione dell'ambiente e delle dipendenze (venv locale)..."
uv sync --quiet
echo "Ambiente pronto."
echo ""

# Download and convert the ONNX model once, if not already present.
# Kept non-fatal - if it fails the app still runs with the rule-based analyzer.
if [ ! -f "$MODEL_DIR/model.onnx" ]; then
    echo "Modello AI non presente. Scaricamento e conversione (una tantum,"
    echo "richiede internet e alcuni minuti)..."
    if uv run --with torch --with "optimum-onnx[onnxruntime]" --with transformers \
        python scripts/convert_toxicity_model_to_onnx.py; then
        echo "Modello AI installato."
    else
        echo "AVVISO - installazione del modello non riuscita."
        echo "L'app partira' comunque usando l'analisi con regole."
    fi
    echo ""
fi

# Modello SLM (opzionale): abilita l'analisi contestuale che riduce i falsi
# positivi valutando ogni messaggio nel contesto della conversazione. ~1 GB.
# Non-fatale e saltabile: senza, l'app usa la sola analisi veloce.
SLM_DIR="models/qwen2.5-1.5b-instruct-gguf"
SLM_FILE="$SLM_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
SLM_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
SLM_SHA256="6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"

if [ ! -f "$SLM_FILE" ]; then
    echo "Modello di analisi contestuale (SLM) non presente."
    echo "E' OPZIONALE: migliora l'accuratezza riducendo i falsi positivi (valuta i"
    echo "messaggi nel contesto della conversazione). Richiede circa 1 GB di download."
    read -r -p "Vuoi scaricarlo ora? [s/N] " REPLY_SLM
    case "$REPLY_SLM" in
        [sSyY]*)
            mkdir -p "$SLM_DIR"
            TMP_SLM="$SLM_FILE.part"
            echo "Scaricamento in corso (una tantum, alcuni minuti)..."
            if curl -L --fail -o "$TMP_SLM" "$SLM_URL"; then
                # Verifica integrita' SHA-256 prima di installare: mai un binario non verificato.
                ACTUAL_SHA="$( (shasum -a 256 "$TMP_SLM" 2>/dev/null || sha256sum "$TMP_SLM" 2>/dev/null) | awk '{print $1}')"
                if [ "$ACTUAL_SHA" = "$SLM_SHA256" ]; then
                    mv "$TMP_SLM" "$SLM_FILE"
                    echo "Modello SLM installato e verificato (SHA-256 corretto)."
                else
                    rm -f "$TMP_SLM"
                    echo "ERRORE - hash del file scaricato non corrispondente: file eliminato."
                    echo "L'app partira' comunque con la sola analisi veloce."
                fi
            else
                rm -f "$TMP_SLM"
                echo "AVVISO - download non riuscito. L'app partira' con la sola analisi veloce."
            fi
            echo ""
            ;;
        *)
            echo "Saltato. Potrai attivarlo in seguito rilanciando questo avvio."
            echo ""
            ;;
    esac
fi

# Ask the passphrase without echoing it, never stored
echo "Inserisci la passphrase della cassaforte."
echo "(Al primo avvio in assoluto scegline una nuova e annota la recovery key"
echo " che comparira' qui sotto - e' l'unico modo di recuperare i dati.)"
echo ""
read -r -s -p "Passphrase - " SHIELDDESK_DEV_PASSPHRASE
echo ""

if [ -z "$SHIELDDESK_DEV_PASSPHRASE" ]; then
    echo ""
    echo "ERRORE - passphrase vuota. Avvio annullato per non creare un vault effimero."
    read -r -p "Premi Invio per chiudere."
    exit 1
fi

export SHIELDDESK_DEV_PASSPHRASE

echo ""
echo "Avvio di ShieldDesk..."
echo "Si aprira' automaticamente nel browser. Se non accade, apri l'indirizzo"
echo "che comparira' qui sotto. Chiudi con Ctrl+C quando hai finito."
echo ""

uv run python -m shielddesk.web_main

echo ""
read -r -p "ShieldDesk e' stato chiuso. Premi Invio per terminare."
