# LocalFix competition demo script

**Length:** 3–4 minutes. Start the Vite frontend in Demo Mode. The synthetic camera, sample voice transcript, and sample timings must stay visibly labeled as simulated. Keep the fictional manual disclaimer available. Do not present these as hardware measurements or real repairs.

1. **Frame the problem — Operations Home.** Point to the ACM-4200 field asset card and the local-only/runtime panel. Explain that the demo equipment and manual are fictional and that the product workflow is local-first.
2. **Inspect — Live Diagnose.** Open Live Diagnose. Show the synthetic cabinet artwork, model label, and E07 overlay. Call out “DEMO · SIMULATED.” Choose Scan; explain that the moving scan is a workflow simulation, not detector inference.
3. **Ask by voice.** Use the voice control. The sample transcript appears as “SIMULATED VOICE”; no microphone audio is captured. Ask “Why is this machine showing E07?” The simulated answer connects E07 to the manual's motor feedback description.
4. **Show evidence.** Open View Evidence. Point to retrieved pages 84, 102, and 37, source sections, relevance score, and source chain. Clarify the score is retrieval relevance, not probability.
5. **Locate a component.** Return to diagnosis and select Show Me from the procedure/diagnosis flow. Relay K2 receives a highlighted demo box marked “DEMO LOCALIZATION.” Explain the future live path requires an installed open-vocabulary detector.
6. **Start the procedure.** Open Procedure. Stop at the safety gate. Read the confirmation: only the technician can confirm site-approved isolation; LocalFix cannot verify it. Click explicit acknowledgement and complete the visual-check steps.
7. **Record the work.** Add a factual note and save the case. Open Cases to show the case/evidence timeline, then Reports. Generate the demo PDF and show its simulation label.
8. **Demonstrate offline operation.** Turn Wi-Fi off. Keep the local frontend/API processes running. Ask the same question again in Demo Mode. The complete simulated flow remains available without internet; demo status remains visible.
9. **Close honestly.** Open Runtime. Show blank demo latency fields and unavailable model states. Explain what changes when licensed local weights, preprocessors, output decoders, and a confirmed QNN/QAIRT session are installed.

## Live-device extension

To claim a real Snapdragon NPU result, install an authorized model/runtime, finish its modality-specific adapter, verify `QNNExecutionProvider` in `/runtime/status`, and run a comparable task benchmark. Do not substitute this scripted demo for that measurement.
