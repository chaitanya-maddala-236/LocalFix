from __future__ import annotations

import json
import uuid
from typing import Any

from ..database import connect, now_iso
from ..schemas import CaseCreate, CaseResponse, Evidence


def _case_details(connection: Any, case_row: Any) -> dict[str, Any]:
    case_id = case_row["case_id"]
    evidence_rows = connection.execute("SELECT * FROM case_evidence WHERE case_id=? ORDER BY page", (case_id,)).fetchall()
    step_rows = connection.execute("SELECT * FROM case_steps WHERE case_id=? ORDER BY step_index", (case_id,)).fetchall()
    evidence = [Evidence(
        id=row["evidence_id"], document_id=row["document_id"] or "", document_name=row["document_name"] or "",
        page=row["page"] or 0, section=row["section"] or "", equipment_model=case_row["equipment_model"],
        text=row["text"] or "", retrieval_score=row["score"] or 0, source_hash=row["source_hash"] or "",
    ).model_dump() for row in evidence_rows]
    steps = [{"index": row["step_index"], "action": row["action"], "safety_level": row["safety_level"],
              "completed": bool(row["completed"]), "source_document_id": row["source_document_id"],
              "source_page": row["source_page"]} for row in step_rows]
    return {
        "case_id": case_id, "equipment_model": case_row["equipment_model"], "serial_number": case_row["serial_number"],
        "fault_code": case_row["fault_code"], "diagnosis": case_row["diagnosis"], "status": case_row["status"],
        "technician": case_row["technician"], "notes": case_row["notes"], "resolution": case_row["resolution"],
        "created_at": case_row["created_at"], "updated_at": case_row["updated_at"],
        "observations": json.loads(case_row["observations"] or "[]"),
        "evidence": evidence, "steps": steps, "simulated": bool(case_row["simulated"]),
    }


def create_case(payload: CaseCreate) -> CaseResponse:
    case_id = f"case_{uuid.uuid4().hex[:10]}"
    timestamp = now_iso()
    with connect() as connection:
        connection.execute(
            "INSERT INTO cases (case_id,equipment_model,serial_number,fault_code,diagnosis,status,technician,notes,resolution,created_at,updated_at,simulated,observations) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (case_id, payload.equipment_model, payload.serial_number, payload.fault_code, payload.diagnosis,
             payload.status, payload.technician, payload.notes, payload.resolution, timestamp, timestamp,
             int(payload.simulated), json.dumps(payload.observations, ensure_ascii=False)),
        )
        for item in payload.evidence:
            connection.execute(
                "INSERT OR IGNORE INTO case_evidence VALUES (?,?,?,?,?,?,?,?,?)",
                (case_id, item.id, item.document_id, item.document_name, item.page, item.section, item.text,
                 item.retrieval_score, item.source_hash),
            )
        for step in payload.steps:
            connection.execute(
                "INSERT INTO case_steps VALUES (?,?,?,?,?,?,?)",
                (case_id, step.index, step.action, step.safety_level, int(step.completed), step.source_document_id, step.source_page),
            )
        row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        return CaseResponse(**_case_details(connection, row))


def list_cases(query: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[CaseResponse], int]:
    with connect() as connection:
        if query:
            term = f"%{query.strip()}%"
            total = connection.execute("SELECT COUNT(*) FROM cases WHERE case_id LIKE ? OR equipment_model LIKE ? OR fault_code LIKE ? OR diagnosis LIKE ?", (term, term, term, term)).fetchone()[0]
            rows = connection.execute("SELECT * FROM cases WHERE case_id LIKE ? OR equipment_model LIKE ? OR fault_code LIKE ? OR diagnosis LIKE ? ORDER BY updated_at DESC LIMIT ? OFFSET ?", (term, term, term, term, limit, offset)).fetchall()
        else:
            total = connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            rows = connection.execute("SELECT * FROM cases ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [CaseResponse(**_case_details(connection, row)) for row in rows], int(total)


def get_case(case_id: str) -> CaseResponse | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            return None
        return CaseResponse(**_case_details(connection, row))
