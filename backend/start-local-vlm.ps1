$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$ollama = Join-Path $projectRoot 'models\ollama_runtime\ollama.exe'
if (-not (Test-Path -LiteralPath $ollama)) { Write-Host 'Local VLM runtime is not installed. Run backend\setup-local-vlm.ps1 while online.'; return }

$env:OLLAMA_MODELS = Join-Path $projectRoot 'models\ollama'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
try {
  Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1 | Out-Null
  return
} catch { }

Start-Process -FilePath $ollama -ArgumentList 'serve' -WorkingDirectory (Split-Path -Parent $ollama) -WindowStyle Hidden | Out-Null
for ($attempt = 0; $attempt -lt 20; $attempt++) {
  Start-Sleep -Milliseconds 500
  try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 1 | Out-Null
    Write-Host 'Local VLM service is listening on 127.0.0.1:11434. Cloud features are disabled for this process.'
    return
  } catch { }
}
Write-Warning 'Ollama did not become ready. LocalFix will continue without VLM reasoning.'
