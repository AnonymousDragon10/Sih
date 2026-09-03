from fastapi import APIRouter, HTTPException
from ..models import IdentifyRequest, ConsentRequest
from ..db import db_cursor, new_id, now, audit
from .. import consent as consent_module

router = APIRouter(prefix="/identify", tags=["identify"])


@router.post("")
def identify(req: IdentifyRequest):
    session_id = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO sessions
               (id, created_at, status, patient_name, age, sex, preferred_language, department, abha_id)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (session_id, now(), "identify", req.patient_name, req.age, req.sex,
             req.preferred_language, req.department, req.abha_id),
        )
    audit(session_id, "session_created", {"department": req.department, "has_abha": bool(req.abha_id)})
    return {"session_id": session_id, "message": "Session created. Please record consent next."}


@router.post("/consent")
def consent(req: ConsentRequest):
    if not req.consent_capture_history:
        raise HTTPException(400, "Cannot proceed without consent to capture history.")
    consent_obj = consent_module.record_consent(
        req.session_id, req.consent_capture_history, req.consent_share_with_his, req.consent_link_abha
    )
    with db_cursor() as cur:
        cur.execute("UPDATE sessions SET status='converse' WHERE id=?", (req.session_id,))
    audit(req.session_id, "consent_recorded", consent_obj)
    return {"status": "ok", "consent": consent_obj}


@router.get("/{session_id}")
def get_session(session_id: str):
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return dict(row)
