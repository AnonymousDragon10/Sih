"""
Module A - Conversational Multimodal History Engine.

Design decision (see whiteboard "hard part #2"): red-flag detection is
NOT left purely to LLM judgement. The LLM proposes a red flag; a
deterministic keyword/rule layer independently checks the same
transcript. Either one firing is enough to raise the alert. This
dual-path design trades some false positives for far fewer dangerous
false negatives, which is the right trade for a triage safety net.
"""
import re
from .llm_client import LLMClient

# --- Deterministic red-flag rules (fast, auditable, cannot be "argued out of" by the model) ---
RED_FLAG_PATTERNS = [
    (re.compile(r"chest pain", re.I), "Chest pain reported"),
    (re.compile(r"(short(ness)? of breath|breathless|difficulty breathing|dyspnea|dyspnoea)", re.I), "Breathlessness reported"),
    (re.compile(r"(sudden|acute).{0,20}(weakness|numbness|slurred speech|facial droop)", re.I), "Possible stroke symptoms"),
    (re.compile(r"(coughing|vomiting).{0,15}blood|hemoptysis|haematemesis", re.I), "Blood in cough/vomit reported"),
    (re.compile(r"(severe|worst).{0,15}headache", re.I), "Severe/thunderclap headache reported"),
    (re.compile(r"suicid|self.?harm|end my life", re.I), "Self-harm / suicidal ideation mentioned"),
    (re.compile(r"seizure|convulsion|fit(ting)?", re.I), "Seizure activity reported"),
    (re.compile(r"unconscious|fainted|loss of consciousness", re.I), "Loss of consciousness reported"),
]

SOCRATES_FIELDS = ["Site", "Onset", "Character", "Radiation", "Associations",
                    "Time course", "Exacerbating/relieving factors", "Severity"]

AYUSH_DASHAVIDHA_PARIKSHA = [
    "Prakriti", "Vikriti", "Sara", "Samhanana", "Pramana",
    "Satmya", "Sattva", "Ahara Shakti", "Vyayama Shakti", "Vaya",
]

DIALOGUE_SYSTEM_PROMPT = """You are a clinical history-taking assistant conducting a structured
patient interview, modeled on the SOCRATES framework (Site, Onset, Character, Radiation,
Associations, Time course, Exacerbating/relieving factors, Severity) for any presenting complaint.

Rules you must follow strictly:
- Ask ONE clear, simple question at a time, in plain language a non-medical person understands.
- Never suggest a diagnosis. Never say what you think is "likely" or "probably" wrong with the patient.
- After each patient answer, decide the next most clinically useful follow-up question.
- Always propose 3-4 short quick_reply_options the patient could tap instead of speaking.
- If AYUSH mode is active, also weave in Dashavidha Pariksha assessment questions
  (Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Ahara Shakti, Vyayama Shakti, Vaya)
  and Ahara-Vihara (diet/lifestyle) once the chief complaint has been explored.
- If the patient's answer suggests a possible emergency (e.g. chest pain with breathlessness,
  stroke symptoms, severe bleeding, loss of consciousness, suicidal ideation), set
  red_flag_suspected=true and explain why in red_flag_reason.

Respond as JSON with exactly these fields:
next_question, quick_reply_options (array), red_flag_suspected (bool), red_flag_reason (string or null), topic (string)
"""


class ConversationEngine:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def check_deterministic_red_flags(self, text: str) -> tuple[bool, str | None]:
        for pattern, reason in RED_FLAG_PATTERNS:
            if pattern.search(text):
                return True, reason
        return False, None

    def next_turn(self, transcript: list[dict], department: str, chief_complaint: str | None) -> dict:
        """
        transcript: list of {"role": "assistant"|"patient", "text": str}
        Returns dict matching DIALOGUE_SYSTEM_PROMPT's JSON contract, merged
        with the deterministic red-flag check (rule OR model firing = flagged).
        """
        history_text = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in transcript)
        mode_note = "\nAYUSH MODE ACTIVE: include Dashavidha Pariksha / Ahara-Vihara questions." \
            if department == "ayush" else ""

        prompt = (
            f"Chief complaint so far: {chief_complaint or 'not yet stated'}{mode_note}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            "Produce the next question."
        )
        llm_result = self.llm.chat_json(DIALOGUE_SYSTEM_PROMPT, prompt)

        last_patient_text = transcript[-1]["text"] if transcript and transcript[-1]["role"] == "patient" else ""
        rule_flag, rule_reason = self.check_deterministic_red_flags(last_patient_text)

        red_flag = bool(llm_result.get("red_flag_suspected")) or rule_flag
        reason_parts = [r for r in [llm_result.get("red_flag_reason"), rule_reason] if r]

        return {
            "next_question": llm_result.get("next_question", "Can you tell me more about your problem?"),
            "quick_reply_options": llm_result.get("quick_reply_options", []),
            "red_flag_suspected": red_flag,
            "red_flag_reason": " | ".join(dict.fromkeys(reason_parts)) if reason_parts else None,
            "topic": llm_result.get("topic", "general"),
        }

    def opening_question(self, department: str) -> dict:
        base = {
            "next_question": "What is the main problem that has brought you here today?",
            "quick_reply_options": ["Pain somewhere", "Fever", "Cough/Cold", "Something else"],
            "red_flag_suspected": False,
            "red_flag_reason": None,
            "topic": "chief_complaint",
        }
        if department == "ayush":
            base["next_question"] += " (We will also ask a few questions about your daily routine and constitution.)"
        return base
