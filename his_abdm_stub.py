"""
Module D (part 2) - HIS / ABDM integration.

WHY THIS IS A STUB, HONESTLY:
Real ABDM integration requires: NHA sandbox onboarding, HFR (Health
Facility Registry) + HPR (Health Professional Registry) registration,
X.509 cert exchange for signed FHIR bundles, and a live ABHA
consent-manager callback flow. None of that can exist without an
actual registered facility and NHA credentials - it is a compliance
and partnership process, not a coding task.

What this stub gives you instead: the CORRECT integration seam.
push_to_his() and link_abha_record() are the exact two calls a real
integration would need, with the exact shape of data a FHIR Bundle /
HIS API would expect. Swapping the mocked bodies for real HTTP calls
to your hospital's actual HIS + the NHA's real ABDM gateway is then a
scoped, well-defined integration task rather than a redesign.
"""
from .db import db_cursor, now, new_id, audit


def build_fhir_like_bundle(session: dict, summary: dict) -> dict:
    """Minimal FHIR-Bundle-shaped payload (not a validated FHIR resource -
    a real integration would use a proper FHIR library, e.g. fhir.resources)."""
    return {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [
            {
                "resourceType": "Patient",
                "name": session["patient_name"],
                "age": session["age"],
                "sex": session["sex"],
                "abhaId": session.get("abha_id"),
            },
            {
                "resourceType": "Composition",
                "title": "AI-Assisted Pre-Consultation History Summary (MediKiosk)",
                "section": summary,
                "status": "preliminary",
                "note": "Draft generated pre-consultation; requires physician review per module design.",
            },
        ],
    }


def push_to_his(session: dict, summary: dict) -> dict:
    """Mock POST to hospital HIS/EMR. Logs the attempt and returns a fake ack."""
    bundle = build_fhir_like_bundle(session, summary)
    fake_his_reference_id = f"HIS-{new_id()[:8].upper()}"
    audit(session["id"], "push_to_his", {"his_reference_id": fake_his_reference_id, "bundle_size": len(str(bundle))})
    return {"status": "ok (mocked)", "his_reference_id": fake_his_reference_id}


def link_abha_record(session: dict, summary: dict) -> dict:
    """Mock call to ABDM Health Information Exchange to link this encounter to the patient's PHR."""
    if not session.get("abha_id"):
        return {"status": "skipped", "reason": "No ABHA ID on this session (patient registered as new/without ABHA)."}
    fake_hie_txn_id = f"HIE-{new_id()[:8].upper()}"
    audit(session["id"], "link_abha", {"abha_id": session["abha_id"], "hie_txn_id": fake_hie_txn_id})
    return {"status": "ok (mocked)", "hie_txn_id": fake_hie_txn_id}
