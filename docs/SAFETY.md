# Safety and evidence policy

LocalFix is a field-service prototype, not an authority over physical equipment.

## Evidence rules

- A supported finding must map to retrieved source text or an explicit observation.
- Each evidence object keeps document ID/name, original page, section, chunk, source hash, and retrieval score.
- Retrieval scores are ranking signals, not calibrated confidence.
- Unsupported questions return insufficient evidence. No VLM/LLM output is allowed to introduce a procedure without source validation.
- Synthetic OCR, detections, manual passages, and workflow metrics carry a demo/simulated marker.

## Safety gate

Candidate steps carry routine, caution, or restricted safety classes and a source page. The current ACM-4200 demo includes only fictional visual checks and an explicit safe-state confirmation step. Restricted steps require a human acknowledgement. LocalFix cannot verify that a machine is isolated, safe, de-energized, or suitable for service. The demo does not authorize energized tests, electrical measurements, component removal, connector disconnection, or bypassing safeguards.

If required evidence or the safety source is missing, the candidate procedure is blocked. A technician must follow the applicable current site procedure and qualified service instructions. Any report describes technician-recorded state, not an independent safety certification.

## Logging and privacy

Logs should contain operation, model, provider, elapsed time, outcome, and error class only. Do not log raw image/audio bytes or manual text. PDFs and SQLite stay beneath the project data directory. APIs bind to `127.0.0.1`; uploads are type/size/page checked and filenames sanitized. External inference is not configured.
