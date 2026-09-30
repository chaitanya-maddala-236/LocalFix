from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from ..schemas import CaseResponse


def report_payload(case: CaseResponse, runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": "LocalFix", "case_id": case.case_id, "equipment": case.equipment_model,
        "model": case.equipment_model, "serial_number": case.serial_number,
        "observed_fault": case.fault_code, "observed_evidence": [item.model_dump() for item in case.evidence],
        "camera_observations": case.observations,
        "diagnosis": case.diagnosis, "procedure_performed": [item.model_dump() for item in case.steps],
        "technician_notes": case.notes, "resolution": case.resolution or case.status,
        "manual_references": [{"document": item.document_name, "section": item.section, "page": item.page, "source_hash": item.source_hash} for item in case.evidence],
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"), "runtime_mode": runtime["backend"],
        "model_information": runtime["model_details"], "simulated": case.simulated,
    }


def markdown_report(payload: dict[str, Any]) -> str:
    evidence = "\n".join(f"- {item['document_name']} · {item['section']} · p. {item['page']} · `{item['source_hash'][:12]}`" for item in payload["observed_evidence"])
    steps = "\n".join(f"- {item['action']} ({item['safety_level']})" for item in payload["procedure_performed"])
    observations = "\n".join(f"- {item}" for item in payload["camera_observations"])
    simulated_notice = "> DEMO SIMULATION — data is illustrative, not live model inference.\n\n" if payload["simulated"] else ""
    return (f"# LocalFix service report · {payload['case_id']}\n\n{simulated_notice}"
            f"- Timestamp: {payload['timestamp']}\n- Equipment: {payload['equipment']}\n- Model: {payload['model']}\n"
            f"- Serial: {payload['serial_number'] or 'Not recorded'}\n- Observed fault: {payload['observed_fault'] or 'Not recorded'}\n\n"
            f"## Camera and OCR observations\n\n{observations or 'No camera/OCR observations recorded.'}\n\n"
            f"## Diagnosis\n\n{payload['diagnosis'] or 'Not recorded'}\n\n## Procedure performed\n\n{steps or 'No procedure steps recorded.'}\n\n"
            f"## Technician notes\n\n{payload['technician_notes']}\n\n## Resolution\n\n{payload['resolution']}\n\n"
            f"## Evidence references\n\n{evidence or 'No manual references attached.'}\n\n"
            f"## Runtime\n\n- Backend: {payload['runtime_mode']}\n- Model states: `{json.dumps({key: value['state'] for key, value in payload['model_information'].items()})}`\n"
            "- Network requests: 0 from LocalFix inference APIs\n")


def pdf_report(payload: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="LocalFixTitle", parent=styles["Title"], textColor=colors.HexColor("#273224"), fontSize=20, leading=25, spaceAfter=5))
    styles.add(ParagraphStyle(name="LocalFixSection", parent=styles["Heading2"], textColor=colors.HexColor("#5a7737"), fontSize=10, leading=14, spaceBefore=12, spaceAfter=5))
    styles.add(ParagraphStyle(name="LocalFixBody", parent=styles["BodyText"], fontSize=9, leading=13, textColor=colors.HexColor("#303630")))
    story = [Paragraph("LOCALFIX · FIELD SERVICE", styles["Heading4"]), Paragraph(f"Service report · {escape(str(payload['case_id']))}", styles["LocalFixTitle"]),
             Paragraph(escape(str(payload["timestamp"])), styles["LocalFixBody"]), Spacer(1, 8)]
    if payload["simulated"]:
        notice = Table([[Paragraph("DEMO SIMULATION · Illustrative workflow, not live device inference", styles["LocalFixBody"])]], colWidths=[170 * mm])
        notice.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf1dd")), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#ddc089")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        story.extend([notice, Spacer(1, 9)])
    metadata = [["Equipment", escape(str(payload["equipment"] or "—")), "Serial", escape(str(payload["serial_number"] or "—"))], ["Fault", escape(str(payload["observed_fault"] or "—")), "Runtime", escape(str(payload["runtime_mode"]))]]
    table = Table(metadata, colWidths=[25 * mm, 57 * mm, 25 * mm, 63 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f3eb")), ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#d6ddd0")), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([table, Paragraph("Camera and OCR observations", styles["LocalFixSection"])])
    for item in payload["camera_observations"]:
        story.append(Paragraph(f"• {escape(str(item))}", styles["LocalFixBody"]))
    if not payload["camera_observations"]:
        story.append(Paragraph("No camera/OCR observations recorded.", styles["LocalFixBody"]))
    story.extend([Paragraph("Diagnosis", styles["LocalFixSection"]), Paragraph(escape(str(payload["diagnosis"] or "Not recorded.")), styles["LocalFixBody"]), Paragraph("Procedure performed", styles["LocalFixSection"])])
    for step in payload["procedure_performed"]:
        story.append(Paragraph(f"• {escape(str(step['action']))} <font color='#74815f'>({escape(str(step['safety_level']))})</font>", styles["LocalFixBody"]))
    story.extend([Paragraph("Technician notes", styles["LocalFixSection"]), Paragraph(escape(str(payload["technician_notes"] or "No notes recorded.")), styles["LocalFixBody"]), Paragraph("Resolution", styles["LocalFixSection"]), Paragraph(escape(str(payload["resolution"] or "Not recorded.")), styles["LocalFixBody"]), Paragraph("Evidence references", styles["LocalFixSection"])])
    for item in payload["manual_references"]:
        story.append(Paragraph(f"• {escape(str(item['document']))} · {escape(str(item['section']))} · p. {escape(str(item['page']))} · source {escape(str(item['source_hash'])[:12])}", styles["LocalFixBody"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Local data · source page references preserved · safety confirmation is technician-reported.", styles["Italic"]))
    document.build(story)
    return buffer.getvalue()
