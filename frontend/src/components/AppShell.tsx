import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Activity, BookOpen, Boxes, ChevronDown, CircleHelp, ClipboardList, Command, FileText, Gauge, HardDrive, LayoutDashboard, Radio, Settings2, ShieldCheck, Wifi, WifiOff, Zap } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useLocalFix } from '../state/LocalFixContext'
import { getCases, getRuntime } from '../services/api'
import { demoCases, demoEvidence, demoRuntime } from '../data/demo'
import { Badge } from './ui'

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/diagnose', label: 'Diagnose', icon: Activity },
  { to: '/evidence', label: 'Manuals & evidence', icon: BookOpen },
  { to: '/procedure', label: 'Procedure', icon: ClipboardList },
  { to: '/cases', label: 'Cases', icon: Boxes },
  { to: '/reports', label: 'Reports & runtime', icon: FileText },
]

const titles: Record<string, string> = { '/': 'Overview', '/diagnose': 'Live diagnosis', '/evidence': 'Evidence inspector', '/procedure': 'Guided procedure', '/cases': 'Service cases', '/reports': 'Reports & runtime' }

export function AppShell() {
  const location = useLocation()
  const { demoMode, setDemoMode, setRuntime, runtime, setCases, setEvidence, setDiagnosis, setSafetyAcknowledged, setComponentShown, setCurrentAsset, setOcrResult, setDetections } = useLocalFix()
  const [switching, setSwitching] = useState(false)
  const [notice, setNotice] = useState('')
  async function toggleMode() {
    if (demoMode) {
      setSwitching(true)
      try { const next = await getRuntime(); const localCases = await getCases().catch(() => []); setRuntime({ ...next, mode: 'local' }); setCases(localCases); setEvidence([]); setDiagnosis(''); setCurrentAsset({ model: null, serialNumber: null, faultCode: null }); setOcrResult([]); setDetections([]); setComponentShown(false); setSafetyAcknowledged(false); setDemoMode(false); setNotice('Connected to the local runtime. Model availability is shown from device telemetry.') }
      catch { setRuntime({ ...runtime, mode: 'local', simulated: false, backend: 'Backend unavailable', npu: 'unavailable', models: { vision: 'missing', ocr: 'missing', speech: 'missing', reasoning: 'missing' }, latencyMs: {}, ramMb: null }); setCases([]); setEvidence([]); setCurrentAsset({ model: null, serialNumber: null, faultCode: null }); setOcrResult([]); setDetections([]); setDemoMode(false); setNotice('Local backend is unavailable. Start backend/run.ps1 to connect; local AI actions will show their actual availability.') }
      finally { setSwitching(false); window.setTimeout(() => setNotice(''), 5200) }
    } else { setRuntime({ ...demoRuntime, network: navigator.onLine ? 'online' : 'offline' }); setCases(demoCases); setEvidence(demoEvidence); setDiagnosis('Motor control feedback mismatch'); setCurrentAsset({ model: 'DemoTech ACM-4200', serialNumber: 'SN-823919', faultCode: 'E07' }); setOcrResult([]); setDetections([]); setSafetyAcknowledged(false); setComponentShown(false); setDemoMode(true); setNotice('Demo simulation active. Runtime values are not device measurements.'); window.setTimeout(() => setNotice(''), 4200) }
  }
  return <div className="app-shell">
    <aside className="sidebar" aria-label="Main navigation">
      <NavLink to="/" className="brand"><span className="brand-mark"><span/><span/><span/></span><span className="brand-word">LOCAL<span>FIX</span></span></NavLink>
      <div className="workspace-switch"><span className="workspace-avatar">F</span><span className="workspace-copy"><b>Field Ops</b><small>ACM service team</small></span><ChevronDown size={14}/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav className="primary-nav">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={17} strokeWidth={1.8}/><span>{label}</span>{to === '/cases' && <span className="nav-count">{demoMode ? '2' : ''}</span>}</NavLink>)}</nav>
      <div className="sidebar-bottom">
        <div className="sidebar-section-label">DEVICE STATUS</div>
        <div className="device-mini"><div className="device-mini-icon"><Zap size={15}/></div><div className="device-mini-copy"><b>{demoMode ? 'Demo runtime' : runtime.backend}</b><small>{demoMode ? 'SIMULATED' : runtime.npu === 'active' ? 'QNN · NPU' : 'LOCAL · CPU'}</small></div><span className={`status-dot ${runtime.npu === 'active' && !demoMode ? 'good' : ''}`}/></div>
        <div className="sidebar-status-line"><span><WifiOff size={13}/> OFFLINE READY</span><span className="local-dot"/></div>
        <button className="sidebar-help"><CircleHelp size={15}/> Help center <span>↗</span></button>
        <div className="user-row"><div className="user-avatar">JD</div><div className="user-copy"><b>Jordan Davis</b><small>Field technician</small></div><Settings2 size={15}/></div>
      </div>
    </aside>
    <main className="main-shell">
      <header className="topbar">
        <div className="breadcrumb"><span>LOCALFIX</span><span className="crumb-slash">/</span><b>{titles[location.pathname] ?? 'Field operations'}</b></div>
        <div className="topbar-actions"><div className="network-indicator" title="Network interface state; LocalFix does not require internet access"><>{runtime.network === 'online' ? <Wifi size={14}/> : <WifiOff size={14}/>}</><span>{runtime.network === 'offline' ? 'DEVICE OFFLINE' : runtime.network === 'online' ? 'NETWORK UP · LOCAL APP' : 'NETWORK UNKNOWN'}</span></div><span className="top-divider"/><button className={`mode-toggle ${demoMode ? 'is-demo' : ''}`} onClick={toggleMode} disabled={switching} title="Switch between simulated demo and live local runtime"><span className="mode-toggle-icon">{demoMode ? <Command size={14}/> : <HardDrive size={14}/>}</span><span>{switching ? 'CONNECTING…' : demoMode ? 'DEMO MODE' : 'LOCAL RUNTIME'}</span><span className="mode-toggle-state"/></button><button className="icon-button" aria-label="Runtime status"><Gauge size={17}/></button><div className="top-avatar">JD</div></div>
      </header>
      {!demoMode && runtime.backend === 'Backend unavailable' && <div className="backend-banner"><Radio size={15}/><span>Backend not connected. Start the local FastAPI service to use device inference.</span><Badge tone="amber">LIVE MODE · NO MODEL DATA</Badge></div>}
      {notice && <motion.div className="toast-note" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}><ShieldCheck size={15}/>{notice}</motion.div>}
      <div className="page-container"><AnimatePresence mode="wait"><motion.div key={location.pathname} className="route-frame" initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} transition={{ duration: 0.2, ease: 'easeOut' }}><Outlet/></motion.div></AnimatePresence></div>
      <footer className="app-footer"><span><span className="footer-mark">◈</span> LOCALFIX <span className="footer-version">0.1.0</span></span><span><ShieldCheck size={12}/> Your field engineer. Offline. On-device. Evidence-first.</span><span>ALL DATA STAYS ON THIS DEVICE</span></footer>
    </main>
  </div>
}
