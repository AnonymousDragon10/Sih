from pydantic import BaseModel, Field
from typing import Optional, Literal


class IdentifyRequest(BaseModel):
    patient_name: str
    age: int
    sex: Literal["male", "female", "other"]
    preferred_language: str = Field(description="e.g. hi, en, bn, ta, te, mr")
    department: Literal["allopathic", "ayush"] = "allopathic"
    abha_id: Optional[str] = None  # mocked; blank => "register as new"


class ConsentRequest(BaseModel):
    session_id: str
    consent_capture_history: bool
    consent_share_with_his: bool
    consent_link_abha: bool


class ConverseTurnRequest(BaseModel):
    session_id: str
    input_mode: Literal["voice", "touch"]
    text: str  # for voice: ASR transcript from the client; for touch: selected option text


class DocumentUploadMeta(BaseModel):
    session_id: str
    doc_type: Literal["prescription", "lab_report", "discharge_summary", "other"] = "other"


class PhysicianEditRequest(BaseModel):
    session_id: str
    edited_summary_json: dict
    decision: Literal["accepted", "amended", "rejected"]
