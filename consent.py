"""
Module D (part 1) - Consent layer.

Kept deliberately simple and explicit: three separate, granular,
revocable consent flags rather than one blanket checkbox, per the
DPDP Act 2023 "purpose limitation" and ABDM consent-artifact spirit.
This is a DEMO-FIDELITY implementation of the *pattern*, not a
certified DPDP/ABDM consent-manager integration (see his_abdm_stub.py
docstring for why that's out of scope here).
"""
from .db import db_cursor, now
import json


CONSENT_AUDIO_SCRIPT = {
    "en": "We will record your answers and any documents you share to prepare a summary for "
          "your doctor. You can decline any part, and your recording is deleted right after "
          "your summary is created. Do you agree to continue?",
    "hi": "hum aapke jawab aur dastavez doctor ke liye summary banane mein istemal karenge. "
          "Aap kisi bhi hisse ko mana kar sakte hain, aur summary banne ke baad recording turant "
          "mita di jaayegi. Kya aap aage badhna chahte hain?",
}


def record_consent(session_id: str, capture_history: bool, share_with_his: bool, link_abha: bool):
    consent_obj = {
        "capture_history": capture_history,
        "share_with_his": share_with_his,
        "link_abha": link_abha,
        "recorded_at": now(),
    }
    with db_cursor() as cur:
        cur.execute("UPDATE sessions SET consent_json=? WHERE id=?", (json.dumps(consent_obj), session_id))
    return consent_obj


def get_consent(session_id: str) -> dict | None:
    with db_cursor() as cur:
        row = cur.execute("SELECT consent_json FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row and row["consent_json"]:
        return json.loads(row["consent_json"])
    return None


def purge_session_raw_data(session_id: str):
    """
    'Session termination' requirement: once the summary is finalized and
    pushed, wipe raw transcript text and raw OCR blobs, keeping only the
    structured summary + an audit trail that it happened.
    """
    with db_cursor() as cur:
        cur.execute("UPDATE conversation_turns SET text='[purged]' WHERE session_id=?", (session_id,))
        cur.execute("UPDATE documents SET raw_ocr_text='[purged]' WHERE session_id=?", (session_id,))
