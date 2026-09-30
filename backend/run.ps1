$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:LOCALFIX_ROOT = $projectRoot
& (Join-Path $PSScriptRoot 'start-local-vlm.ps1')
$venv = Join-Path $projectRoot '.venv'
$python = if (Test-Path (Join-Path $venv 'Scripts\python.exe')) { Join-Path $venv 'Scripts\python.exe' } else { 'python' }
if ($python -eq 'python') {
  python -m venv $venv
  $python = Join-Path $venv 'Scripts\python.exe'
  & $python -m pip install --upgrade pip
  & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
}
& $python -m uvicorn app.main:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8000 --reload
