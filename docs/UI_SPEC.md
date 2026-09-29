# LocalFix UI specification

The interface uses a near-black graphite base, thin green-gray borders, restrained electric-lime emphasis, amber safety cues, compact metadata, and roomy page hierarchy. Inter/Segoe UI system fonts keep the product fully offline. Cards use 12–14 px radius, minimal shadow, and no broad gradients. The implementation uses small local shadcn-style primitives (`Button`, `Badge`, `Card`) with Radix Tabs dependency available for future expansion; Motion handles route/drawer transitions and CSS prefers-reduced-motion controls motion.

## Navigation and route map

| Route | Primary screen | Main task |
|---|---|---|
| `/` | Operations Home | Start a diagnosis, review runtime and recent cases |
| `/diagnose` | Live Diagnose | Camera/import, ask, retrieve and review the supported finding |
| `/evidence` | Evidence Inspector | Inspect source page, rank and citation chain; ingest local PDFs |
| `/procedure` | Procedure | Review cited steps and explicitly confirm the safe state |
| `/cases` | Cases | Search a local case and inspect source-backed activity |
| `/reports` | Reports / Runtime tabs | Export a report; inspect actual model and device availability |

The shared sidebar and topbar show workspace, network, demo/local mode, and device status. Settings navigation opens the Runtime tab. All core actions have visible focus states; camera and microphone controls have accessible labels. Demo scene artwork is original SVG and remains labeled as synthetic.

## Interaction states

Camera: standby → scanning → ready, with explicit camera error and model-unavailable states. Voice demo uses a sample transcript and captures no audio; live ASR is unavailable until a local adapter is complete. Diagnosis states include analyzing, supported summary, insufficient evidence, and backend/model error. Procedure states include waiting, technician-reported safe-state acknowledgement, step completion, and case save. Reduced-motion users receive immediate state changes with no continuous animation.

## Information hierarchy

The Live Diagnose view keeps the camera stage larger than the intelligence panel. The inspector makes source page and retrieval score visible beside the finding. Score labels say “retrieval relevance” or “FTS5 relevance”; they are not described as calibrated probability. Procedures display source, page, reason, safety level, and completion. The report preview marks simulation and distinguishes manual evidence from live OCR observations.
