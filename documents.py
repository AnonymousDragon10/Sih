import base64
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from ..db import db_cursor, new_id, now, audit
from ..llm_client import get_llm_client
from ..document_engine import DocumentEngine

router = APIRouter(prefix="/documents", tags=["documents"])
engine = DocumentEngine(get_llm_client())

ALLOWED_TYPES = {"image/jpeg": "image/jpeg", "image/png": "image/png", "image/webp": "image/webp"}


@router.post("/upload")
async def upload_document(
    session_id: str = Form(...),
    doc_type: str = Form("other"),
    file: UploadFile = File(...),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type {file.content_type}. Upload a JPEG/PNG/WEBP photo of the document.")

    raw_bytes = await file.read()
    if len(raw_bytes) > 8 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 8MB for the demo).")

    image_b64 = base64.b64encode(raw_bytes).decode("utf-8")
    result = engine.digitize(image_b64, ALLOWED_TYPES[file.content_type])
    result["investigations"] = DocumentEngine.flag_abnormal_investigations(result.get("investigations", []))

    doc_id = new_id()
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO documents
               (id, session_id, filename, doc_type, raw_ocr_text, extracted_json, low_confidence_fields, uploaded_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (doc_id, session_id, file.filename, result.get("doc_type_guess", doc_type),
             result.get("raw_ocr_text", ""), json.dumps(result), json.dumps(result.get("low_confidence_fields", [])),
             now()),
        )
    audit(session_id, "document_uploaded", {
        "doc_id": doc_id, "doc_type": result.get("doc_type_guess"),
        "low_confidence_field_count": len(result.get("low_confidence_fields", [])),
    })
    return {"document_id": doc_id, **result}


@router.get("/{session_id}")
def list_documents(session_id: str):
    with db_cursor() as cur:
        rows = cur.execute(
            "SELECT id, filename, doc_type, extracted_json, low_confidence_fields, uploaded_at "
            "FROM documents WHERE session_id=?",
            (session_id,),
        ).fetchall()
    docs = []
    for r in rows:
        d = json.loads(r["extracted_json"])
        d["document_id"] = r["id"]
        d["filename"] = r["filename"]
        docs.append(d)
    return {"documents": docs}
