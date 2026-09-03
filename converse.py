from fastapi import APIRouter, HTTPException
from ..models import ConverseTurnRequest
from ..db import db_cursor, new_id, now, audit
from ..llm_client import get_llm_client
from ..conversation_engine import ConversationEngine

router = APIRouter(prefix="/converse", tags=["converse"])
engine = ConversationEngine(get_llm_client())


def _get_session(session_id: str) -> dict:
    with db_cursor() as cur:
        row = cur.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return dict(row)


def _get_transcript(session_id: str) -> list[dict]:
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT role, text FROM conversation_turns WHERE session_id=? ORDER BY turn_index ASC",
            (session_id,),
        ).fetchall()
    return [{"role": r["role"], "text": r["text"]} for r in rows]


def _save_turn(session_id: str, role: str, text: str, input_mode: str = "system"):
    with db_cursor() as cur:
        count = cur.execute(
            "SELECT COUNT(*) c FROM conversation_turns WHERE session_id=?", (session_id,)
        ).fetchone()["c"]
        cur.execute(
            """INSERT INTO conversation_turns (id, session_id, turn_index, role, input_mode, text, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (new_id(), session_id, count, role, input_mode, text, now()),
        )


@router.post("/start/{session_id}")
def start_conversation(session_id: str):
    session = _get_session(session_id)
    opening = engine.opening_question(session["department"])
    _save_turn(session_id, "assistant", opening["next_question"])
    return opening


@router.post("/turn")
def submit_turn(req: ConverseTurnRequest):
    session = _get_session(req.session_id)
    _save_turn(req.session_id, "patient", req.text, req.input_mode)

    transcript = _get_transcript(req.session_id)
    chief_complaint = transcript[0]["text"] if len(transcript) >= 2 else None

    result = engine.next_turn(transcript, session["department"], chief_complaint)
    _save_turn(req.session_id, "assistant", result["next_question"])

    if result["red_flag_suspected"]:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE sessions SET red_flag=1, red_flag_reason=? WHERE id=?",
                (result["red_flag_reason"], req.session_id),
            )
        audit(req.session_id, "red_flag_raised", {"reason": result["red_flag_reason"]})

    return result


@router.post("/finish/{session_id}")
def finish_conversation(session_id: str):
    with db_cursor() as cur:
        cur.execute("UPDATE sessions SET status='scan' WHERE id=?", (session_id,))
    transcript = _get_transcript(session_id)
    return {"status": "ok", "turn_count": len(transcript), "next_step": "document upload"}


@router.get("/transcript/{session_id}")
def get_transcript(session_id: str):
    return {"transcript": _get_transcript(session_id)}
