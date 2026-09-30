$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot 'models\ollama_runtime'
$modelStore = Join-Path $projectRoot 'models\ollama'
$ollama = Join-Path $runtimeDir 'ollama.exe'
$model = if ($env:LOCALFIX_VLM_MODEL) { $env:LOCALFIX_VLM_MODEL } else {
  (Get-Content -LiteralPath (Join-Path $projectRoot 'models\manifest.json') -Raw | ConvertFrom-Json).local_services.reasoning.model
}
if (-not $model -or $model -match 'cloud') { throw 'LocalFix requires a local Qwen3-VL model tag. Cloud model tags are not allowed.' }
$manifestPath = Join-Path $projectRoot 'models\manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$manifest.local_services.reasoning.model = $model
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 12), [System.Text.UTF8Encoding]::new($false))
New-Item -ItemType Directory -Force -Path $runtimeDir, $modelStore | Out-Null

if (-not (Test-Path -LiteralPath $ollama)) {
  $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
  $packageArchitecture = switch ($architecture) {
    'X64' { 'amd64' }
    'Arm64' { 'arm64' }
    default { throw "Ollama local VLM setup supports Windows x64 or ARM64. Detected $architecture." }
  }
  $archive = Join-Path $runtimeDir "ollama-windows-$packageArchitecture.zip"
  Invoke-WebRequest -Uri "https://ollama.com/download/ollama-windows-$packageArchitecture.zip" -OutFile $archive -UseBasicParsing
  Expand-Archive -LiteralPath $archive -DestinationPath $runtimeDir -Force
  Remove-Item -LiteralPath $archive
}

$signature = Get-AuthenticodeSignature -FilePath $ollama
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Ollama Inc\.') {
  throw 'The Ollama executable signature is not valid for Ollama Inc.; the local VLM runtime was not started.'
}
$versionText = (& $ollama --version 2>&1 | Out-String)
if ($versionText -notmatch '(\d+\.\d+\.\d+)') { throw "Could not read the local Ollama version: $versionText" }
if ([version]$Matches[1] -lt [version]'0.12.7') { throw "Qwen3-VL needs Ollama 0.12.7 or newer. Found $($Matches[1])." }

$env:OLLAMA_MODELS = $modelStore
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:LOCALFIX_VLM_MODEL = $model
$tagsUri = 'http://127.0.0.1:11434/api/tags'
$serviceAlreadyRunning = $false
try {
  $tags = Invoke-RestMethod -Uri $tagsUri -TimeoutSec 1
  $serviceAlreadyRunning = $true
} catch {
  & (Join-Path $PSScriptRoot 'start-local-vlm.ps1')
  for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    try { $tags = Invoke-RestMethod -Uri $tagsUri -TimeoutSec 1; break } catch { }
  }
}
if (-not $tags) { throw 'Ollama did not become ready on 127.0.0.1:11434.' }
$installed = @($tags.models | ForEach-Object { $_.name })
$hasModel = $installed -contains $model
if (-not $hasModel) {
  if ($serviceAlreadyRunning) {
    throw 'A different Ollama server already occupies loopback port 11434. Stop it and rerun setup so model files are stored under D:\LocalFix\models\ollama.'
  }
  & $ollama pull $model
  if ($LASTEXITCODE -ne 0) { throw "Could not download $model. The demo continues with VLM marked unavailable." }
}
$finalTags = Invoke-RestMethod -Uri $tagsUri -TimeoutSec 3
$finalNames = @($finalTags.models | ForEach-Object { $_.name })
if ($finalNames -notcontains $model) {
  throw "The configured local model $model is not visible to the loopback Ollama service."
}
Write-Host "Local VLM ready: $model. Model files are stored on D:. Ollama cloud models are disabled for the service started by LocalFix. NPU use is not claimed."
