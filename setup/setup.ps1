# ITHACA setup for Windows. Run from PowerShell:  powershell -ExecutionPolicy Bypass -File setup\setup.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OllamaModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "qwen2.5vl:3b" }
function Say($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "!! $m" -ForegroundColor Yellow }
function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Warn "$cmd is missing: $hint"; $script:Missing = $true }
}
$script:Missing = $false

Say "Checking tools"
Need "python" "install Python 3.11+ from python.org (tick 'Add to PATH')"
Need "node" "install Node.js LTS from nodejs.org"
Need "npm" "comes with Node.js"
Need "ffmpeg" "needed for recap videos: winget install Gyan.FFmpeg"
if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) { Warn "ollama is missing: needed for the local Oracle model (https://ollama.com)" }
if ($script:Missing) { Warn "Install the missing tools above, then run this again."; exit 1 }

Say "Backend: virtual environment and Python packages"
Set-Location "$Root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -q --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt pytest
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "created backend\.env (fill in your keys)" }

Say "Frontend: Node packages"
Set-Location "$Root\frontend"
npm ci --silent
if (-not (Test-Path ".env.local")) { Copy-Item ".env.example" ".env.local"; Write-Host "created frontend\.env.local" }

Say "Local Oracle model (Ollama)"
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
  if (-not (ollama list | Select-String -SimpleMatch $OllamaModel)) { ollama pull $OllamaModel }
}

Say "Tests"
Set-Location "$Root\backend"
& .\.venv\Scripts\python.exe -m pytest -q tests

Say "Done. Start everything with:  powershell -ExecutionPolicy Bypass -File setup\dev.ps1"
