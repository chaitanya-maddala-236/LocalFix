$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw 'Run backend\run.ps1 once to create the project virtual environment before setup.'
}
$architecture = & $venvPython -c "import platform; print(platform.machine())"
if ($LASTEXITCODE -ne 0 -or $architecture -ne 'AMD64') {
  throw 'This optional CPU AI bundle currently supports the tested Windows AMD64 development host. It does not install Snapdragon/QNN runtimes.'
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-local-ai.txt')
& $venvPython (Join-Path $PSScriptRoot 'setup_local_models.py') --download
if ($LASTEXITCODE -ne 0) { throw 'Local model preparation failed. The backend will continue to show the unavailable model stages.' }
Write-Host 'Local OCR, English speech, and semantic retrieval assets are ready. Disconnecting the network will not disable these local models.'
