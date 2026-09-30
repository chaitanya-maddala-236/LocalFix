param([switch]$PullModel)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$model = 'ai-hub-models/Qwen3-VL-4B-Instruct'

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'Arm64') {
  throw 'GenieX deployment requires native Windows ARM64 on a Snapdragon device.'
}
$geniex = Get-Command geniex -ErrorAction SilentlyContinue
if (-not $geniex) {
  throw 'Install the Qualcomm GenieX Windows ARM64 CLI from the Qwen3-VL AI Hub model Quick Start, then rerun this setup script.'
}

$env:GENIEX_DATADIR = Join-Path $projectRoot 'models\geniex'
New-Item -ItemType Directory -Force -Path $env:GENIEX_DATADIR | Out-Null
$cached = (& $geniex.Source list 2>$null | Out-String)
if ($LASTEXITCODE -ne 0) { throw 'GenieX could not list its local model cache.' }

if ($cached -notmatch 'Qwen3-VL-4B-Instruct') {
  if (-not $PullModel) {
    throw "The local model is missing. While online, run: .\backend\setup-geniex-snapdragon.ps1 -PullModel"
  }
  & $geniex.Source pull $model
  if ($LASTEXITCODE -ne 0) { throw 'GenieX could not download the selected AI Hub model.' }
}

Write-Host "GenieX model is present in the local cache: $env:GENIEX_DATADIR"
Write-Host 'The model can run offline after this one-time model download.'
