import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, ArrowRight, Camera, Check, ChevronDown, CircleAlert, ClipboardCheck, CloudOff, Focus, ImagePlus, Info, Mic, MoreHorizontal, ScanLine, Send, ShieldCheck, Sparkles, Square, Waves, X, ZoomIn } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { Badge, Button, Card } from '../components/ui'
import { EquipmentArt } from '../components/EquipmentArt'
import { useLocalFix } from '../state/LocalFixContext'
import type { Evidence, OCRObservation, VisualDetection } from '../types'

type CameraState = 'idle' | 'scanning' | 'ready' | 'error'
type ComponentLocation = { target: string; box: [number, number, number, number]; model: string; latencyMs: number }

export default function DiagnosePage() {
  const { demoMode, evidence, setEvidence, diagnosis, setDiagnosis, componentShown, setComponentShown, runtime,
    currentAsset, setCurrentAsset, ocrResult, setOcrResult, detections, setDetections } = useLocalFix()
  const [cameraState, setCameraState] = useState<CameraState>('idle')
  const [cameraOn, setCameraOn] = useState(false)
  const [videoError, setVideoError] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [imageBlob, setImageBlob] = useState<Blob | null>(null)
  const [question, setQuestion] = useState('')
  const [transcript, setTranscript] = useState('')
  const [listening, setListening] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [locating, setLocating] = useState(false)
  const [componentLocation, setComponentLocation] = useState<ComponentLocation | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [torch, setTorch] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [message, setMessage] = useState('')
  const [liveEvidence, setLiveEvidence] = useState<Evidence[]>([])
  const [liveDiagnosis, setLiveDiagnosis] = useState<string | null>(null)
  const [liveExplanation, setLiveExplanation] = useState('')
  const [liveVisualObservation, setLiveVisualObservation] = useState('')
  const [liveAnswerOrigin, setLiveAnswerOrigin] = useState<'rule_summary' | 'local_vlm_validated'>('rule_summary')
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const audioStreamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const fileRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
      void videoRef.current.play().catch(() => undefined)
    }
  }, [cameraOn])

  useEffect(() => () => {
    streamRef.current?.getTracks().forEach(track => track.stop())
    audioStreamRef.current?.getTracks().forEach(track => track.stop())
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }, [])

  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl) }, [imageUrl])

  async function connectCamera() {
    setVideoError('')
    if (cameraOn) { streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null; setCameraOn(false); setCameraState('idle'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      streamRef.current = stream; setCameraOn(true); setCameraState('ready')
    } catch { setVideoError('Camera unavailable or permission denied. You can continue with the clearly labeled demo scene.'); setCameraState('error') }
  }

  function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    if (file.type === 'image/svg+xml') { setMessage('Use PNG, JPEG, or WebP for imported images. The built-in synthetic illustration can still be scanned locally.'); return }
    if (!file.type.startsWith('image/')) { setMessage('Choose a supported image file.'); return }
    if (file.size > 20 * 1024 * 1024) { setMessage('Images must be under 20 MB for local analysis.'); return }
    if (imageUrl) URL.revokeObjectURL(imageUrl)
    streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null
    setCameraOn(false); setImageBlob(file); setImageUrl(URL.createObjectURL(file)); setCameraState('ready')
    setMessage(demoMode ? 'Image is displayed locally. Switch to Local Runtime to run actual OCR and model inference.' : 'Image loaded locally. Press Scan to run installed on-device models.')
  }

  async function currentFrameBlob(): Promise<Blob | null> {
    if (cameraOn && videoRef.current?.videoWidth && videoRef.current.videoHeight) {
      const video = videoRef.current
      const scale = Math.min(1, 1920 / video.videoWidth)
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale)
      const context = canvas.getContext('2d')
      if (!context) return null
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      return await new Promise(resolve => canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.88))
    }
    if (imageUrl) return rasterizeImageUrl(imageUrl)
    if (!demoMode) {
      const illustration = document.querySelector('.camera-stage > svg')
      if (illustration) {
        const source = new XMLSerializer().serializeToString(illustration)
        const localUrl = URL.createObjectURL(new Blob([source], { type: 'image/svg+xml' }))
        try { return await rasterizeImageUrl(localUrl) }
        finally { URL.revokeObjectURL(localUrl) }
      }
    }
    return imageBlob
  }

  async function frameToBase64(blob: Blob): Promise<string> {
    return await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onerror = () => reject(new Error('Could not read the local image.'))
      reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
      reader.readAsDataURL(blob)
    })
  }

  async function freezeFrame() {
    const blob = await currentFrameBlob()
    if (!blob) { setMessage('Connect the camera or import an image before freezing a frame.'); return }
    if (imageUrl) URL.revokeObjectURL(imageUrl)
    setImageBlob(blob); setImageUrl(URL.createObjectURL(blob))
    streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null
    setCameraOn(false); setCameraState('ready'); setMessage('Frame captured to memory on this device. It will not be saved unless you add it to a case.')
  }

  async function startScan() {
    setComponentShown(false); setDetections([]); setComponentLocation(null)
    if (demoMode) {
      if (cameraOn || imageBlob) { setMessage('Switch to Local Runtime to analyze camera or imported images. The demo scene remains simulated.'); return }
      setCameraState('scanning'); setProcessing(true)
      window.setTimeout(() => { setCameraState('ready'); setProcessing(false); setMessage('Demo scene analyzed. All detections and timings are simulated.') }, 1200)
      return
    }
    const frame = await currentFrameBlob()
    if (!frame) { setMessage('Connect the camera or import an image before scanning.'); return }
    setCameraState('scanning'); setProcessing(true); setMessage('')
    try {
      const imageBase64 = await frameToBase64(frame)
      const ocrRequest = fetch('/api/vision/ocr', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image_base64: imageBase64 }), signal: AbortSignal.timeout(45000) })
      const detectionRequest = runtime.models.vision === 'ready'
        ? fetch('/api/vision/detect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image_base64: imageBase64 }), signal: AbortSignal.timeout(45000) })
        : null
      const ocrResponse = await ocrRequest
      const ocrPayload = await ocrResponse.json()
      if (!ocrResponse.ok) throw new Error(ocrPayload.detail?.message ?? 'Local OCR is unavailable.')
      const values = (ocrPayload.values ?? []) as OCRObservation[]
      let detectorWarning = ''
      setOcrResult(values)
      setCurrentAsset({
        model: values.find(value => value.kind === 'model')?.normalized ?? null,
        serialNumber: values.find(value => value.kind === 'serial')?.normalized ?? null,
        faultCode: values.find(value => value.kind === 'fault')?.normalized ?? null,
      })
      if (detectionRequest) {
        const detectionResponse = await detectionRequest
        const detectionPayload = await detectionResponse.json()
        if (detectionResponse.ok) setDetections((detectionPayload.detections ?? []) as VisualDetection[])
        else detectorWarning = detectionPayload.detail?.message ?? 'The configured component detector could not process the frame.'
      }
      const extracted = values.map(value => `${value.kind}: ${value.normalized}`).join(' · ')
      const syntheticNote = !cameraOn && !imageUrl ? ' The illustrated sample is synthetic.' : ''
      setMessage(detectorWarning || (extracted ? `Local OCR read: ${extracted}. Frame processed on this device.${syntheticNote}` : `The local OCR model found no readable equipment labels or fault codes in this frame.${syntheticNote}`))
    } catch (error) {
      setOcrResult([]); setCurrentAsset({ model: null, serialNumber: null, faultCode: null })
      setMessage(`${error instanceof Error ? error.message : 'Local image analysis failed.'} The image was not sent to a remote service.`)
    } finally { setCameraState('ready'); setProcessing(false) }
  }

  async function locateComponent() {
    if (demoMode) {
      setComponentShown(true)
      setMessage('Demo localization simulated. Switch to Local Runtime for an on-device visual estimate.')
      return
    }
    if (runtime.models.reasoning !== 'ready') {
      setMessage('Install and load the local multimodal model before requesting a component location.')
      return
    }
    const frame = await currentFrameBlob()
    if (!frame) { setMessage('Connect the camera or import an image before locating a component.'); return }
    const target = requestedComponentTarget(question)
    setLocating(true); setComponentLocation(null); setMessage('The local VLM is estimating a visible region…')
    try {
      const imageBase64 = await frameToBase64(frame)
      const response = await fetch('/api/vision/locate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: imageBase64, target }),
        signal: AbortSignal.timeout(210000),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail?.message ?? 'Local visual localization is unavailable.')
      if (!result.found || !Array.isArray(result.box) || result.box.length !== 4) {
        setMessage(`The local model could not clearly locate “${target}” in this frame. Move closer, improve lighting, and try again.`)
        return
      }
      const [x0, y0, x1, y1] = result.box.map(Number) as [number, number, number, number]
      if (![x0, y0, x1, y1].every(value => Number.isFinite(value) && value >= 0 && value <= 1) || x1 <= x0 || y1 <= y0) {
        setMessage('The local model returned an invalid region; no highlight was shown.')
        return
      }
      if (cameraOn) {
        if (imageUrl) URL.revokeObjectURL(imageUrl)
        setImageBlob(frame); setImageUrl(URL.createObjectURL(frame))
        streamRef.current?.getTracks().forEach(track => track.stop()); streamRef.current = null
        setCameraOn(false)
      }
      setZoom(1)
      setComponentLocation({ target: String(result.target ?? target), box: [x0, y0, x1, y1], model: String(result.model), latencyMs: Number(result.latency_ms) })
      setMessage(`Local VLM visual estimate shown for “${target}”. This is not a calibrated detector result; verify it against the equipment.`)
    } catch (error) {
      setMessage(`${error instanceof Error ? error.message : 'Local component localization failed.'} No location was fabricated.`)
    } finally { setLocating(false) }
  }

  async function runQuestion(event?: FormEvent) {
    event?.preventDefault()
    const query = question.trim() || transcript.trim()
    if (!query) { setMessage('Enter a question or use the demo voice prompt first.'); return }
    setProcessing(true); setMessage(''); setLiveVisualObservation(''); setLiveAnswerOrigin('rule_summary')
    if (demoMode) {
      window.setTimeout(() => {
        const supported = /e07|motor|relay|connector|fault|acm-4200/i.test(query)
        setDiagnosis(supported ? 'Motor control feedback mismatch' : 'No supported answer for this question')
        setProcessing(false)
        setMessage('Simulated demo response grounded in the fictional ACM-4200 manual.')
      }, 760)
      return
    }
    const equipmentModel = currentAsset.model?.toUpperCase() === 'ACM-4200' ? 'DemoTech ACM-4200' : currentAsset.model
    const observations = [
      ...ocrResult.map(value => `OCR ${value.kind}: ${value.normalized}`),
      ...detections.map(value => `Vision detector: ${value.label} (${value.confidence.toFixed(3)})`),
    ]
    try {
      let imageBase64: string | undefined
      if (runtime.models.reasoning === 'ready') {
        const frame = await currentFrameBlob()
        if (frame) imageBase64 = await frameToBase64(frame)
      }
      const response = await fetch('/api/diagnose', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: query, equipment_model: equipmentModel, observations, image_base64: imageBase64, image_mime_type: 'image/jpeg' }),
        signal: AbortSignal.timeout(210000),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail?.message ?? 'Local diagnosis is unavailable.')
      const mapped: Evidence[] = (result.evidence ?? []).map((item: Record<string, unknown>) => ({ id: String(item.id), document: String(item.document_name), documentId: String(item.document_id), equipmentModel: typeof item.equipment_model === 'string' ? item.equipment_model : null, sourceHash: String(item.source_hash ?? ''), page: Number(item.page), section: String(item.section), title: String(item.section), excerpt: String(item.text), relevance: Number(item.retrieval_score ?? 0), sourceType: 'manual' }))
      setLiveEvidence(mapped); setEvidence(mapped)
      setLiveDiagnosis(result.status === 'supported_summary' ? String(result.finding) : null)
      setDiagnosis(result.status === 'supported_summary' ? String(result.finding) : '')
      setLiveExplanation(String(result.explanation ?? ''))
      setLiveVisualObservation(String(result.visual_observation ?? ''))
      setLiveAnswerOrigin(result.answer_origin === 'local_vlm_validated' ? 'local_vlm_validated' : 'rule_summary')
      if (result.status === 'supported_summary' && result.answer_origin === 'local_vlm_validated') {
        setMessage(`Local ${String(result.model)} reviewed the camera frame and manual passages. Its summary passed evidence checks; procedures remain source-gated.`)
      } else if (result.status === 'supported_summary') {
        setMessage('The local source rule summary is validated against retrieved manual text. No local VLM response passed validation.')
      } else {
        setMessage('The local sources do not support a finding. No procedure was generated.')
      }
    } catch (error) {
      setLiveEvidence([]); setEvidence([]); setLiveDiagnosis(null); setDiagnosis(''); setLiveExplanation(''); setLiveVisualObservation('')
      setMessage(`${error instanceof Error ? error.message : 'Local service unavailable.'} No unsupported answer was shown.`)
    } finally { setProcessing(false) }
  }

  async function toggleVoiceCapture() {
    if (demoMode) {
      if (listening) { setListening(false); setTranscript('Why is this machine showing E07?'); setQuestion('Why is this machine showing E07?'); return }
      setListening(true); setTranscript(''); window.setTimeout(() => { setListening(false); setTranscript('Why is this machine showing E07?'); setQuestion('Why is this machine showing E07?') }, 1450)
      return
    }
    if (listening) { recorderRef.current?.stop(); setListening(false); return }
    if (runtime.models.speech !== 'ready') { setMessage('Local speech recognition needs the optional faster-whisper model. Run backend/setup-local-ai.ps1 on this AMD64 development host.'); return }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false })
      audioStreamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : ''
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      recorderRef.current = recorder; audioChunksRef.current = []; setTranscript(''); setListening(true)
      recorder.ondataavailable = event => { if (event.data.size) audioChunksRef.current.push(event.data) }
      recorder.onerror = () => { setListening(false); setMessage('Microphone capture failed. No audio was stored.') }
      recorder.onstop = () => {
        stream.getTracks().forEach(track => track.stop()); audioStreamRef.current = null; setListening(false)
        const audio = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (audio.size) void transcribeLocalAudio(audio)
      }
      recorder.start()
      window.setTimeout(() => { if (recorder.state === 'recording') recorder.stop() }, 30_000)
    } catch (error) { setMessage(`Microphone unavailable or permission denied: ${error instanceof Error ? error.message : 'capture failed'}.`) }
  }

  async function transcribeLocalAudio(audio: Blob) {
    setProcessing(true); setMessage('Transcribing audio locally…')
    try {
      const audioBase64 = await frameToBase64(audio)
      const response = await fetch('/api/speech/transcribe', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_base64: audioBase64, content_type: audio.type || 'audio/webm' }),
        signal: AbortSignal.timeout(120000),
      })
      const result = await response.json()
      if (!response.ok) throw new Error(result.detail?.message ?? 'Local speech recognition failed.')
      const words = String(result.transcript ?? '').trim()
      setTranscript(words); setQuestion(words)
      setMessage(words ? `Transcribed on device using ${result.model} · ${result.backend}.` : 'The local speech model did not detect speech in this clip.')
    } catch (error) { setMessage(`${error instanceof Error ? error.message : 'Local speech recognition failed.'} Audio was not sent to a remote service.`) }
    finally { setProcessing(false) }
  }

  const shownEvidence = demoMode ? evidence : liveEvidence
  const shownDiagnosis = demoMode ? diagnosis : liveDiagnosis
  const noAnswer = !shownDiagnosis || shownDiagnosis === 'No supported answer for this question'
  const demoScene = demoMode && !cameraOn && !imageUrl
  const visionAvailable = runtime.models.vision === 'ready'
  const ocrAvailable = runtime.models.ocr === 'ready'
  const componentTarget = requestedComponentTarget(question)
  return <div className="diagnose-page">
    <div className="diagnose-topline"><div><div className="eyebrow">FIELD SESSION <span className="eyebrow-separator">/</span> ACTIVE ASSET</div><h1>Live diagnosis <span className="live-pulse"/></h1></div><div className="diagnose-top-actions"><Badge tone={demoMode ? 'amber' : 'neutral'}>{demoMode ? 'DEMO · SIMULATED' : 'LOCAL RUNTIME'}</Badge><Button variant="secondary" size="small"><MoreHorizontal size={17}/></Button></div></div>
    <div className="diagnose-workspace">
      <section className="camera-column">
        <Card className="camera-card">
          <div className="camera-toolbar"><div className="camera-source"><span className="camera-source-icon"><Camera size={14}/></span><span><b>{cameraOn ? 'Device camera' : imageUrl ? 'Imported image' : 'ACM-4200 · Demo scene'}</b><small>{cameraOn ? 'LIVE FEED · LOCAL' : imageUrl ? 'LOCAL IMAGE' : 'SIMULATED CAMERA FEED'}</small></span><ChevronDown size={14}/></div><div className="camera-tools"><button onClick={connectCamera} aria-label={cameraOn ? 'Stop device camera' : 'Connect device camera'} className={cameraOn ? 'tool-active' : ''}><Camera size={15}/><span>{cameraOn ? 'Stop' : 'Camera'}</span></button><button onClick={startScan} disabled={processing}><ScanLine size={15}/><span>Scan</span></button><button onClick={() => setTorch(value => !value)} className={torch ? 'tool-active' : ''} aria-label="Toggle torch simulation"><Sparkles size={15}/><span>Torch</span></button><button onClick={() => setZoom(value => value >= 1.4 ? 1 : value + .2)} aria-label="Zoom camera"><ZoomIn size={15}/><span>{zoom.toFixed(1)}×</span></button><button onClick={() => fileRef.current?.click()} aria-label="Import image"><ImagePlus size={15}/></button><input ref={fileRef} type="file" accept="image/*" onChange={onFile} hidden/></div></div>
          <div className={`camera-stage ${cameraState === 'scanning' ? 'is-scanning' : ''} ${torch ? 'torch-on' : ''}`}>
            {cameraOn ? <video ref={videoRef} autoPlay playsInline muted className="camera-video" style={{ transform: `scale(${zoom})` }}/> : imageUrl ? <img src={imageUrl} className="camera-upload" alt="Technician selected equipment" style={{ transform: `scale(${zoom})` }}/> : <EquipmentArt/>}
            {!cameraOn && !imageUrl && <div className="scene-grid"/>}
            <div className="camera-vignette"/>
            {cameraState === 'scanning' && <motion.div className="scan-sweep" initial={{ top: '8%' }} animate={{ top: '90%' }} transition={{ duration: 1.15, ease: 'linear' }}/>} 
            <div className="camera-hud-top"><span className="hud-chip"><span className="hud-dot"/> {cameraState === 'scanning' ? 'SCANNING EQUIPMENT' : cameraOn ? 'CAMERA ACTIVE' : 'FIELD VIEW'}</span><span className="hud-chip hud-time">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} <span className="hud-divider"/> LOCAL</span></div>
            <div className="camera-hud-bottom"><span><Focus size={13}/> FRAME 01</span><span>16:10 <span className="hud-divider"/> 1280 × 800</span></div>
            {demoScene && <motion.div className={`detected-model ${componentShown ? 'model-targeted' : ''}`} animate={{ scale: componentShown ? 1.04 : 1 }}><span className="box-corner corner-tl"/><span className="box-corner corner-tr"/><span className="box-corner corner-bl"/><span className="box-corner corner-br"/><span className="detection-eyebrow">IDENTIFIED MODEL</span><b>ACM-4200</b><small>MODEL LABEL · SIMULATED</small></motion.div>}
            {demoScene && <div className="detected-fault"><span className="fault-marker">E07</span><span><small>DISPLAY OCR · DEMO</small><b>Motor fault</b></span></div>}
            {!demoMode && detections.map((item, index) => <div key={`${item.label}-${index}`} className={`live-detection-box ${componentShown && item.label.toLowerCase().includes('relay') ? 'detection-targeted' : ''}`} style={{ left: `${item.box[0] * 100}%`, top: `${item.box[1] * 100}%`, width: `${(item.box[2] - item.box[0]) * 100}%`, height: `${(item.box[3] - item.box[1]) * 100}%` }}><span>{item.label.replaceAll('_', ' ')} · {item.confidence.toFixed(2)}</span></div>)}
            {!demoMode && ocrResult.filter(item => item.box && item.kind !== 'other').map((item, index) => <div key={`${item.normalized}-${index}`} className="live-ocr-box" style={{ left: `${(item.box?.[0] ?? 0) * 100}%`, top: `${(item.box?.[1] ?? 0) * 100}%`, width: `${((item.box?.[2] ?? 0) - (item.box?.[0] ?? 0)) * 100}%`, height: `${((item.box?.[3] ?? 0) - (item.box?.[1] ?? 0)) * 100}%` }}><span>OCR · {item.normalized}</span></div>)}
            {!demoMode && componentLocation && <div role="note" aria-label={`Local model estimated location of ${componentLocation.target}`} className="model-location-estimate" style={{ left: `${componentLocation.box[0] * 100}%`, top: `${componentLocation.box[1] * 100}%`, width: `${(componentLocation.box[2] - componentLocation.box[0]) * 100}%`, height: `${(componentLocation.box[3] - componentLocation.box[1]) * 100}%` }}><span>{componentLocation.target.toUpperCase()} · MODEL ESTIMATE</span></div>}
            <AnimatePresence>{componentShown && demoScene && <motion.div className="relay-target" initial={{ opacity: 0, scale: .96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}><span className="relay-target-corners"/><span className="relay-target-label"><span className="target-dot"/> MOTOR RELAY K2 <small>DEMO LOCALIZATION</small></span></motion.div>}</AnimatePresence>
            {!demoMode && !visionAvailable && <div className="camera-error camera-no-model"><CircleAlert size={15}/><span>{detections.length ? `${detections.length} LIVE DETECTIONS` : 'COMPONENT DETECTOR NOT INSTALLED'} <small>{ocrAvailable ? 'LOCAL OCR IS AVAILABLE · CUSTOM TRAINED DETECTOR WEIGHTS REQUIRED' : 'INSTALL LOCAL OCR MODELS TO READ LABELS · NO VISION MODEL LOADED'}</small></span></div>}
            {cameraState === 'idle' && <div className="camera-empty-hint"><div><ScanLine size={17}/><span>Scene ready for inspection</span><small>Scan or connect your camera to begin</small></div></div>}
            {cameraState === 'error' && <div className="camera-error"><CircleAlert size={16}/>{videoError}</div>}
            {torch && <div className="torch-overlay"/>}
          </div>
          <div className="camera-statusbar"><div className="camera-state-label"><span className={`state-led ${cameraState === 'ready' ? 'led-ready' : cameraState === 'scanning' ? 'led-scanning' : ''}`}/><span>{cameraState === 'scanning' ? 'ANALYZING FRAME' : cameraState === 'ready' ? 'READY' : cameraState === 'error' ? 'CAMERA ERROR' : 'STANDBY'}</span><span className="statusbar-divider"/><span className="source-local"><CloudOff size={12}/> ON DEVICE · NO UPLOAD</span></div><button className="freeze-button" onClick={freezeFrame}><Square size={12}/> Capture frame</button></div>
        </Card>
        <div className="voice-composer card"><div className={`voice-button ${listening ? 'voice-listening' : ''}`}><button onClick={toggleVoiceCapture} aria-label={listening ? 'Stop recording and transcribe' : demoMode ? 'Play simulated voice transcript' : 'Record question on device'}>{listening ? <Waves size={19}/> : <Mic size={18}/>}</button><span className="voice-ring"/></div><div className="voice-main"><div className="voice-label">{listening ? 'LISTENING…' : transcript ? 'VOICE TRANSCRIPT' : 'ASK LOCALFIX'}</div>{transcript ? <div className="transcript-text">“{transcript}” <Badge tone={demoMode ? 'amber' : 'lime'}>{demoMode ? 'SIMULATED VOICE' : 'LOCAL ASR'}</Badge></div> : <input aria-label="Ask LocalFix a question" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') runQuestion() }} placeholder={listening ? 'Recording locally… press mic to finish' : 'Ask about the equipment, fault, or next step…'}/>}<small>{demoMode ? 'Demo transcript uses a sample phrase. No microphone audio is captured.' : runtime.models.speech === 'ready' ? 'English audio is captured and transcribed on this device. Press the mic again to stop.' : 'Local ASR model unavailable. Typed questions and offline manual retrieval still work.'}</small></div><Button variant="primary" className="ask-button" disabled={processing || listening} onClick={() => runQuestion()}>{processing ? <span className="mini-spinner"/> : <Send size={15}/>}<span>{processing ? 'Working' : 'Ask'}</span></Button><button className="voice-more" aria-label="Voice options"><MoreHorizontal size={17}/></button></div>
        {message && <div className="diagnose-notice"><Info size={14}/><span>{message}</span><button onClick={() => setMessage('')} aria-label="Dismiss"><X size={13}/></button></div>}
      </section>

      <aside className="intelligence-column">
        <Card className="intelligence-card">
          <div className="intel-header"><div><span className="intel-overline"><span className="intel-orb"><Sparkles size={12}/></span> LOCALFIX INTELLIGENCE</span><h2>AI diagnosis</h2></div><Badge tone={demoMode ? 'amber' : 'neutral'}>{demoMode ? 'SIMULATED' : 'LOCAL · SOURCE RULES'}</Badge></div>
          <div className="intel-equipment"><div className="intel-equipment-icon"><Activity size={17}/></div><div><b>{demoMode ? 'DemoTech ACM-4200' : currentAsset.model ?? 'Equipment not verified'}</b><small>{demoMode ? 'Industrial motor controller · demo asset' : currentAsset.serialNumber ?? (ocrAvailable ? 'Read from camera OCR · verify identity' : 'Run local OCR to identify equipment')}</small></div><button aria-label="Equipment details"><MoreHorizontal size={16}/></button></div>
          <div className="intel-observation"><div className="intel-observation-label"><span>{demoMode ? 'OBSERVED CONDITION · DEMO' : 'CAMERA OBSERVATIONS'}</span>{(demoMode || currentAsset.faultCode) && <Badge tone="red">{demoMode ? 'E07' : currentAsset.faultCode}</Badge>}</div><div className="intel-code-line"><span className="code-glyph">{demoMode || currentAsset.faultCode ? '!' : '—'}</span><div><b>{demoMode ? 'Motor feedback mismatch' : currentAsset.faultCode ? `${currentAsset.faultCode} read by OCR` : 'No fault code read'}</b><small>{demoMode ? 'Sample display text · OCR simulated' : ocrResult.length ? `${ocrResult.length} local OCR values · review boxes on frame` : ocrAvailable ? 'Scan a camera frame or imported image' : 'Install the optional local OCR package'}</small></div></div>{demoMode ? <div className="intel-tags"><span><Check size={12}/> ACM-4200 · demo</span><span><Check size={12}/> E07 · demo</span><span><ShieldCheck size={12}/> Source matched</span></div> : ocrResult.length > 0 && <div className="intel-tags">{ocrResult.slice(0, 3).map((value, index) => <span key={`${value.kind}-${index}`}><Check size={12}/> {value.normalized}</span>)}</div>}</div>
          <div className="diagnosis-block"><div className="diagnosis-block-head"><span>{noAnswer ? 'NO SUPPORTED FINDING' : 'SUPPORTED FINDING'}</span>{!noAnswer && <span className="evidence-strength"><span/> {liveAnswerOrigin === 'local_vlm_validated' && !demoMode ? 'LOCAL VLM · EVIDENCE-VALIDATED' : 'SOURCE-ALIGNED'}</span>}</div><h3>{noAnswer ? 'No reliable evidence' : shownDiagnosis}</h3><p>{noAnswer ? demoMode ? 'The local manual does not contain enough support for this question. Try asking about E07, the relay, or connector checks.' : 'Ask a question to retrieve local manual passages. Equipment identity and live OCR are not verified.' : demoMode ? 'The service manual links E07 to motor feedback. Begin with the cited visual checks after confirming the safe state.' : liveExplanation}</p>{!demoMode && liveVisualObservation && <div className="vlm-observation"><span>CAMERA OBSERVATION · LOCAL MODEL</span><p>{liveVisualObservation}</p></div>}<div className="source-coverage"><div className="coverage-label"><span>Retrieved sources</span><b>{shownEvidence.length} {shownEvidence.length === 1 ? 'source' : 'sources'}</b></div><div className="coverage-track"><span style={{ width: `${Math.min(100, shownEvidence.length * 29)}%` }}/></div></div></div>
          <div className="evidence-list-mini"><div className="evidence-list-heading"><span>RETRIEVED EVIDENCE</span>{shownEvidence.length > 0 && <button onClick={() => demoMode ? setDrawerOpen(true) : navigate('/evidence')}>View all <ArrowRight size={12}/></button>}</div>{shownEvidence.slice(0, 2).map(item => <button className="evidence-mini-row" key={item.id} onClick={() => navigate('/evidence')}><span className="evidence-doc-icon"><FileIcon/></span><span className="evidence-mini-copy"><b>{item.title}</b><small>{item.section} <span>·</span> p. {item.page}</small></span><span className="relevance-score">{demoMode ? 'DEMO' : item.relevance.toFixed(3)}</span></button>)}{shownEvidence.length === 0 && <div className="no-evidence-row">No source passages loaded yet.</div>}</div>
          <div className="target-action-row"><Button variant="secondary" onClick={locateComponent} disabled={locating}><Focus size={14}/>{locating ? 'Locating…' : `Show ${componentTarget}`}</Button><span>{demoMode ? 'SIMULATED' : componentLocation ? `${componentLocation.model} · ${Math.round(componentLocation.latencyMs)} ms · estimated region` : runtime.models.reasoning === 'ready' ? 'LOCAL VLM · ESTIMATE' : 'LOCAL VLM REQUIRED'}</span></div>
          <div className="intel-actions"><Button variant="secondary" onClick={() => setDrawerOpen(true)}><BookIcon/> View evidence</Button><Button variant="primary" onClick={() => navigate('/procedure')}><ClipboardCheck size={15}/> Start procedure</Button></div>
          <div className="processing-line"><div className="processing-line-title"><span>PROCESSING CHAIN</span><span className="processing-total">{demoMode ? 'SIMULATED' : 'DEVICE STATUS'}</span></div><div className="processing-steps">{demoMode ? <><span><Check size={11}/> Vision</span><i/><span><Check size={11}/> OCR</span><i/><span><Check size={11}/> Retrieve</span><i/><span><Check size={11}/> Validate</span></> : <><span>{detections.length ? `Vision · ${detections.length}` : visionAvailable ? 'Vision · ready' : 'Vision · weights needed'}</span><i/><span>{ocrAvailable ? 'OCR · local' : 'OCR · unavailable'}</span><i/><span>{runtime.retrieval?.semantic ? 'Retrieve · hybrid' : 'Retrieve · FTS5'}</span><i/><span>{runtime.models.reasoning === 'ready' ? 'VLM · local' : 'VLM · unavailable'}</span></>}</div></div>
        </Card>
        <div className="intel-footnote"><ShieldCheck size={13}/><span>Every recommended action is tied to a local source. Safety-sensitive actions stay gated.</span></div>
      </aside>
    </div>

    <AnimatePresence>{drawerOpen && <><motion.div className="drawer-scrim" onClick={() => setDrawerOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: .55 }} exit={{ opacity: 0 }}/><motion.aside className="evidence-drawer" initial={{ x: 460 }} animate={{ x: 0 }} exit={{ x: 460 }} transition={{ type: 'spring', damping: 28, stiffness: 260 }}><div className="drawer-head"><div><div className="eyebrow">DIAGNOSIS CONTEXT</div><h2>Evidence used</h2></div><button className="icon-button" onClick={() => setDrawerOpen(false)} aria-label="Close evidence"><X size={17}/></button></div><p className="drawer-intro">{demoMode ? 'The finding uses source passages from the fictional ACM-4200 manual and simulated observations.' : liveAnswerOrigin === 'local_vlm_validated' ? 'The local VLM summary cites these retrieved passages. Its visual observation is shown separately; the VLM cannot create or authorize procedures.' : 'The rule summary uses local manual passages and this session’s camera observations. No VLM response passed evidence validation.'}</p>{shownEvidence.map(item => <div className="drawer-evidence" key={item.id}><div className="drawer-evidence-meta"><Badge tone={item.sourceType === 'manual' ? 'blue' : 'lime'}>{item.sourceType === 'manual' ? 'MANUAL' : 'OBSERVATION'}</Badge><span>RELEVANCE {item.relevance.toFixed(2)}</span></div><h3>{item.title}</h3><p>{item.excerpt}</p><div className="drawer-citation"><BookIcon/>{item.document}<span>p. {item.page}</span></div></div>)}<Button variant="primary" className="drawer-cta" onClick={() => navigate('/evidence')}>Open evidence viewer <ArrowRight size={14}/></Button></motion.aside></>}</AnimatePresence>
  </div>
}

function FileIcon() { return <span className="file-glyph">PDF</span> }
function BookIcon() { return <span className="book-glyph">▤</span> }

function requestedComponentTarget(question: string): string {
  const namedTarget = question.match(/\b(?:show|find|locate|point out)\s+(?:me\s+)?(?:the\s+)?(.+?)(?:[?.!]|$)/i)?.[1]
  return (namedTarget?.trim() || 'motor relay K2').slice(0, 80)
}

async function rasterizeImageUrl(url: string): Promise<Blob | null> {
  const image = new Image()
  image.src = url
  await image.decode()
  const scale = Math.min(1, 1920 / image.naturalWidth)
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
  const context = canvas.getContext('2d')
  if (!context) return null
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  return await new Promise(resolve => canvas.toBlob(blob => resolve(blob), 'image/jpeg', 0.9))
}
