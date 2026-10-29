# Same as update_data.py, for computers without Python. Each step keeps the old file if it fails.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ok = 0
$series = [ordered]@{ policy = "V39079"; prime = "V80691311"; posted = "V80691335" }
$rates = @{}; $dates = @()
foreach ($k in $series.Keys) {
  $code = $series[$k]
  try {
    $r = Invoke-RestMethod -Uri "https://www.bankofcanada.ca/valet/observations/$code/json?recent=1" -TimeoutSec 20
    $o = $r.observations[-1]; $rates[$k] = [double]$o.$code.v; $dates += $o.d
  } catch { Write-Host "  ! Bank of Canada $k rate: not reachable; keeping the saved value" }
}
if ($rates.Count -gt 0) {
  $path = Join-Path $root "data\rates.json"
  $out = [ordered]@{}
  if (Test-Path $path) { try { (Get-Content $path -Raw | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $out[$_.Name] = $_.Value } } catch {} }
  foreach ($k in $rates.Keys) { $out[$k] = $rates[$k] }
  $out["d"] = ($dates | Sort-Object)[-1]; $out["source"] = "Bank of Canada Valet API"
  ($out | ConvertTo-Json -Compress) | Set-Content -Path "$path.tmp" -Encoding UTF8
  Move-Item -Force "$path.tmp" $path; $ok++
  Write-Host ("  + Bank of Canada: " + (($rates.Keys | ForEach-Object { "$_ $($rates[$_])%" }) -join ", "))
}
$dest = Join-Path $root "vendor\chart.umd.min.js"
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
foreach ($u in @("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js","https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js","https://unpkg.com/chart.js@4.5.1/dist/chart.umd.min.js")) {
  try { Invoke-WebRequest -Uri $u -OutFile "$dest.tmp" -UseBasicParsing -TimeoutSec 30
        if ((Get-Item "$dest.tmp").Length -gt 100000) { Move-Item -Force "$dest.tmp" $dest; $ok++; Write-Host "  + Chart library saved for offline use"; break } } catch {}
}
if ($ok -gt 0) { try {
  $up = Join-Path $root "data\updated.json"; $j = Get-Content $up -Raw | ConvertFrom-Json
  $j.date = (Get-Date -Format "yyyy-MM-dd"); $j.checked = (Get-Date -Format "yyyy-MM-ddTHH:mm")
  ($j | ConvertTo-Json -Compress) | Set-Content -Path $up -Encoding UTF8
} catch { Write-Host "  ! Couldn't update the Live date" } }
if ($ok -gt 0) { Write-Host "`n  Done." } else { Write-Host "`n  Nothing could be updated (offline?). The app still works with the data it has." }
