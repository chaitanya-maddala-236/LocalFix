import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Bookmark, Check, ChevronDown, Copy, FileText, Highlighter, Info, Minus, Plus, Search, ShieldCheck, Sparkles, Upload, X } from 'lucide-react'
import { motion } from 'motion/react'
import { Badge, Button, Card, PageHeading } from '../components/ui'
import { demoEvidence, manualPages } from '../data/demo'
import { useLocalFix } from '../state/LocalFixContext'
import type { Evidence } from '../types'

type ManualEntry = { document_id: string; document_name: string; equipment_model: string | null; page_count: number }

export default function EvidencePage() {
  const { demoMode, evidence } = useLocalFix()
  const available = demoMode ? demoEvidence : evidence
  const [selectedId, setSelectedId] = useState(demoEvidence[0].id)
  const selected: Evidence | undefined = available.find(item => item.id === selectedId) ?? available[0]
  const [zoom, setZoom] = useState(100)
  const [copied, setCopied] = useState(false)
  const [query, setQuery] = useState('E07 motor feedback')
  const [highlight, setHighlight] = useState(true)
  const [livePage, setLivePage] = useState('')
  const [manuals, setManuals] = useState<ManualEntry[]>([])
  const [uploadState, setUploadState] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (demoMode || !selected?.documentId) { setLivePage(''); return }
    const controller = new AbortController()
    void fetch(`/api/manuals/${encodeURIComponent(selected.documentId)}/pages/${selected.page}`, { signal: controller.signal })
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Source page unavailable.')))
      .then(result => setLivePage(String(result.text ?? '')))
      .catch(error => { if (!controller.signal.aborted) setLivePage(error instanceof Error ? error.message : '') })
    return () => controller.abort()
  }, [demoMode, selected?.documentId, selected?.page])

  useEffect(() => {
    if (demoMode) { setManuals([]); return }
    void fetch('/api/manuals', { signal: AbortSignal.timeout(1800) }).then(response => response.ok ? response.json() : []).then(result => setManuals(result as ManualEntry[])).catch(() => setManuals([]))
  }, [demoMode, uploadState])

  const pageText = selected ? demoMode
    ? manualPages[selected.page] ?? `${selected.document}\n\nPage ${selected.page}\n\nThis selected passage is a fictional LocalFix demo source.`
    : livePage || selected.excerpt : ''
  const segments = useMemo(() => {
    const pieces = pageText.split(/(E07|motor feedback|motor relay K2|connector|safe state|isolation)/gi)
    return pieces.map((part, index) => /^(E07|motor feedback|motor relay K2|connector|safe state|isolation)$/i.test(part) ? <mark key={index}>{part}</mark> : <span key={index}>{part}</span>)
  }, [pageText])

  async function copyCitation() {
    if (!selected) return
    const citation = `${selected.document}, ${selected.section}, p. ${selected.page}`
    try { await navigator.clipboard.writeText(citation); setCopied(true); window.setTimeout(() => setCopied(false), 1800) }
    catch { setCopied(false) }
  }

  async function uploadManual(file?: File) {
    if (!file) return
    if (demoMode) { setUploadState('Switch to Local Runtime to ingest a PDF into the local backend. Demo mode does not write to device storage.'); return }
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) { setUploadState('Choose a PDF manual.'); return }
    const form = new FormData(); form.append('file', file)
    setUploadState(`Ingesting ${file.name} locally…`)
    try {
      const response = await fetch('/api/manuals/ingest', { method: 'POST', body: form, signal: AbortSignal.timeout(120000) })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail?.message ?? 'Manual ingestion failed.')
      const note = result.warnings?.length ? ` · ${result.warnings.join(' ')}` : ''
      setUploadState(`${result.document_name}: indexed ${result.indexed_pages}/${result.pages} pages into ${result.chunks} chunks.${note}`)
    } catch (error) { setUploadState(error instanceof Error ? error.message : 'Manual ingestion failed.') }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault(); setDragging(false)
    void uploadManual(event.dataTransfer.files[0])
  }

  const evidenceIndex = selected ? available.findIndex(item => item.id === selected.id) : -1
  return <div className="evidence-page">
    <PageHeading eyebrow="TRACEABILITY · SOURCE REVIEW" title="Evidence inspector" subtitle="See the manual passage behind the finding, with source page and retrieval context preserved." action={<div className="evidence-heading-actions"><Link to="/diagnose" className="button button-secondary"><ArrowLeft size={14}/> Back to diagnosis</Link><button className="button button-primary" onClick={() => fileRef.current?.click()}><Upload size={14}/> Add manual</button><input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden onChange={event => { void uploadManual(event.target.files?.[0]); event.target.value = '' }}/></div>}/>
    <div className={`manual-upload-strip ${dragging ? 'drag-active' : ''}`} onDragOver={event => { event.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
      <div className="upload-strip-icon"><Upload size={15}/></div><div><b>{demoMode ? 'Local manual ingestion' : 'Drop a PDF manual here'}</b><small>{demoMode ? 'Switch to Local Runtime to save and index a manual on this device.' : 'PDF only · up to 50 MB · text and original page numbers are retained'}</small></div>{!demoMode && <Badge tone="lime">ON DEVICE</Badge>}{uploadState && <button className="upload-dismiss" aria-label="Dismiss upload message" onClick={() => setUploadState('')}><X size={13}/></button>}
    </div>
    {uploadState && <div className="upload-status"><Info size={13}/><span>{uploadState}</span></div>}
    {!demoMode && manuals.length > 0 && <div className="manual-library-row"><span><BookIcon/> {manuals.length} local {manuals.length === 1 ? 'manual' : 'manuals'}</span>{manuals.map(manual => <Badge tone="neutral" key={manual.document_id}>{manual.document_name} · {manual.page_count} pages</Badge>)}</div>}
    {!selected ? <Card className="no-live-evidence"><div className="empty-evidence-icon"><Search size={20}/></div><h2>No evidence loaded yet</h2><p>Ask a question in Live Diagnose to search the local manuals. Results will appear here with their original source page and section.</p><Link to="/diagnose" className="button button-secondary">Go to diagnosis <ArrowRight size={14}/></Link></Card> : <>
      <div className="evidence-toolbar"><div className="document-ident"><div className="pdf-icon"><FileText size={18}/></div><div><b>{selected.document}</b><small>{demoMode ? 'FICTIONAL DEMO SOURCE' : 'LOCAL SOURCE DOCUMENT'} <span/> PAGE {selected.page} <span/> {selected.sourceHash ? `HASH ${selected.sourceHash.slice(0, 8)}` : 'SOURCE PAGE PRESERVED'}</small></div><Badge tone={demoMode ? 'amber' : 'lime'}>{demoMode ? 'DEMO SOURCE' : 'LOCAL SOURCE'}</Badge></div><div className="document-controls"><button aria-label="Search document" onClick={() => setQuery('E07 motor feedback')}><Search size={15}/></button><button onClick={() => setZoom(value => Math.max(80, value - 10))} aria-label="Zoom out"><Minus size={15}/></button><span>{zoom}%</span><button onClick={() => setZoom(value => Math.min(130, value + 10))} aria-label="Zoom in"><Plus size={15}/></button><span className="toolbar-divider"/><button onClick={() => setHighlight(value => !value)} className={highlight ? 'control-selected' : ''}><Highlighter size={14}/><span>Highlights</span></button></div></div>
      <div className="evidence-layout">
        <Card className="manual-card"><div className="manual-viewer-bar"><span><span className="viewer-dot"/> {demoMode ? 'FICTIONAL MANUAL PREVIEW' : 'EXTRACTED SOURCE PAGE'}</span><span>PAGE <b>{selected.page}</b>{demoMode && <> <span className="viewer-slash">/</span> 126</>}</span></div><div className="manual-page-scroller"><motion.article className="manual-page" key={`${selected.id}-${pageText.length}`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .2 }} style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center' }}><div className="manual-page-brand"><span className="manual-brand-mark">◈</span><div><b>{demoMode ? <>DEMO<span>TECH</span></> : <>{selected.document.split(' ').slice(0, 1)}<span> MANUAL</span></>}</b><small>FIELD SERVICE DOCUMENT</small></div><span className="manual-watermark">{demoMode ? 'DEMO COPY' : 'LOCAL SOURCE'}</span></div><div className="manual-running-head">{demoMode ? 'ACM-4200 MOTOR CONTROLLER' : selected.document.toUpperCase()} <span>FIELD SERVICE</span></div><div className="manual-page-rule"/><div className="manual-page-section"><span>SECTION {selected.section.split('·')[0].trim()}</span><span>PAGE {String(selected.page).padStart(3, '0')}</span></div><h2>{selected.title}</h2><div className={`manual-body ${highlight ? 'manual-highlighted' : ''}`}>{segments}</div>{demoMode && <div className="manual-callout"><Info size={15}/><div><b>DEMONSTRATION DOCUMENT</b><p>Fictional training content for LocalFix. Follow applicable site procedures and qualified service instructions.</p></div></div>}<div className="manual-page-footer"><span>{demoMode ? 'DEMO TECHNICAL PUBLICATION · REV 2026.1' : 'LOCAL DOCUMENT · PAGE TEXT EXTRACTED ON DEVICE'}</span><span>{String(selected.page).padStart(3, '0')}</span></div></motion.article></div><div className="manual-pager"><button aria-label="Previous evidence page" disabled={evidenceIndex <= 0} onClick={() => setSelectedId(available[Math.max(0, evidenceIndex - 1)].id)}><ArrowLeft size={14}/></button><div>{available.map(item => <button key={item.id} className={`page-dot ${item.id === selected.id ? 'current' : ''}`} aria-label={`Open page ${item.page}`} onClick={() => setSelectedId(item.id)} />)}</div><span>Evidence pages <b>{evidenceIndex + 1}</b> / {available.length}</span><button aria-label="Next evidence page" disabled={evidenceIndex >= available.length - 1} onClick={() => setSelectedId(available[Math.min(available.length - 1, evidenceIndex + 1)].id)}><ArrowRight size={14}/></button></div></Card>
        <aside className="evidence-inspector"><Card className="why-card"><div className="why-header"><div><div className="eyebrow">WHY THIS ANSWER?</div><h2>Evidence chain</h2></div><span className="why-spark"><Sparkles size={16}/></span></div><div className="why-query"><span>TECHNICIAN QUESTION</span><p>“{query}”</p><button onClick={() => setQuery('What should I check for E07?')}>Edit query <ChevronDown size={12}/></button></div><div className="evidence-chain"><div className="chain-item"><span className="chain-icon observation"><Highlighter size={14}/></span><div><small>{demoMode ? 'OBSERVATION' : 'QUESTION CONTEXT'}</small><b>{demoMode ? 'E07 detected' : 'Question submitted'}</b><span>{demoMode ? 'Control display · demo OCR' : 'No camera OCR observation attached'}</span></div>{demoMode && <Check size={13}/>}</div><div className="chain-connector"/><div className="chain-item"><span className="chain-icon identity"><ShieldCheck size={14}/></span><div><small>IDENTITY</small><b>{demoMode ? 'ACM-4200' : selected.equipmentModel ?? 'Equipment not verified'}</b><span>{demoMode ? 'Model label · simulated OCR' : 'Source metadata / technician context'}</span></div>{demoMode && <Check size={13}/>}</div><div className="chain-connector"/><div className="chain-item"><span className="chain-icon retrieval"><Search size={14}/></span><div><small>RETRIEVAL</small><b>{selected.section}</b><span>{demoMode ? 'SQLite FTS · demo context' : 'SQLite FTS5 · local retrieval'}</span></div><Check size={13}/></div><div className="chain-connector"/><div className="chain-item chain-source"><span className="chain-icon source"><BookMarkIcon/></span><div><small>SOURCE</small><b>{selected.document}</b><span>Page {selected.page} · source hash preserved</span></div><Check size={13}/></div><div className="chain-connector"/><div className="chain-item"><span className="chain-icon reasoning"><Sparkles size={14}/></span><div><small>SUPPORTED FINDING</small><b>{demoMode ? 'Motor-control feedback' : selected.section}</b><span>{demoMode ? 'Claim linked to cited fault table' : 'Retrieved passage; review source text'}</span></div>{demoMode && <Check size={13}/>}</div></div><div className="evidence-score-row"><span><span className="score-dot"/> {demoMode ? 'Evidence strength' : 'FTS5 relevance score'}</span><b>{demoMode ? <>0.87 <small>demo relevance</small></> : selected.relevance.toFixed(5)}</b></div><div className="why-note"><ShieldCheck size={14}/><span>Relevance is a retrieval score, not a calibrated probability. The finding is limited to the evidence shown.</span></div></Card>
          <Card className="source-card"><div className="source-card-head"><div><div className="eyebrow">SELECTED PASSAGE</div><h3>{selected.title}</h3></div><Badge tone="blue">MANUAL</Badge></div><p>{selected.excerpt}</p><div className="source-card-meta"><span>SECTION <b>{selected.section}</b></span><span>PAGE <b>{selected.page}</b></span><span>{demoMode ? 'DEMO SCORE' : 'FTS SCORE'} <b>{selected.relevance.toFixed(demoMode ? 2 : 5)}</b></span></div><div className="source-actions"><Button variant="secondary" onClick={copyCitation}>{copied ? <Check size={14}/> : <Copy size={14}/>} {copied ? 'Copied' : 'Copy citation'}</Button><Button variant="primary" onClick={() => document.querySelector('.manual-page')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}>Open source <ArrowRight size={14}/></Button></div></Card><div className="evidence-footer-note"><ShieldCheck size={13}/><span>Original source page numbers remain attached to every retrieved chunk.</span></div></aside>
      </div></>}
  </div>
}

function BookIcon() { return <Bookmark size={13}/> }
function BookMarkIcon() { return <Bookmark size={14}/> }
