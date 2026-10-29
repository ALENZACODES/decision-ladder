# Decision Ladder: go live on Nebius Token Factory in one command (Windows PowerShell).
#   powershell -ExecutionPolicy Bypass -File scripts\go_live.ps1
# Steps: check Python -> ask for keys (not saved to disk) -> list models -> smoke test -> eval -> start the app.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $py) { Write-Host "Python 3.10+ is required: https://www.python.org/downloads/" -ForegroundColor Red; exit 1 }
$python = $py.Source
& $python -c "import sys; assert sys.version_info >= (3,10), sys.version" ; if ($LASTEXITCODE) { exit 1 }

function Read-Secret($label) {
  $s = Read-Host -AsSecureString $label
  return [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}
if (-not $env:NEBIUS_API_KEY) { $env:NEBIUS_API_KEY = Read-Secret "Paste your Nebius Token Factory API key (input hidden)" }
if (-not $env:TAVILY_API_KEY) {
  $t = Read-Secret "Paste your Tavily API key (optional, Enter to skip)"
  if ($t) { $env:TAVILY_API_KEY = $t }
}

Write-Host "`n== 1/4  Models visible to your key ==" -ForegroundColor Cyan
& $python -m decision_ladder models
if ($LASTEXITCODE) { Write-Host "Could not list models: check the key and your internet connection." -ForegroundColor Red; exit 1 }

Write-Host "`n== 2/4  Live smoke test (writes smoke_report.json) ==" -ForegroundColor Cyan
& $python -m decision_ladder smoke
$smoke = $LASTEXITCODE

Write-Host "`n== 3/4  Evaluation (writes eval_report.json) ==" -ForegroundColor Cyan
& $python -m decision_ladder eval

Write-Host "`n== 4/4  Starting the app on http://localhost:8000 (Ctrl+C to stop) ==" -ForegroundColor Cyan
if ($smoke) { Write-Host "Smoke test had failures: see smoke_report.json before recording the video." -ForegroundColor Yellow }
Start-Process "http://localhost:8000"
& $python -m decision_ladder serve 8000
