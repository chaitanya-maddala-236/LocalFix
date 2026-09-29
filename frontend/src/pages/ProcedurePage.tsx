import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlertOctagon, ArrowLeft, ArrowRight, Camera, Check, CheckCheck, ChevronRight, ClipboardCheck, CircleAlert, FileText, Info, LockKeyhole, Plus, Shield, ShieldCheck, Sparkles, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Badge, Button, Card, PageHeading } from '../components/ui'
import { demoSteps } from '../data/demo'
import { useLocalFix } from '../state/LocalFixContext'
import type { ServiceCase } from '../types'
import type { ProcedureStep as ProcedureStepType } from '../types'

export default function ProcedurePage() {
  const { demoMode, safetyAcknowledged, setSafetyAcknowledged, setComponentShown, addCase, cases, evidence, diagnosis } = useLocalFix()
  const [completed, setCompleted] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [saved, setSaved] = useState(false)
  const [resolved, setResolved] = useState(false)
  const [liveSteps, setLiveSteps] = useState<ProcedureStepType[]>([])
  const [liveNotice, setLiveNotice] = useState('')
  const [savedCaseId, setSavedCaseId] = useState('')
  const navigate = useNavigate()
  const steps = demoMode ? demoSteps : liveSteps
  const currentIndex = steps.findIndex(step => !completed.includes(step.id))

  useEffect(() => {
    setCompleted([]); setResolved(false); setLiveNotice('')
    setSafetyAcknowledged(false)
    if (demoMode) { setLiveSteps([]); return }
    if (!evidence.length) { setLiveSteps([]); setLiveNotice('Run a local retrieval from Live Diagnose to load a source-backed procedure.'); return }
    const controller = new AbortController()
    void fetch('/api/procedure', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipment_model: evidence[0].equipmentModel ?? 'DemoTech ACM-4200', diagnosis, evidence_ids: evidence.map(item => item.id) }), signal: controller.signal })
      .then(async response => { const result = await response.json(); if (!response.ok) throw new Error(result.detail?.message ?? 'Procedure service unavailable.'); return result })
      .then(result => {
        const mapped: ProcedureStepType[] = (result.steps ?? []).map((step: Record<string, unknown>) => ({
          id: `api_s${step.index}`, title: String(step.action).split(/[.!?]/)[0], action: String(step.action), reason: String(step.reason),
          level: step.safety_level as ProcedureStepType['level'], source: `${String(step.source_document)} · ${String(step.section)}`,
          page: Number(step.source_page), status: Number(step.index) === 1 ? 'current' : 'waiting',
        }))
        setLiveSteps(mapped); setLiveNotice(mapped.length ? String(result.safety_notice) : String(result.safety_notice ?? 'No source-backed procedure was returned.'))
      })
      .catch(error => { if (!controller.signal.aborted) { setLiveSteps([]); setLiveNotice(error instanceof Error ? error.message : 'No source-backed procedure available.') } })
    return () => controller.abort()
  }, [demoMode, evidence, diagnosis])

  function confirmSafety(stepId = 's1') {
    setSafetyAcknowledged(true)
    setCompleted(current => [...new Set([...current, stepId])])
  }
  function completeStep(stepId: string) {
    if (stepId === 's1' && !safetyAcknowledged) return
    setCompleted(current => [...new Set([...current, stepId])])
  }
  async function resolveCase() {
    if (!demoMode) {
      if (!steps.length) return
      setLiveNotice('Saving the case to local SQLite…')
      try {
        const faultCode = evidence.map(item => item.excerpt.match(/\bE\d{2}\b/i)?.[0]?.toUpperCase()).find(Boolean) ?? null
        const payload = { equipment_model: evidence[0]?.equipmentModel ?? 'Equipment model not verified', serial_number: null, fault_code: faultCode, diagnosis: diagnosis || 'Evidence review pending', status: 'Resolved', technician: 'Jordan Davis', notes: note || 'Technician-recorded observations.', resolution: 'Resolved', simulated: evidence.every(item => item.document.startsWith('DemoTech')), evidence: evidence.map(item => ({ id: item.id, document_id: item.documentId ?? '', document_name: item.document, page: item.page, section: item.section, equipment_model: item.equipmentModel ?? null, text: item.excerpt, retrieval_score: item.relevance, source_hash: item.sourceHash ?? '' })), steps: steps.map((step, index) => ({ index: index + 1, action: step.action, safety_level: step.level, completed: completed.includes(step.id), source_document_id: evidence[0]?.documentId ?? null, source_page: step.page })) }
        const response = await fetch('/api/cases', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal: AbortSignal.timeout(12000) })
        const result = await response.json(); if (!response.ok) throw new Error(result.detail?.message ?? 'Could not save the case locally.')
        const entry: ServiceCase = { id: String(result.case_id), equipment: String(result.equipment_model), fault: String(result.fault_code ?? '—'), diagnosis: String(result.diagnosis), status: 'Resolved', technician: String(result.technician), duration: '—', evidenceCount: Array.isArray(result.evidence) ? result.evidence.length : evidence.length, timestamp: 'Just now', notes: String(result.notes), simulated: Boolean(result.simulated) }
        addCase(entry); setSavedCaseId(entry.id); setResolved(true); setLiveNotice('Case saved to local SQLite.')
      } catch (error) { setLiveNotice(error instanceof Error ? error.message : 'Local case save failed.') }
      return
    }
    const entry: ServiceCase = {
      id: `${1043 + cases.length - 2}`, equipment: 'ACM-4200', fault: 'E07', diagnosis: 'Motor control feedback mismatch',
      status: 'Resolved', technician: 'Jordan Davis', duration: '18 min', evidenceCount: 3, timestamp: 'Just now',
      notes: note || 'Demo procedure completed with cited visual observations.', simulated: demoMode,
    }
    addCase(entry); setSavedCaseId(entry.id); setResolved(true)
  }

  return <div className="procedure-page">
    <PageHeading eyebrow="GUIDED TROUBLESHOOTING · CASE #1042" title="Work the evidence." subtitle="Every step carries a source reference. Restricted steps stay locked until you confirm the required safe state." action={<Link to="/diagnose" className="button button-secondary"><ArrowLeft size={14}/> Diagnosis</Link>}/>
    <div className="procedure-banner"><div className="procedure-banner-icon"><Shield size={17}/></div><div><b>{demoMode ? 'Fictional training procedure' : 'Source-backed local procedure'}</b><span>{demoMode ? 'ACM-4200 Service Manual 2026 · Section 4.2 · Page 84' : 'Steps are assembled from retrieved manual excerpts; no LLM procedure generation.'}</span></div><Badge tone={demoMode ? 'amber' : 'blue'}>{demoMode ? 'DEMO SIMULATION' : 'LOCAL SOURCE'}</Badge></div>
    {!demoMode && liveNotice && <div className="live-model-notice"><CircleAlert size={15}/><span>{liveNotice}</span></div>}
    <div className="procedure-layout"><section className="procedure-main"><div className="timeline-header"><div><span className="eyebrow">TROUBLESHOOTING SEQUENCE</span><h2>{demoMode ? 'E07 · Motor feedback' : diagnosis || 'Source-backed checks'}</h2></div><span className="step-count">{completed.length} <span>/</span> {steps.length} complete</span></div>
      <div className="procedure-timeline">{steps.map((step, index) => {
        const isComplete = completed.includes(step.id)
        const isCurrent = currentIndex === index
        const locked = step.level === 'restricted' && !safetyAcknowledged
        return <div className={`procedure-step ${isComplete ? 'step-complete' : ''} ${isCurrent ? 'step-current' : ''} ${locked ? 'step-locked' : ''}`} key={step.id}>
          <div className="step-spine"><div className="step-node">{isComplete ? <Check size={15}/> : locked ? <LockKeyhole size={13}/> : String(index + 1).padStart(2, '0')}</div>{index !== steps.length - 1 && <div className="step-connector"/>}</div>
          <Card className="step-card"><div className="step-card-head"><div><div className="step-meta"><span>STEP {String(index + 1).padStart(2, '0')}</span><span className={`risk-pill risk-${step.level}`}>{step.level === 'restricted' ? 'SAFETY REQUIRED' : step.level.toUpperCase()}</span>{isComplete && <Badge tone="lime">COMPLETE</Badge>}</div><h3>{step.title}</h3></div>{step.level === 'restricted' && <div className="step-lock-icon"><LockKeyhole size={15}/></div>}</div><p className="step-action">{step.action}</p><div className="step-reason"><Sparkles size={13}/><span>{step.reason}</span></div><div className="step-card-footer"><div className="step-source"><FileText size={13}/><span>{step.source}</span><b>p. {step.page}</b></div><div className="step-actions">{step.id.endsWith('2') && demoMode && <Button variant="secondary" size="small" onClick={() => { setComponentShown(true); navigate('/diagnose') }}><Camera size={13}/> Show me</Button>}{!isComplete && step.level === 'restricted' && <Button variant="primary" size="small" onClick={() => confirmSafety(step.id)} disabled={safetyAcknowledged}><ShieldCheck size={14}/>{safetyAcknowledged ? 'Confirmed' : 'Confirm safe state'}</Button>}{!isComplete && step.level !== 'restricted' && <Button variant={isCurrent ? 'primary' : 'secondary'} size="small" onClick={() => completeStep(step.id)} disabled={locked}>{step.id.endsWith('4') ? <Plus size={14}/> : <Check size={14}/>} {step.id.endsWith('4') ? 'Record note' : 'Mark complete'}</Button>}</div></div>{step.id.endsWith('1') && !safetyAcknowledged && <div className="safety-warning"><AlertOctagon size={15}/><span><b>Stop before proceeding.</b> Confirm the machine is stopped and isolated according to the applicable site-approved procedure. LocalFix cannot verify isolation.</span><button onClick={() => confirmSafety(step.id)}>I have confirmed <ArrowRight size={12}/></button></div>}</Card>
        </div>
      })}{!demoMode && steps.length === 0 && <Card className="no-live-evidence"><div className="empty-evidence-icon"><ClipboardCheck size={20}/></div><h2>No procedure generated</h2><p>Retrieve relevant manual evidence in Live Diagnose first. LocalFix will only build candidate steps from retrieved source text.</p><Button variant="secondary" onClick={() => navigate('/diagnose')}>Open diagnosis <ArrowRight size={14}/></Button></Card>}</div>
      <Card className="procedure-note-card"><div className="note-icon"><FileText size={16}/></div><div className="note-entry"><label htmlFor="tech-note">TECHNICIAN OBSERVATION</label><textarea id="tech-note" rows={3} value={note} onChange={event => setNote(event.target.value)} placeholder="Record what you observed. Keep it factual and concise…"/><div className="note-footer"><span>Stored with this local case</span><Button variant="secondary" size="small" onClick={() => setSaved(true)}>{saved ? <Check size={13}/> : <Plus size={13}/>} {saved ? 'Note saved' : 'Save note'}</Button></div></div></Card>
      <div className="procedure-complete-bar"><div><div className="complete-icon"><CheckCheck size={16}/></div><div><b>{completed.length === steps.length && steps.length > 0 ? 'All checks recorded' : 'Finish the case when ready'}</b><span>Service report includes the cited evidence and your observations.</span></div></div><Button variant="primary" onClick={resolveCase} disabled={!steps.length || resolved}>{resolved ? <Check size={14}/> : <ClipboardCheck size={14}/>} {resolved ? 'Case saved' : 'Complete & save case'} <ArrowRight size={14}/></Button></div>
      <AnimatePresence>{resolved && <motion.div className="resolution-toast" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><CheckCheck size={17}/><div><b>Case saved to local history</b><span>{savedCaseId} is ready for its service report.</span></div><Link to="/reports">Open report <ArrowRight size={13}/></Link><button onClick={() => setResolved(false)} aria-label="Dismiss"><X size={13}/></button></motion.div>}</AnimatePresence>
    </section>
    <aside className="procedure-side"><Card className="procedure-side-card"><div className="procedure-side-head"><div className="procedure-side-icon"><ShieldCheck size={16}/></div><div><div className="eyebrow">SAFETY GATE</div><h3>Technician in control</h3></div></div><p>LocalFix can show supported checks. It cannot verify equipment isolation or replace your site safety process.</p><div className={`safety-state ${safetyAcknowledged ? 'safety-state-done' : ''}`}><span className="safety-state-dot"/><div><b>{safetyAcknowledged ? 'Safe state confirmed' : 'Acknowledgement required'}</b><small>{safetyAcknowledged ? 'Confirmed by Jordan Davis for this procedure' : 'Required before continuing the sequence'}</small></div>{safetyAcknowledged && <Check size={14}/>}</div><div className="safety-side-foot"><LockKeyhole size={12}/> Confirmation is a technician action, never an AI inference.</div></Card>
      <Card className="procedure-side-card source-side-card"><div className="eyebrow">PROCEDURE SOURCE</div><h3>Service Manual 2026</h3><p>DemoTech ACM-4200 · Section 4.2</p><div className="source-page-preview"><span>PAGE</span><b>84</b><span>E07 — Motor feedback</span><div className="preview-lines"><i/><i/><i/><i/></div></div><Link to="/evidence" className="source-open-link">Open cited page <ChevronRight size={14}/></Link></Card>
      <div className="procedure-help"><Info size={14}/><span>For real equipment, follow current site procedures and qualified service guidance.</span></div></aside></div>
  </div>
}
