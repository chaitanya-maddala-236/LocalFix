$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$apiModelFragment = 'Qwen3-VL-4B-Instruct'

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'Arm64') {
  throw 'The GenieX runtime path requires native Windows ARM64 on a Snapdragon device.'
}
$geniexCommand = Get-Command geniex -CommandType Application -ErrorAction SilentlyContinue
$geniexPath = if ($env:LOCALFIX_GENIEX_EXE -and (Test-Path -LiteralPath $env:LOCALFIX_GENIEX_EXE)) {
  $env:LOCALFIX_GENIEX_EXE
} elseif ($geniexCommand) {
  $geniexCommand.Source
} else {
  $installedPath = Join-Path $env:LOCALAPPDATA 'GenieX CLI\geniex.exe'
  if (Test-Path -LiteralPath $installedPath) { $installedPath } else { $null }
}
if (-not $geniexPath) { throw 'GenieX is not installed. Install the Windows ARM64 CLI or set LOCALFIX_GENIEX_EXE to its full path.' }

$env:GENIEX_DATADIR = Join-Path $projectRoot 'models\geniex'
$cached = (& $geniexPath list 2>$null | Out-String)
if ($LASTEXITCODE -ne 0 -or $cached -notmatch 'Qwen3-VL-4B-Instruct') {
  throw 'The local GenieX model is missing. Run backend/setup-geniex-snapdragon.ps1 -PullModel while online.'
}

$serverUri = 'http://127.0.0.1:18181/v1/models'
$serverReady = $false
$modelForRequest = $null
$existingServerResponded = $false
try {
  $modelsResponse = Invoke-RestMethod -Uri $serverUri -TimeoutSec 2
  $existingServerResponded = $true
} catch { }

if ($existingServerResponded) {
  $modelEntry = @($modelsResponse.data) | Where-Object { $_.id -match [regex]::Escape($apiModelFragment) } | Select-Object -First 1
  if (-not $modelEntry) {
    $listed = @($modelsResponse.data | ForEach-Object { $_.id }) -join ', '
    throw "A GenieX server already occupies 127.0.0.1:18181 but does not expose $apiModelFragment. Listed models: $listed"
  }
  $modelForRequest = [string]$modelEntry.id -replace ':[^/:]+$', ''
  $serverReady = $true
}

if (-not $serverReady) {
  $logDir = Join-Path $projectRoot 'logs'
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  Start-Process -FilePath $geniexPath `
    -ArgumentList @('serve', '--host', '127.0.0.1:18181', '--compute', 'npu') `
    -WorkingDirectory $projectRoot -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDir 'geniex-server.out.log') `
    -RedirectStandardError (Join-Path $logDir 'geniex-server.err.log') | Out-Null
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Seconds 1
    try {
      $modelsResponse = Invoke-RestMethod -Uri $serverUri -TimeoutSec 2
      $modelEntry = @($modelsResponse.data) | Where-Object { $_.id -match [regex]::Escape($apiModelFragment) } | Select-Object -First 1
      if (-not $modelEntry) { continue }
      $modelForRequest = [string]$modelEntry.id -replace ':[^/:]+$', ''
      $serverReady = $true
      break
    } catch { }
  }
}
if (-not $serverReady) {
  $errorLog = Join-Path $projectRoot 'logs\geniex-server.err.log'
  $logTail = if (Test-Path -LiteralPath $errorLog) { (Get-Content -LiteralPath $errorLog -Tail 20) -join [Environment]::NewLine } else { 'No GenieX log was produced.' }
  throw "The GenieX loopback server did not expose $apiModelFragment at 127.0.0.1:18181. Error log: $errorLog`n$logTail"
}

$env:LOCALFIX_VLM_PROVIDER = 'geniex'
$env:LOCALFIX_VLM_URL = 'http://127.0.0.1:18181'
$env:LOCALFIX_VLM_MODEL = $modelForRequest
$env:LOCALFIX_ROOT = $projectRoot
Write-Host "GenieX model ready on loopback: $modelForRequest. LocalFix requests NPU inference; status remains unverified until an on-device inference and provider check succeeds."
