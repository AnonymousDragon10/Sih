"""
Single interface every module talks to, so swapping providers (or
swapping in Bhashini/self-hosted models later) never touches business
logic. Two implementations:

  - MockLLM:      deterministic canned responses, zero network calls.
                  Used automatically if no ANTHROPIC_API_KEY is set,
                  or if LLM_PROVIDER=mock. Lets the whole app run and
                  be demoed with no key and no internet.
  - AnthropicLLM: real calls to the Claude API (text + vision).

Both implement:
    .chat_json(system, messages, schema_hint) -> dict
    .vision_json(system, image_b64, media_type, prompt, schema_hint) -> dict
"""
import os
import json
import base64
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def chat_json(self, system: str, user_prompt: str) -> dict: ...

    @abstractmethod
    def vision_json(self, system: str, image_b64: str, media_type: str, prompt: str) -> dict: ...


def _safe_json_parse(text: str) -> dict:
    """LLMs sometimes wrap JSON in prose or code fences; strip and parse defensively."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw_text": text}


class AnthropicLLM(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def chat_json(self, system: str, user_prompt: str) -> dict:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system + "\n\nRespond with ONLY valid JSON, no prose, no markdown fences.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _safe_json_parse(text)

    def vision_json(self, system: str, image_b64: str, media_type: str, prompt: str) -> dict:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system + "\n\nRespond with ONLY valid JSON, no prose, no markdown fences.",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _safe_json_parse(text)


class MockLLM(LLMClient):
    """
    Offline stand-in. Returns plausible, schema-shaped fixtures so the
    entire product flow (UI, DB writes, physician screen) can be
    demoed and unit-tested without any network access or API key.
    """

    def chat_json(self, system: str, user_prompt: str) -> dict:
        lower = user_prompt.lower()

        # Dialogue-manager style calls ask for a "next_question" field
        if "next_question" in system or "SOCRATES" in system:
            if "chest pain" in lower:
                return {
                    "next_question": "When did the chest pain start, and does it spread to your arm, jaw, or back?",
                    "quick_reply_options": ["Started today", "Started this week", "Started weeks ago", "It spreads to my arm/jaw"],
                    "red_flag_suspected": True,
                    "red_flag_reason": "Chest pain reported - ruling out cardiac emergency (SOCRATES: onset/radiation).",
                    "topic": "HPI.chest_pain.onset_radiation",
                }
            return {
                "next_question": "Can you tell me more about when this problem started and how it has changed?",
                "quick_reply_options": ["A few hours ago", "A few days ago", "More than a week ago", "It comes and goes"],
                "red_flag_suspected": False,
                "red_flag_reason": None,
                "topic": "HPI.onset",
            }

        # Summary generation calls
        if "chief_complaint" in system or "clinical summary" in system.lower():
            return {
                "chief_complaint": "Intermittent chest discomfort for 3 days",
                "history_of_present_illness": "Patient (mock data) reports intermittent left-sided chest discomfort "
                                               "for 3 days, non-radiating per latest answer, no associated "
                                               "diaphoresis reported. Aggravated by exertion, relieved by rest.",
                "past_medical_surgical_history": "No known prior surgeries reported. Hypertension reported 2 years ago.",
                "drug_allergy_history": "On Amlodipine 5mg OD (per uploaded prescription). No known drug allergies reported.",
                "family_history": "Father: hypertension. No reported family history of premature cardiac disease.",
                "personal_history": "Non-smoker, occasional alcohol use reported.",
                "review_of_systems": "No reported fever, cough, breathlessness at rest, or GI symptoms.",
                "ayush_parameters": None,
                "prior_investigations_summary": "Lipid profile (uploaded, 2024-01-10): LDL 162 mg/dL (HIGH, ref <130).",
                "ai_confidence_note": "Draft generated from conversation + 1 document. Physician review required before use.",
            }

        return {"result": "mock_response", "note": "Configure ANTHROPIC_API_KEY and LLM_PROVIDER=anthropic for real output."}

    def vision_json(self, system: str, image_b64: str, media_type: str, prompt: str) -> dict:
        return {
            "doc_type_guess": "prescription",
            "raw_ocr_text": "[MOCK OCR] Dr. R. Sharma\nDx: Hypertension\nRx: Tab Amlodipine 5mg OD x 30 days\nAdvice: Low salt diet, follow up 4 weeks",
            "diagnoses": ["Hypertension"],
            "medications": [
                {"name": "Amlodipine", "dose": "5mg", "frequency": "OD", "duration": "30 days", "confidence": 0.62}
            ],
            "investigations": [],
            "document_date_guess": "2024-01-10",
            "low_confidence_fields": ["medications[0].dose"],
            "note": "This is MOCK vision output (no image was actually analyzed). "
                    "Set ANTHROPIC_API_KEY + LLM_PROVIDER=anthropic for real OCR/extraction.",
        }


def get_llm_client() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "mock").lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if provider == "anthropic" and api_key:
        return AnthropicLLM(api_key=api_key)
    return MockLLM()
