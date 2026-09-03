import json
from fastapi import APIRouter, HTTPException
from ..models import PhysicianEditRequest
from ..db import db_cursor, new_id, now, audit
from ..llm_client import get_llm_client
from ..summary_engine import SummaryEngine
from .. import his_abdm_stub
from .. import consent as consent_module
from .converse import _get_transcript, _get_session
from .documents import list_documents

router = APIRouter(prefix="/consult", tags=["consult"])
engine = SummaryEngine(get_llm_client())


@router.post("/{session_id}/generate-summary")
def generate_summary(session_id: str):
    session = _get_session(session_id)
    transcript = _get_transcript(session_id)
    docs = list_documents(session_id)["documents"]

    summary = engine.generate(transcript, docs, ayush_mode=(session["department"] == "ayush"))

    summary_id = new_id()
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO summaries (id, session_id, summary_json, status, created_at) VALUES (?,?,?,?,?)",
            (summary_id, session_id, json.dumps(summary), "draft", now()),
        )
        cur.execute("UPDATE sessions SET status='summarized' WHERE id=?", (session_id,))
    audit(session_id, "summary_generated", {"summary_id": summary_id})
    return {"summary_id": summary_id, "status": "draft", "summary": summary,
            "red_flag": bool(session["red_flag"]), "red_flag_reason": session["red_flag_reason"]}


@router.get("/{session_id}/summary")
def get_latest_summary(session_id: str):
    with db_cursor() as cur:
        row = cur.execute(
            "SELECT * FROM summaries WHERE session_id=? ORDER BY created_at DESC LIMIT 1", (session_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "No summary generated yet.")
    return dict(row) | {"summary_json": json.loads(row["summary_json"])}


@router.post("/{session_id}/finalize")
def finalize(session_id: str, req: PhysicianEditRequest):
    """
    Physician's action on the draft. This is the ONLY endpoint that writes
    to the HIS/ABDM stub - nothing is pushed automatically. Per the
    'physician retains full control' requirement, a rejected summary is
    never pushed anywhere.
    """
    session = _get_session(session_id)
    with db_cursor() as cur:
        cur.execute(
            "UPDATE summaries SET physician_edited_json=?, status=?, finalized_at=? WHERE session_id=?",
            (json.dumps(req.edited_summary_json), req.decision, now(), session_id),
        )
    audit(session_id, "physician_decision", {"decision": req.decision})

    his_result, abha_result = None, None
    if req.decision in ("accepted", "amended"):
        consent = consent_module.get_consent(session_id) or {}
        if consent.get("share_with_his"):
            his_result = his_abdm_stub.push_to_his(session, req.edited_summary_json)
        if consent.get("link_abha"):
            abha_result = his_abdm_stub.link_abha_record(session, req.edited_summary_json)
        consent_module.purge_session_raw_data(session_id)
        with db_cursor() as cur:
            cur.execute("UPDATE sessions SET status='finalized' WHERE id=?", (session_id,))
        audit(session_id, "session_finalized_and_purged", {})

    return {"decision": req.decision, "his_result": his_result, "abha_result": abha_result}
