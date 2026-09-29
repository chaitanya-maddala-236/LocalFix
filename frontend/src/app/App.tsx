import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/AppShell'

const HomePage = lazy(() => import('../pages/HomePage'))
const DiagnosePage = lazy(() => import('../pages/DiagnosePage'))
const EvidencePage = lazy(() => import('../pages/EvidencePage'))
const ProcedurePage = lazy(() => import('../pages/ProcedurePage'))
const CasesPage = lazy(() => import('../pages/CasesPage'))
const ReportsPage = lazy(() => import('../pages/ReportsPage'))

export default function App() {
  return <Suspense fallback={<div className="route-loading" role="status">Loading LocalFix workspace…</div>}><Routes><Route element={<AppShell/>}>
    <Route index element={<HomePage/>}/><Route path="diagnose" element={<DiagnosePage/>}/>
    <Route path="evidence" element={<EvidencePage/>}/><Route path="procedure" element={<ProcedurePage/>}/>
    <Route path="cases" element={<CasesPage/>}/><Route path="reports" element={<ReportsPage/>}/>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Route></Routes></Suspense>
}
