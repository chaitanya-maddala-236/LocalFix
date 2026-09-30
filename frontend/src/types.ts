export type RuntimeStatus = {
  mode: 'demo' | 'local'
  simulated: boolean
  backend: string
  npu: 'active' | 'unavailable' | 'unknown'
  network: 'offline' | 'online' | 'unknown'
  models: Record<string, 'ready' | 'missing' | 'unavailable'>
  model_details?: Record<string, { model?: string | null; backend?: string | null; state?: string; precision?: string | null; active_providers?: string[]; error?: string | null; tokens_per_second?: number | null; first_token_latency_ms?: number | null }>
  latencyMs: Partial<Record<'vision' | 'ocr' | 'speech' | 'retrieval' | 'reasoning', number | null>>
  ramMb: number | null
  ramScope?: string
  retrieval?: { mode: 'hybrid_rrf' | 'sqlite_fts5'; semantic: boolean; embedding_model?: string | null }
}

export type OCRObservation = {
  text: string; normalized: string; kind: 'model' | 'serial' | 'fault' | 'other'
  box: [number, number, number, number] | null; confidence: number | null
}

export type VisualDetection = {
  label: string; confidence: number; box: [number, number, number, number]
}

export type AssetIdentity = {
  model: string | null; serialNumber: string | null; faultCode: string | null
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
  observations?: string[]
}
