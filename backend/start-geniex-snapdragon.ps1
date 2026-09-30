$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$model = 'ai-hub-models/Qwen3-VL-4B-Instruct'

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'Arm64') {
  throw 'The GenieX runtime path requires native Windows ARM64 on a Snapdragon device.'
}
$geniex = Get-Command geniex -ErrorAction SilentlyContinue
if (-not $geniex) { throw 'GenieX is not installed. Install the Windows ARM64 CLI and follow backend/setup-geniex-snapdragon.ps1.' }

$env:GENIEX_DATADIR = Join-Path $projectRoot 'models\geniex'
$cached = (& $geniex.Source list 2>$null | Out-String)
if ($LASTEXITCODE -ne 0 -or $cached -notmatch 'Qwen3-VL-4B-Instruct') {
  throw 'The local GenieX model is missing. Run backend/setup-geniex-snapdragon.ps1 -PullModel while online.'
}

$serverUri = 'http://127.0.0.1:18181/v1/models'
$serverReady = $false
try {
  Invoke-RestMethod -Uri $serverUri -TimeoutSec 2 | Out-Null
  $serverReady = $true
} catch { }

if (-not $serverReady) {
  Start-Process -FilePath $geniex.Source `
    -ArgumentList @('serve', '--host', '127.0.0.1:18181', '--compute', 'npu') `
    -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    try {
      Invoke-RestMethod -Uri $serverUri -TimeoutSec 2 | Out-Null
      $serverReady = $true
      break
    } catch { }
  }
}
if (-not $serverReady) { throw 'The GenieX loopback server did not become ready at 127.0.0.1:18181.' }

$env:LOCALFIX_VLM_PROVIDER = 'geniex'
$env:LOCALFIX_VLM_URL = 'http://127.0.0.1:18181'
$env:LOCALFIX_VLM_MODEL = $model
$env:LOCALFIX_ROOT = $projectRoot
Write-Host 'GenieX is available on loopback. LocalFix is configured to request NPU inference; runtime status remains unverified until the device reports a successful task.'
