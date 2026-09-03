"""
Module B - Medical Document Digitization & Intelligence.

Implements Approach B from the whiteboard comparison: a single
multimodal (vision) LLM call reads the document image directly and
returns structured clinical entities, rather than a two-stage
OCR-engine -> separate-NER pipeline (Approach A).

Mitigation for Approach B's main weakness (hallucination risk on
illegible handwriting): the model is required to return (1) its raw
perceived text alongside the structured fields, so a human can always
cross-check, and (2) a list of low_confidence_fields that the
physician UI renders with a visible "please verify" flag rather than
silently trusting them.
"""
from .llm_client import LLMClient

DOCUMENT_SYSTEM_PROMPT = """You are a medical document digitization assistant. You will be shown an
image of a patient's prior medical document (prescription, lab report, or discharge summary),
which may be handwritten or printed, and may be in English, Hindi, or another Indian language.

Extract structured clinical information. Be conservative: if a field is illegible or ambiguous,
still make your best-guess value but ALSO add its field path to low_confidence_fields so a
physician knows to double check it. NEVER invent a medication or value that has no basis in the
image - if you cannot tell what a field says at all, use null instead of guessing wildly.

Respond as JSON with exactly these fields:
doc_type_guess (prescription|lab_report|discharge_summary|other),
raw_ocr_text (your best full transcription of visible text),
diagnoses (array of strings),
medications (array of {name, dose, frequency, duration, confidence 0-1}),
investigations (array of {test_name, value, unit, reference_range, abnormal (bool)}),
document_date_guess (string or null),
low_confidence_fields (array of field-path strings, e.g. "medications[0].dose")
"""


class DocumentEngine:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def digitize(self, image_b64: str, media_type: str) -> dict:
        result = self.llm.vision_json(
            system=DOCUMENT_SYSTEM_PROMPT,
            image_b64=image_b64,
            media_type=media_type,
            prompt="Digitize this medical document image per the schema.",
        )
        # Defensive defaults so downstream code never KeyErrors on a partial LLM response
        result.setdefault("doc_type_guess", "other")
        result.setdefault("raw_ocr_text", "")
        result.setdefault("diagnoses", [])
        result.setdefault("medications", [])
        result.setdefault("investigations", [])
        result.setdefault("document_date_guess", None)
        result.setdefault("low_confidence_fields", [])
        return result

    @staticmethod
    def flag_abnormal_investigations(investigations: list[dict]) -> list[dict]:
        """Cheap, explicit re-check on top of the model's own 'abnormal' flag:
        if value/reference_range are both parseable numbers, verify range ourselves."""
        flagged = []
        for inv in investigations:
            is_abnormal = inv.get("abnormal", False)
            try:
                val = float(str(inv.get("value", "")).split()[0])
                ref = inv.get("reference_range", "")
                if "-" in ref:
                    lo, hi = [float(x) for x in ref.replace(" ", "").split("-")[:2]]
                    is_abnormal = is_abnormal or not (lo <= val <= hi)
            except (ValueError, IndexError):
                pass
            inv["abnormal"] = is_abnormal
            flagged.append(inv)
        return flagged
