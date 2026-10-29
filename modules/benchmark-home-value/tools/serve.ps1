# Tiny local web server for Benchmark Home Value (used when Python isn't installed).
# Serves only files inside the app folder, only to this computer (localhost).
param([int]$Port = 8765, [switch]$NoBrowser)
$root = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:${Port}/")
try { $listener.Start() }
catch {
  Write-Host "Couldn't start the local server on port ${Port}: $($_.Exception.Message)"
  Write-Host "You can still use the online version of Benchmark Home Value."
  Read-Host "Press Enter to close"
  exit 1
}
if (-not $NoBrowser) { Start-Process "http://localhost:${Port}/index.html" }
Write-Host "Benchmark Home Value is running at http://localhost:${Port}/  (close this window to stop)"
$types = @{ ".html"="text/html; charset=utf-8"; ".json"="application/json"; ".js"="text/javascript; charset=utf-8"; ".css"="text/css";
            ".png"="image/png"; ".svg"="image/svg+xml"; ".ico"="image/x-icon"; ".txt"="text/plain; charset=utf-8"; ".csv"="text/csv"; ".md"="text/plain; charset=utf-8" }
while ($listener.IsListening) {
  $ctx = $null
  try {
    $ctx = $listener.GetContext()
    $rel = [Uri]::UnescapeDataString($ctx.Request.Url.AbsolutePath.TrimStart('/'))
    if ([string]::IsNullOrEmpty($rel)) { $rel = "index.html" }
    $file = [System.IO.Path]::GetFullPath((Join-Path $root $rel))
    if (-not $file.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $file -PathType Leaf)) {
      $ctx.Response.StatusCode = 404; $ctx.Response.Close(); continue
    }
    $ext = [System.IO.Path]::GetExtension($file).ToLower()
    $ctx.Response.ContentType = $(if ($types.ContainsKey($ext)) { $types[$ext] } else { "application/octet-stream" })
    $ctx.Response.Headers.Add("Cache-Control", "no-cache")
    $bytes = [System.IO.File]::ReadAllBytes($file)
    $ctx.Response.ContentLength64 = $bytes.Length
    $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    $ctx.Response.Close()
  } catch {
    if ($ctx) { try { $ctx.Response.Abort() } catch {} }
  }
}
