param([switch]$GenieX)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$armPython = $env:LOCALFIX_PYTHON
if (-not $armPython -or -not (Test-Path -LiteralPath $armPython)) {
  throw 'Set LOCALFIX_PYTHON to the full path of a native Windows ARM64 Python 3.11 executable.'
}
$pythonInfo = & $armPython -c "import platform,sys; print(f'{platform.machine()}|{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $pythonInfo -ne 'ARM64|3.11') {
  throw "Snapdragon QNN requires native Windows ARM64 Python 3.11.x. Detected: $pythonInfo"
}
$venv = Join-Path $projectRoot '.venv-snapdragon'
$python = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
  & $armPython -m venv $venv
  & $python -m pip install --upgrade pip
  & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-snapdragon-arm64.txt')
}
$providerCheck = & $python -c "import onnxruntime as ort; print('QNNExecutionProvider' in ort.get_available_providers())"
if ($LASTEXITCODE -ne 0 -or $providerCheck -ne 'True') {
  throw 'QNNExecutionProvider is not available in this environment. Review the ONNX Runtime QNN setup before starting LocalFix.'
}
$env:LOCALFIX_ROOT = $projectRoot
if ($GenieX) {
  . (Join-Path $PSScriptRoot 'start-geniex-snapdragon.ps1')
} else {
  . (Join-Path $PSScriptRoot 'start-local-vlm.ps1')
}
& $python -m uvicorn app.main:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8000
