import type { Evidence, ProcedureStep, RuntimeStatus, ServiceCase } from '../types'

export const demoRuntime: RuntimeStatus = {
  mode: 'demo', simulated: true, backend: 'Demo simulation', npu: 'unknown', network: 'offline',
  models: { vision: 'unavailable', ocr: 'unavailable', speech: 'unavailable', reasoning: 'unavailable' },
  latencyMs: {}, ramMb: null,
}

export const demoEvidence: Evidence[] = [
  { id: 'ev-e07', document: 'DemoTech ACM-4200 Service Manual 2026', page: 84, section: '4.2 · Fault code E07', title: 'E07 — motor control feedback', excerpt: 'E07 is recorded when the motor feedback circuit does not return the expected state during a start request. Begin with the external connector and relay indicator checks listed in the service sequence.', relevance: 0.87, sourceType: 'manual' },
  { id: 'ev-table', document: 'DemoTech ACM-4200 Service Manual 2026', page: 102, section: 'Appendix B · Fault table', title: 'Fault code reference', excerpt: 'E07 — Motor control feedback mismatch. Record the event and verify the unit identity before service.', relevance: 0.81, sourceType: 'manual' },
  { id: 'ev-diagram', document: 'DemoTech ACM-4200 Service Manual 2026', page: 37, section: '2.6 · Control bay layout', title: 'Control bay component map', excerpt: 'The motor relay (K2) is located to the right of the control board. The main connector is below the relay; the service fuse is above the board.', relevance: 0.74, sourceType: 'manual' },
]

export const demoSteps: ProcedureStep[] = [
  { id: 's1', title: 'Verify safe equipment state', action: 'Confirm the machine is stopped and isolated using the site-approved isolation procedure.', reason: 'The manual requires safe isolation before opening the control bay.', level: 'restricted', source: 'Service Manual 2026 · Safety 1.3', page: 8, status: 'current' },
  { id: 's2', title: 'Inspect motor-control relay', action: 'With the approved safe state confirmed, visually inspect relay K2 and its indicator for visible damage or an abnormal state.', reason: 'E07 is associated with the motor feedback circuit; K2 is the first visual check in the cited sequence.', level: 'caution', source: 'Service Manual 2026 · Section 4.2', page: 84, status: 'waiting' },
  { id: 's3', title: 'Inspect the main connector', action: 'Check the external connector seating and record any visible condition. Do not disconnect unless the site procedure authorizes it.', reason: 'The fault table lists the connector check before internal replacement actions.', level: 'caution', source: 'Service Manual 2026 · Section 4.2', page: 84, status: 'waiting' },
  { id: 's4', title: 'Record observation', action: 'Add the observed indicator state and connector condition to the case notes.', reason: 'A traceable observation supports the next service decision.', level: 'routine', source: 'Service Manual 2026 · Checklist 8.1', page: 116, status: 'waiting' },
]

export const demoCases: ServiceCase[] = [
  { id: '1042', equipment: 'ACM-4200', serialNumber: 'SN-823919', fault: 'E07', diagnosis: 'Motor control feedback mismatch', status: 'Resolved', technician: 'LocalFix Demo User', duration: '18 min', evidenceCount: 3, timestamp: '12 min ago', notes: 'K2 indicator observed in the expected state after approved connector inspection. Test cycle passed.', simulated: true },
  { id: '1041', equipment: 'ACM-4200', serialNumber: 'SN-823918', fault: 'E03', diagnosis: 'Cooling airflow alert', status: 'Resolved', technician: 'LocalFix Demo User', duration: '24 min', evidenceCount: 2, timestamp: 'Yesterday', notes: 'Air path cleared per maintenance checklist.', simulated: true },
]

export const manualPages: Record<number, string> = {
  8: '1.3 Safe service state\nBefore opening the control bay, stop the machine and follow the site-approved isolation and verification procedure. The procedures in this demonstration are fictional training material and do not replace site-specific instructions. Do not bypass protective devices.',
  37: '2.6 Control bay layout\nThe control board (A1) occupies the central mounting plate. Motor relay K2 is positioned to the right of A1. Main connector J4 is below K2. The service fuse F1 is above A1. Component positions are shown for orientation only.',
  84: '4.2 Fault code E07 — motor control feedback\nCondition: The motor feedback circuit did not return the expected state during a start request.\n\nSupported initial checks:\n1. Confirm the equipment identity and record the displayed code.\n2. Verify safe state according to Section 1.3.\n3. Observe the motor relay K2 indicator and record its visible state.\n4. Inspect the external connector seating for visible condition.\n5. Record observations and consult the site-approved service process if the code remains.\n\nThis fictional procedure does not authorize energized testing, component removal, or bypassing safeguards.',
  102: 'Appendix B — Fault code reference\nE07 | Motor control feedback mismatch | Record the event; verify equipment identity; follow Section 4.2.\nE03 | Cooling airflow alert | Inspect the external airflow path per Section 5.1.\nE11 | Sensor communication | Record the code and refer to qualified service personnel.',
  116: '8.1 Service checklist\nRecord model, serial number, displayed code, observed indicators, external connector condition, action taken, and final result. Attach photographs only when site policy allows. Preserve source references in the service record.',
}
