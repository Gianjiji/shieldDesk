# ShieldDesk launcher for Windows.
# Right-click and choose "Run with PowerShell", or run from a terminal.
# On first run it installs everything needed. The vault passphrase is
# asked at every launch and is never stored on disk.

$ErrorActionPreference = "Stop"
$ModelDir = "models\toxic-xlm-roberta-onnx"

# Work from the folder this script lives in
Set-Location -Path $PSScriptRoot

Write-Host "==================================="
Write-Host "  ShieldDesk"
Write-Host "==================================="
Write-Host ""
Write-Host "Sistema operativo rilevato - Windows"
Write-Host ""

# Must run from the project root
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "ERRORE - questo file non e' nella cartella del progetto."
    Write-Host "Spostalo nella cartella che contiene pyproject.toml e riprova."
    Read-Host "Premi Invio per chiudere"
    exit 1
}

# Helper - is uv reachable
function Test-Uv {
    return [bool](Get-Command uv -ErrorAction SilentlyContinue)
}

# Install uv automatically if missing
if (-not (Test-Uv)) {
    Write-Host "uv non trovato. Installazione automatica in corso..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    # Add the default install location to PATH for this session
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

if (-not (Test-Uv)) {
    Write-Host "ERRORE - installazione di uv non riuscita. Controlla la connessione e riprova."
    Read-Host "Premi Invio per chiudere"
    exit 1
}

# uv downloads Python 3.12 and all dependencies into a local .venv
Write-Host "Preparazione dell'ambiente e delle dipendenze (venv locale)..."
uv sync --quiet
Write-Host "Ambiente pronto."
Write-Host ""

# Download and convert the ONNX model once, if not already present.
# Non-fatal - if it fails the app still runs with the rule-based analyzer.
if (-not (Test-Path "$ModelDir\model.onnx")) {
    Write-Host "Modello AI non presente. Scaricamento e conversione (una tantum,"
    Write-Host "richiede internet e alcuni minuti)..."
    uv run --with torch --with "optimum-onnx[onnxruntime]" --with transformers python scripts/convert_toxicity_model_to_onnx.py
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Modello AI installato."
    } else {
        Write-Host "AVVISO - installazione del modello non riuscita."
        Write-Host "L'app partira' comunque usando l'analisi con regole."
    }
    Write-Host ""
}

# Modello SLM (opzionale): abilita l'analisi contestuale che riduce i falsi
# positivi valutando ogni messaggio nel contesto della conversazione. ~1 GB.
# Non-fatale e saltabile: senza, l'app usa la sola analisi veloce.
$SlmDir = "models\qwen2.5-1.5b-instruct-gguf"
$SlmFile = "$SlmDir\qwen2.5-1.5b-instruct-q4_k_m.gguf"
$SlmUrl = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
$SlmSha256 = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"

if (-not (Test-Path $SlmFile)) {
    Write-Host "Modello di analisi contestuale (SLM) non presente."
    Write-Host "E' OPZIONALE: migliora l'accuratezza riducendo i falsi positivi (valuta i"
    Write-Host "messaggi nel contesto della conversazione). Richiede circa 1 GB di download."
    $replySlm = Read-Host "Vuoi scaricarlo ora? [s/N]"
    if ($replySlm -match '^[sSyY]') {
        New-Item -ItemType Directory -Force -Path $SlmDir | Out-Null
        $tmpSlm = "$SlmFile.part"
        Write-Host "Scaricamento in corso (una tantum, alcuni minuti)..."
        # ProgressPreference silenzioso: la barra di Invoke-WebRequest rallenta molto i file grandi.
        $prevProgress = $ProgressPreference
        $ProgressPreference = "SilentlyContinue"
        try {
            Invoke-WebRequest -Uri $SlmUrl -OutFile $tmpSlm -UseBasicParsing
            # Verifica integrita' SHA-256 prima di installare: mai un binario non verificato.
            $actual = (Get-FileHash -Algorithm SHA256 -Path $tmpSlm).Hash.ToLower()
            if ($actual -eq $SlmSha256) {
                Move-Item -Force $tmpSlm $SlmFile
                Write-Host "Modello SLM installato e verificato (SHA-256 corretto)."
            } else {
                Remove-Item -Force $tmpSlm
                Write-Host "ERRORE - hash del file scaricato non corrispondente: file eliminato."
                Write-Host "L'app partira' comunque con la sola analisi veloce."
            }
        } catch {
            if (Test-Path $tmpSlm) { Remove-Item -Force $tmpSlm }
            Write-Host "AVVISO - download non riuscito. L'app partira' con la sola analisi veloce."
        } finally {
            $ProgressPreference = $prevProgress
        }
        Write-Host ""
    } else {
        Write-Host "Saltato. Potrai attivarlo in seguito rilanciando questo avvio."
        Write-Host ""
    }
}

# Ask the passphrase without echoing it, never stored
Write-Host "Inserisci la passphrase della cassaforte."
Write-Host "(Al primo avvio in assoluto scegline una nuova e annota la recovery key"
Write-Host " che comparira' qui sotto - e' l'unico modo di recuperare i dati.)"
Write-Host ""
$secure = Read-Host "Passphrase -" -AsSecureString
$ptr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

if ([string]::IsNullOrEmpty($plain)) {
    Write-Host ""
    Write-Host "ERRORE - passphrase vuota. Avvio annullato per non creare un vault effimero."
    Read-Host "Premi Invio per chiudere"
    exit 1
}

$env:SHIELDDESK_DEV_PASSPHRASE = $plain

Write-Host ""
Write-Host "Avvio di ShieldDesk..."
Write-Host "Si aprira' automaticamente nel browser. Se non accade, apri l'indirizzo"
Write-Host "che comparira' qui sotto. Chiudi con Ctrl+C quando hai finito."
Write-Host ""

uv run python -m shielddesk.web_main

# Clear the passphrase from memory once the app has closed
$plain = $null
$env:SHIELDDESK_DEV_PASSPHRASE = $null

Write-Host ""
Read-Host "ShieldDesk e' stato chiuso. Premi Invio per terminare"
