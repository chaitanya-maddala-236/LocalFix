import { createContext, useContext, useEffect, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react'
import { demoCases, demoEvidence, demoRuntime } from '../data/demo'
import type { Evidence, RuntimeStatus, ServiceCase } from '../types'

type LocalFixState = {
  demoMode: boolean; setDemoMode: (value: boolean) => void
  runtime: RuntimeStatus; setRuntime: (value: RuntimeStatus) => void
  evidence: Evidence[]; setEvidence: Dispatch<SetStateAction<Evidence[]>>
  cases: ServiceCase[]; setCases: Dispatch<SetStateAction<ServiceCase[]>>; addCase: (entry: ServiceCase) => void
  diagnosis: string; setDiagnosis: (value: string) => void
  safetyAcknowledged: boolean; setSafetyAcknowledged: (value: boolean) => void
  componentShown: boolean; setComponentShown: (value: boolean) => void
}

const LocalFixContext = createContext<LocalFixState | null>(null)

export function LocalFixProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(true)
  const [runtime, setRuntime] = useState<RuntimeStatus>(() => ({ ...demoRuntime, network: typeof navigator === 'undefined' ? 'unknown' : navigator.onLine ? 'online' : 'offline' }))
  const [evidence, setEvidence] = useState(demoEvidence)
  const [cases, setCases] = useState(demoCases)
  const [diagnosis, setDiagnosis] = useState('Motor control feedback mismatch')
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false)
  const [componentShown, setComponentShown] = useState(false)
  useEffect(() => {
    const updateNetwork = () => setRuntime(value => ({ ...value, network: navigator.onLine ? 'online' : 'offline' }))
    window.addEventListener('online', updateNetwork); window.addEventListener('offline', updateNetwork)
    return () => { window.removeEventListener('online', updateNetwork); window.removeEventListener('offline', updateNetwork) }
  }, [])
  const state = useMemo(() => ({ demoMode, setDemoMode, runtime, setRuntime, evidence, setEvidence, cases, setCases,
    addCase: (entry: ServiceCase) => setCases(current => [entry, ...current]), diagnosis, setDiagnosis,
    safetyAcknowledged, setSafetyAcknowledged, componentShown, setComponentShown }),
  [demoMode, runtime, evidence, cases, diagnosis, safetyAcknowledged, componentShown])
  return <LocalFixContext.Provider value={state}>{children}</LocalFixContext.Provider>
}

export function useLocalFix() {
  const value = useContext(LocalFixContext)
  if (!value) throw new Error('useLocalFix must be used inside LocalFixProvider')
  return value
}
