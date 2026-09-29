export type RuntimeStatus = {
  mode: 'demo' | 'local'
  simulated: boolean
  backend: string
  npu: 'active' | 'unavailable' | 'unknown'
  network: 'offline' | 'online' | 'unknown'
  models: Record<string, 'ready' | 'missing' | 'unavailable'>
  latencyMs: Partial<Record<'vision' | 'ocr' | 'speech' | 'retrieval' | 'reasoning', number | null>>
  ramMb: number | null
}

export type Evidence = {
  id: string; document: string; page: number; section: string; title: string; excerpt: string;
  relevance: number; sourceType: 'manual' | 'observation'; documentId?: string; equipmentModel?: string | null; sourceHash?: string
}

export type ProcedureStep = {
  id: string; title: string; action: string; reason: string; level: 'routine' | 'caution' | 'restricted';
  source: string; page: number; status: 'waiting' | 'current' | 'complete'
}

export type ServiceCase = {
  id: string; equipment: string; fault: string; diagnosis: string; status: 'Resolved' | 'In progress';
  technician: string; duration: string; evidenceCount: number; timestamp: string; notes: string; simulated?: boolean;
  serialNumber?: string | null; timestampIso?: string; runtimeMode?: string
}
