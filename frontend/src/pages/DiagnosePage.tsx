import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, ArrowRight, Camera, Check, ChevronDown, CircleAlert, ClipboardCheck, CloudOff, Focus, ImagePlus, Info, Mic, MoreHorizontal, ScanLine, Send, ShieldCheck, Sparkles, Square, Waves, X, ZoomIn } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Badge, Button, Card } from '../components/ui'
import { EquipmentArt } from '../components/EquipmentArt'
import { useLocalFix } from '../state/LocalFixContext'
import type { Evidence } from '../types'

type CameraState = 'idle' | 'scanning' | 'ready' | 'error'

export default function DiagnosePage() {
  const { demoMode, evidence, setEvidence, diagnosis, setDiagnosis, componentShown, setComponentShown, runtime } = useLocalFix()
  const [cameraState, setCameraState] = useState<CameraState>('idle')
  const [cameraOn, setCameraOn] = useState(false)
  const [videoError, setVideoError] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [question, setQuestion] = useState('')
  const [transcript, setTranscript] = useState('')
  const [listening, setListening] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [torch, setTorch] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [message, setMessage] = useState('')
  const [liveEvidence, setLiveEvidence] = useState<Evidence[]>([])
  const [liveDiagnosis, setLiveDiagnosis] = useState<string | null>(null)
  const [liveExplanation, setLiveExplanation] = useState('')
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => () => { streamRef.current?.getTracks().forEach(track => track.stop()) }, [])

  async function connectCamera() {
    setVideoError('')
    if (cameraOn) { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; setCameraOn(false); setCameraState('idle'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      streamRef.current = stream; setCameraOn(true); setCameraState('ready')
      if (videoRef.current) videoRef.current.srcObject = stream
    } catch { setVideoError('Camera unavailable or permission denied. You can continue with the clearly labeled demo scene.'); setCameraState('error') }
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) { setMessage('Choose a supported image file.'); return }
    if (imageUrl) URL.revokeObjectURL(imageUrl)
    setImageUrl(URL.createObjectURL(file)); setCameraOn(false); setCameraState('ready'); setMessage('Image loaded locally. In demo mode the displayed analysis is illustrative, not model inference.')
  }

  function startScan() {
    setComponentShown(false); setCameraState('scanning'); setProcessing(true)
    window.setTimeout(() => { setCameraState('ready'); setProcessing(false); setMessage(demoMode ? 'Demo scene analyzed. All detections and timings are simulated.' : 'Live model results are available only from installed local adapters.') }, 1200)
  }

  function runQuestion(event?: FormEvent) {
    event?.preventDefault()
    const query = question.trim() || transcript.trim()
    if (!query) { setMessage('Enter a question or use the demo voice prompt first.'); return }
    setProcessing(true); setMessage('')
    if (demoMode) {
      window.setTimeout(() => {
        const supported = /e07|motor|relay|connector|fault|acm-4200/i.test(query)
        setDiagnosis(supported ? 'Motor control feedback mismatch' : 'No supported answer for this question')
        setProcessing(false)
        setMessage('Simulated demo response grounded in the fictional ACM-4200 manual.')
      }, 760)
      return
    }
    void fetch('/api/diagnose', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: query }), signal: AbortSignal.timeout(12000) })
      .then(async response => { const result = await response.json(); if (!response.ok) throw new Error(result.detail?.message ?? 'Local diagnosis is unavailable.'); return result })
      .then(result => {
        const mapped: Evidence[] = (result.evidence ?? []).map((item: Record<string, unknown>) => ({ id: String(item.id), document: String(item.document_name), documentId: String(item.document_id), equipmentModel: typeof item.equipment_model === 'string' ? item.equipment_model : null, sourceHash: String(item.source_hash ?? ''), page: Number(item.page), section: String(item.section), title: String(item.section), excerpt: String(item.text), relevance: Number(item.retrieval_score ?? 0), sourceType: 'manual' }))
        setLiveEvidence(mapped); setEvidence(mapped); setLiveDiagnosis(result.status === 'supported_summary' ? String(result.finding) : null); setDiagnosis(result.status === 'supported_summary' ? String(result.finding) : ''); setLiveExplanation(String(result.explanation ?? ''))
        setMessage(result.status === 'supported_summary' ? 'Local rule summary validated against retrieved source text. No VLM response was generated.' : 'The local sources do not support a finding. No procedure was generated.')
      })
      .catch(error => { setLiveEvidence([]); setEvidence([]); setLiveDiagnosis(null); setDiagnosis(''); setLiveExplanation(''); setMessage(`${error instanceof Error ? error.message : 'Local service unavailable.'} No unsupported answer was shown.`) })
      .finally(() => setProcessing(false))
  }

  function useDemoVoice() {
    if (!demoMode) { setMessage('Local speech model unavailable. Add and configure an ASR model in the model registry to transcribe on device.'); return }
    if (listening) { setListening(false); setTranscript('Why is this machine showing E07?'); setQuestion('Why is this machine showing E07?'); return }
    setListening(true); setTranscript(''); window.setTimeout(() => { setListening(false); setTranscript('Why is this machine showing E07?'); setQuestion('Why is this machine showing E07?') }, 1450)
  }

  const shownEvidence = demoMode ? evidence : liveEvidence
  const shownDiagnosis = demoMode ? diagnosis : liveDiagnosis
  const noAnswer = !shownDiagnosis || shownDiagnosis === 'No supported answer for this question'
  return <div className="diagnose-page">
    <div className="diagnose-topline"><div><div className="eyebrow">FIELD SESSION <span className="eyebrow-separator">/</span> ACTIVE ASSET</div><h1>Live diagnosis <span className="live-pulse"/></h1></div><div className="diagnose-top-actions"><Badge tone={demoMode ? 'amber' : 'neutral'}>{demoMode ? 'DEMO · SIMULATED' : 'LOCAL RUNTIME'}</Badge><Button variant="secondary" size="small"><MoreHorizontal size={17}/></Button></div></div>
    <div className="diagnose-workspace">
      <section className="camera-column">
        <Card className="camera-card">
          <div className="camera-toolbar"><div className="camera-source"><span className="camera-source-icon"><Camera size={14}/></span><span><b>{cameraOn ? 'Device camera' : imageUrl ? 'Imported image' : 'ACM-4200 · Demo scene'}</b><small>{cameraOn ? 'LIVE FEED · LOCAL' : imageUrl ? 'LOCAL IMAGE' : 'SIMULATED CAMERA FEED'}</small></span><ChevronDown size={14}/></div><div className="camera-tools"><button onClick={connectCamera} aria-label={cameraOn ? 'Stop device camera' : 'Connect device camera'} className={cameraOn ? 'tool-active' : ''}><Camera size={15}/><span>{cameraOn ? 'Stop' : 'Camera'}</span></button><button onClick={startScan} disabled={processing}><ScanLine size={15}/><span>Scan</span></button><button onClick={() => setTorch(value => !value)} className={torch ? 'tool-active' : ''} aria-label="Toggle torch simulation"><Sparkles size={15}/><span>Torch</span></button><button onClick={() => setZoom(value => value >= 1.4 ? 1 : value + .2)} aria-label="Zoom camera"><ZoomIn size={15}/><span>{zoom.toFixed(1)}×</span></button><button onClick={() => fileRef.current?.click()} aria-label="Import image"><ImagePlus size={15}/></button><input ref={fileRef} type="file" accept="image/*" onChange={onFile} hidden/></div></div>
          <div className={`camera-stage ${cameraState === 'scanning' ? 'is-scanning' : ''} ${torch ? 'torch-on' : ''}`}>
            {cameraOn ? <video ref={videoRef} autoPlay playsInline muted className="camera-video"/> : imageUrl ? <img src={imageUrl} className="camera-upload" alt="Technician selected equipment"/> : <EquipmentArt/>}
            {!cameraOn && !imageUrl && <div className="scene-grid"/>}
            <div className="camera-vignette"/>
            {cameraState === 'scanning' && <motion.div className="scan-sweep" initial={{ top: '8%' }} animate={{ top: '90%' }} transition={{ duration: 1.15, ease: 'linear' }}/>} 
            <div className="camera-hud-top"><span className="hud-chip"><span className="hud-dot"/> {cameraState === 'scanning' ? 'SCANNING EQUIPMENT' : cameraOn ? 'CAMERA ACTIVE' : 'FIELD VIEW'}</span><span className="hud-chip hud-time">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} <span className="hud-divider"/> LOCAL</span></div>
            <div className="camera-hud-bottom"><span><Focus size={13}/> FRAME 01</span><span>16:10 <span className="hud-divider"/> 1280 × 800</span></div>
            {demoMode && <motion.div className={`detected-model ${componentShown ? 'model-targeted' : ''}`} animate={{ scale: componentShown ? 1.04 : 1 }}><span className="box-corner corner-tl"/><span className="box-corner corner-tr"/><span className="box-corner corner-bl"/><span className="box-corner corner-br"/><span className="detection-eyebrow">IDENTIFIED MODEL</span><b>ACM-4200</b><small>MODEL LABEL · SIMULATED</small></motion.div>}
            {demoMode && <div className="detected-fault"><span className="fault-marker">E07</span><span><small>DISPLAY OCR · DEMO</small><b>Motor fault</b></span></div>}
            <AnimatePresence>{componentShown && demoMode && <motion.div className="relay-target" initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}><span className="relay-target-corners"/><span className="relay-target-label"><span className="target-dot"/> MOTOR RELAY K2 <small>DEMO LOCALIZATION</small></span></motion.div>}</AnimatePresence>
            {!demoMode && <div className="camera-error camera-no-model"><CircleAlert size={15}/><span>NO LIVE DETECTIONS <small>{runtime.models.vision === 'ready' ? 'MODEL-SPECIFIC CAMERA PIPELINE NOT CONFIGURED' : 'VISION MODEL NOT INSTALLED'}</small></span></div>}
            {cameraState === 'idle' && <div className="camera-empty-hint"><div><ScanLine size={17}/><span>Scene ready for inspection</span><small>Scan or connect your camera to begin</small></div></div>}
            {cameraState === 'error' && <div className="camera-error"><CircleAlert size={16}/>{videoError}</div>}
            {torch && <div className="torch-overlay"/>}
          </div>
          <div className="camera-statusbar"><div className="camera-state-label"><span className={`state-led ${cameraState === 'ready' ? 'led-ready' : cameraState === 'scanning' ? 'led-scanning' : ''}`}/><span>{cameraState === 'scanning' ? 'ANALYZING FRAME' : cameraState === 'ready' ? 'READY' : cameraState === 'error' ? 'CAMERA ERROR' : 'STANDBY'}</span><span className="statusbar-divider"/><span className="source-local"><CloudOff size={12}/> LOCAL PROCESSING</span></div><button className="freeze-button" onClick={() => setMessage('Frame frozen for review.')}><Square size={12}/> Freeze frame</button></div>
        </Card>
        <div className="voice-composer card"><div className={`voice-button ${listening ? 'voice-listening' : ''}`}><button onClick={useDemoVoice} aria-label={listening ? 'Stop recording' : 'Hold to speak'}>{listening ? <Waves size={19}/> : <Mic size={18}/>}</button><span className="voice-ring"/></div><div className="voice-main"><div className="voice-label">{listening ? 'LISTENING…' : transcript ? 'VOICE TRANSCRIPT' : 'ASK LOCALFIX'}</div>{transcript ? <div className="transcript-text">“{transcript}” <Badge tone="amber">{demoMode ? 'SIMULATED VOICE' : 'TRANSCRIPT'}</Badge></div> : <input aria-label="Ask LocalFix a question" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') runQuestion() }} placeholder={listening ? 'Listening for your question…' : 'Ask about the equipment, fault, or next step…'}/>}<small>{demoMode ? 'Demo transcript uses a sample phrase. No microphone audio is captured.' : 'Audio stays on device; transcription requires an installed local speech model.'}</small></div><Button variant="primary" className="ask-button" disabled={processing || listening} onClick={() => runQuestion()}>{processing ? <span className="mini-spinner"/> : <Send size={15}/>}<span>{processing ? 'Working' : 'Ask'}</span></Button><button className="voice-more" aria-label="Voice options"><MoreHorizontal size={17}/></button></div>
        {message && <div className="diagnose-notice"><Info size={14}/><span>{message}</span><button onClick={() => setMessage('')} aria-label="Dismiss"><X size={13}/></button></div>}
      </section>

      <aside className="intelligence-column">
        <Card className="intelligence-card">
          <div className="intel-header"><div><span className="intel-overline"><span className="intel-orb"><Sparkles size={12}/></span> LOCALFIX INTELLIGENCE</span><h2>AI diagnosis</h2></div><Badge tone={demoMode ? 'amber' : 'neutral'}>{demoMode ? 'SIMULATED' : 'LOCAL · NO VLM'}</Badge></div>
          <div className="intel-equipment"><div className="intel-equipment-icon"><Activity size={17}/></div><div><b>{demoMode ? 'DemoTech ACM-4200' : 'Equipment not verified'}</b><small>{demoMode ? 'Industrial motor controller · demo asset' : 'No live model-label OCR available'}</small></div><button aria-label="Equipment details"><MoreHorizontal size={16}/></button></div>
          <div className="intel-observation"><div className="intel-observation-label"><span>{demoMode ? 'OBSERVED CONDITION · DEMO' : 'OBSERVATIONS'}</span>{demoMode && <Badge tone="red">E07</Badge>}</div><div className="intel-code-line"><span className="code-glyph">{demoMode ? '!' : '—'}</span><div><b>{demoMode ? 'Motor feedback mismatch' : 'No local OCR observation'}</b><small>{demoMode ? 'Sample display text · OCR simulated' : 'OCR model or preprocessing unavailable'}</small></div></div>{demoMode && <div className="intel-tags"><span><Check size={12}/> ACM-4200 · demo</span><span><Check size={12}/> E07 · demo</span><span><ShieldCheck size={12}/> Source matched</span></div>}</div>
          <div className="diagnosis-block"><div className="diagnosis-block-head"><span>{noAnswer ? 'NO SUPPORTED FINDING' : 'SUPPORTED FINDING'}</span>{!noAnswer && <span className="evidence-strength"><span/> SOURCE-ALIGNED</span>}</div><h3>{noAnswer ? 'No reliable evidence' : shownDiagnosis}</h3><p>{noAnswer ? demoMode ? 'The local manual does not contain enough support for this question. Try asking about E07, the relay, or connector checks.' : 'Ask a question to retrieve local manual passages. Equipment identity and live OCR are not verified.' : demoMode ? 'The service manual links E07 to motor feedback. Begin with the cited visual checks after confirming the safe state.' : liveExplanation}</p><div className="source-coverage"><div className="coverage-label"><span>Retrieved sources</span><b>{shownEvidence.length} {shownEvidence.length === 1 ? 'source' : 'sources'}</b></div><div className="coverage-track"><span style={{ width: `${Math.min(100, shownEvidence.length * 29)}%` }}/></div></div></div>
          <div className="evidence-list-mini"><div className="evidence-list-heading"><span>RETRIEVED EVIDENCE</span>{shownEvidence.length > 0 && <button onClick={() => demoMode ? setDrawerOpen(true) : navigate('/evidence')}>View all <ArrowRight size={12}/></button>}</div>{shownEvidence.slice(0, 2).map(item => <button className="evidence-mini-row" key={item.id} onClick={() => navigate('/evidence')}><span className="evidence-doc-icon"><FileIcon/></span><span className="evidence-mini-copy"><b>{item.title}</b><small>{item.section} <span>·</span> p. {item.page}</small></span><span className="relevance-score">{demoMode ? 'DEMO' : item.relevance.toFixed(3)}</span></button>)}{shownEvidence.length === 0 && <div className="no-evidence-row">No source passages loaded yet.</div>}</div>
          <div className="intel-actions"><Button variant="secondary" onClick={() => setDrawerOpen(true)}><BookIcon/> View evidence</Button><Button variant="primary" onClick={() => navigate('/procedure')}><ClipboardCheck size={15}/> Start procedure</Button></div>
          <div className="processing-line"><div className="processing-line-title"><span>PROCESSING CHAIN</span><span className="processing-total">{demoMode ? 'SIMULATED' : 'LIVE ADAPTERS'}</span></div><div className="processing-steps">{demoMode ? <><span><Check size={11}/> Vision</span><i/><span><Check size={11}/> OCR</span><i/><span><Check size={11}/> Retrieve</span><i/><span><Check size={11}/> Validate</span></> : <><span>Vision · unavailable</span><i/><span>OCR · unavailable</span><i/><span>{shownEvidence.length ? 'Retrieve · local' : 'Retrieve · idle'}</span><i/><span>VLM · unavailable</span></>}</div></div>
        </Card>
        <div className="intel-footnote"><ShieldCheck size={13}/><span>Every recommended action is tied to a local source. Safety-sensitive actions stay gated.</span></div>
      </aside>
    </div>

    <AnimatePresence>{drawerOpen && <><motion.div className="drawer-scrim" onClick={() => setDrawerOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: .55 }} exit={{ opacity: 0 }}/><motion.aside className="evidence-drawer" initial={{ x: 460 }} animate={{ x: 0 }} exit={{ x: 460 }} transition={{ type: 'spring', damping: 28, stiffness: 260 }}><div className="drawer-head"><div><div className="eyebrow">DIAGNOSIS CONTEXT</div><h2>Evidence used</h2></div><button className="icon-button" onClick={() => setDrawerOpen(false)} aria-label="Close evidence"><X size={17}/></button></div><p className="drawer-intro">The finding uses source passages from the fictional ACM-4200 manual and displayed demo observations.</p>{evidence.map(item => <div className="drawer-evidence" key={item.id}><div className="drawer-evidence-meta"><Badge tone={item.sourceType === 'manual' ? 'blue' : 'lime'}>{item.sourceType === 'manual' ? 'MANUAL' : 'OBSERVATION'}</Badge><span>RELEVANCE {item.relevance.toFixed(2)}</span></div><h3>{item.title}</h3><p>{item.excerpt}</p><div className="drawer-citation"><BookIcon/>{item.document}<span>p. {item.page}</span></div></div>)}<Button variant="primary" className="drawer-cta" onClick={() => navigate('/evidence')}>Open evidence viewer <ArrowRight size={14}/></Button></motion.aside></>}</AnimatePresence>
  </div>
}

function FileIcon() { return <span className="file-glyph">PDF</span> }
function BookIcon() { return <span className="book-glyph">▤</span> }
