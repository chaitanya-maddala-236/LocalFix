import type { RuntimeStatus } from '../types'
import type { ServiceCase } from '../types'

export async function getRuntime(): Promise<RuntimeStatus> {
  const response = await fetch('/api/runtime/status', { signal: AbortSignal.timeout(1800) })
  if (!response.ok) throw new Error(`Runtime service returned ${response.status}`)
  return response.json() as Promise<RuntimeStatus>
}

export async function checkHealth(): Promise<boolean> {
  try { return (await fetch('/api/health', { signal: AbortSignal.timeout(1200) })).ok } catch { return false }
}

export async function getCases(): Promise<ServiceCase[]> {
  const response = await fetch('/api/cases', { signal: AbortSignal.timeout(1800) })
  if (!response.ok) throw new Error(`Cases service returned ${response.status}`)
  const payload = await response.json() as { items: Array<Record<string, unknown>> }
  return payload.items.map(item => ({
    id: String(item.case_id), equipment: String(item.equipment_model ?? 'Unknown equipment'),
    fault: String(item.fault_code ?? '—'), diagnosis: String(item.diagnosis ?? 'Unspecified'),
    status: item.status === 'Resolved' ? 'Resolved' : 'In progress', technician: String(item.technician ?? 'Local technician'),
    duration: '—', evidenceCount: Array.isArray(item.evidence) ? item.evidence.length : 0,
    timestamp: String(item.updated_at ?? 'Just now'), timestampIso: String(item.updated_at ?? ''), serialNumber: typeof item.serial_number === 'string' ? item.serial_number : null,
    notes: String(item.notes ?? ''), simulated: Boolean(item.simulated),
  }))
}
