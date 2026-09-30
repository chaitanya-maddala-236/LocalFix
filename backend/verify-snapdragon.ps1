[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ImagePath,
  [string]$ApiBaseUrl = 'http://127.0.0.1:8000',
  [string]$ComponentTarget = 'motor relay',
  [switch]$RequireOffline,
  [switch]$RunBenchmark
)

$ErrorActionPreference = 'Stop'

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'Arm64') {
  throw 'This verification must run on the target Windows ARM64 Snapdragon laptop; this machine is not ARM64.'
}

$resolvedImage = (Resolve-Path -LiteralPath $ImagePath).Path
$extension = [System.IO.Path]::GetExtension($resolvedImage).ToLowerInvariant()
$mimeType = switch ($extension) {
  '.jpg' { 'image/jpeg' }
  '.jpeg' { 'image/jpeg' }
  '.png' { 'image/png' }
  '.webp' { 'image/webp' }
  default { throw 'Use a local JPEG, PNG, or WebP image of the equipment showing its display and label.' }
}
$imageBytes = [System.IO.File]::ReadAllBytes($resolvedImage)
if ($imageBytes.Length -eq 0 -or $imageBytes.Length -gt 20MB) {
  throw 'The selected image must be between 1 byte and 20 MB.'
}
$imageBase64 = [Convert]::ToBase64String($imageBytes)
$imageHash = (Get-FileHash -LiteralPath $resolvedImage -Algorithm SHA256).Hash.ToLowerInvariant()

$health = Invoke-RestMethod -Uri "$ApiBaseUrl/health" -TimeoutSec 10
if ($health.status -ne 'ready' -or $health.database -ne 'ready') {
  throw 'LocalFix API/database is not ready.'
}
$runtime = Invoke-RestMethod -Uri "$ApiBaseUrl/runtime/status" -TimeoutSec 15
if ($runtime.models.reasoning -ne 'ready' -or $runtime.model_details.reasoning.backend -notmatch '^GenieX') {
  throw 'The configured local GenieX reasoning model is not ready. Review Runtime status and logs/geniex-server.err.log.'
}
if ($RequireOffline -and $runtime.network -ne 'offline') {
  throw "Offline verification requested, but Windows reports network state '$($runtime.network)'. Disable network adapters manually, then rerun."
}

$ocr = Invoke-RestMethod -Uri "$ApiBaseUrl/vision/ocr" -Method Post -ContentType 'application/json' `
  -Body (@{ image_base64 = $imageBase64 } | ConvertTo-Json -Compress) -TimeoutSec 60
$diagnosis = Invoke-RestMethod -Uri "$ApiBaseUrl/diagnose" -Method Post -ContentType 'application/json' `
  -Body (@{
    question = 'What does fault E07 indicate for this ACM-4200? Give one short explanation supported by the manual.'
    equipment_model = 'DemoTech ACM-4200'
    observations = @('The technician selected this image for a local Snapdragon verification run.')
    image_base64 = $imageBase64
    image_mime_type = $mimeType
  } | ConvertTo-Json -Depth 5 -Compress) -TimeoutSec 240
if ($diagnosis.answer_origin -ne 'local_vlm_validated' -or -not $diagnosis.evidence -or -not $diagnosis.model) {
  throw 'The local VLM did not return a manual-grounded answer that passed LocalFix evidence validation.'
}

$locate = Invoke-RestMethod -Uri "$ApiBaseUrl/vision/locate" -Method Post -ContentType 'application/json' `
  -Body (@{ image_base64 = $imageBase64; target = $ComponentTarget } | ConvertTo-Json -Compress) -TimeoutSec 240

$benchmark = $null
if ($RunBenchmark) {
  $benchmark = Invoke-RestMethod -Uri "$ApiBaseUrl/benchmark/run" -Method Post -ContentType 'application/json' `
    -Body (@{
      stages = @('ocr', 'retrieval', 'reasoning')
      repeats = 10
      image_base64 = $imageBase64
    } | ConvertTo-Json -Depth 5 -Compress) -TimeoutSec 1800
}

$device = Get-CimInstance Win32_ComputerSystem
$processor = Get-CimInstance Win32_Processor | Select-Object -First 1
$report = [ordered]@{
  schema_version = 1
  captured_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
  device = [ordered]@{
    manufacturer = $device.Manufacturer
    model = $device.Model
    processor = $processor.Name
    os_architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
  }
  api_base_url = $ApiBaseUrl
  offline_required = [bool]$RequireOffline
  image = [ordered]@{ sha256 = $imageHash; mime_type = $mimeType; bytes = $imageBytes.Length }
  health = $health
  runtime = $runtime
  ocr = $ocr
  diagnosis = $diagnosis
  component_location = $locate
  benchmark = $benchmark
  npu_verification = [ordered]@{
    status = if ($runtime.npu -eq 'active') { 'active_provider_reported' } else { 'unverified' }
    detail = if ($runtime.npu -eq 'active') { 'LocalFix reports an active QNNExecutionProvider.' } else { 'GenieX HTTP status does not expose provider placement; retain GenieX/QAIRT diagnostics and do not claim NPU placement from API success alone.' }
  }
}

$outputDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) 'benchmark\snapdragon-runs'
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$outputPath = Join-Path $outputDirectory ("snapdragon-smoke-{0}.json" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
$report | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $outputPath -Encoding utf8

Write-Host "Live OCR completed: $($ocr.values.Count) normalized values"
Write-Host "Grounded local VLM answer passed: $($diagnosis.model)"
Write-Host "Component location: found=$($locate.found); backend=$($locate.backend)"
Write-Host "Network: $($runtime.network); NPU: $($report.npu_verification.status)"
Write-Host "Verification report: $outputPath"
