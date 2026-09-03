"""
Module C - Structured History Summary Generator.

Synthesizes the full conversation transcript + all digitized documents
into one standard-format clinical note. This engine is explicitly
instructed to never produce a diagnosis or treatment recommendation -
it restates and organizes what was said/found, nothing more. The
output is always labeled a draft; only a physician action
(accept/amend/reject in consult.py) finalizes it.
"""
from .llm_client import LLMClient

SUMMARY_SYSTEM_PROMPT = """You are a clinical summary assistant. You will be given a full patient
interview transcript and structured data extracted from the patient's prior medical documents.
Produce a concise, standard-format clinical history summary for a physician to read in seconds.

CRITICAL RULES:
- Do NOT state or imply a diagnosis. Do NOT recommend treatment. You are organizing what was
  already said/found, not interpreting it clinically.
- Use neutral, clinical, third-person language ("Patient reports...", not "Patient has...").
- If information for a section was not discussed, write "Not elicited" rather than guessing.
- If ayush_mode is true, populate ayush_parameters; otherwise set it to null.

Respond as JSON with exactly these fields:
chief_complaint, history_of_present_illness, past_medical_surgical_history, drug_allergy_history,
family_history, personal_history, review_of_systems, ayush_parameters (object or null),
prior_investigations_summary, ai_confidence_note
"""


class SummaryEngine:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(self, transcript: list[dict], documents: list[dict], ayush_mode: bool) -> dict:
        transcript_text = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
        docs_text = "\n\n".join(
            f"Document ({d.get('doc_type', 'other')}, dated {d.get('document_date_guess', 'unknown')}):\n"
            f"Diagnoses: {d.get('diagnoses', [])}\n"
            f"Medications: {d.get('medications', [])}\n"
            f"Investigations: {d.get('investigations', [])}"
            for d in documents
        )
        prompt = (
            f"ayush_mode: {ayush_mode}\n\n"
            f"=== INTERVIEW TRANSCRIPT ===\n{transcript_text or 'No conversation recorded.'}\n\n"
            f"=== DIGITIZED PRIOR DOCUMENTS ===\n{docs_text or 'No documents uploaded.'}\n\n"
            "Produce the structured summary."
        )
        result = self.llm.chat_json("clinical summary " + SUMMARY_SYSTEM_PROMPT, prompt)
        for field in ["chief_complaint", "history_of_present_illness", "past_medical_surgical_history",
                      "drug_allergy_history", "family_history", "personal_history", "review_of_systems",
                      "prior_investigations_summary"]:
            result.setdefault(field, "Not elicited")
        result.setdefault("ayush_parameters", None)
        result.setdefault("ai_confidence_note",
                           "AI-generated draft. Must be reviewed, edited, and confirmed by the treating physician "
                           "before it becomes part of the medical record.")
        return result
