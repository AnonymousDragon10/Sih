const API_BASE = "http://localhost:8000";

const FIELDS = [
  ["chief_complaint", "Chief Complaint"],
  ["history_of_present_illness", "History of Present Illness (HPI)"],
  ["past_medical_surgical_history", "Past Medical / Surgical History"],
  ["drug_allergy_history", "Drug & Allergy History"],
  ["family_history", "Family History"],
  ["personal_history", "Personal History"],
  ["review_of_systems", "Review of Systems"],
  ["prior_investigations_summary", "Prior Investigations Summary"],
];

let currentSessionId = null;

document.getElementById("btn-load").addEventListener("click", loadSummary);

async function loadSummary() {
  currentSessionId = document.getElementById("in-session-id").value.trim();
  if (!currentSessionId) return alert("Paste a session ID from the kiosk first.");

  // generate-summary is idempotent-ish for the demo (re-generates on request);
  // in the real flow the kiosk already triggers this at the end of Step 3.
  const sumRes = await fetch(`${API_BASE}/consult/${currentSessionId}/generate-summary`, { method: "POST" });
  if (!sumRes.ok) { alert("Could not load this session. Has the patient finished the kiosk flow?"); return; }
  const data = await sumRes.json();

  const banner = document.getElementById("red-flag-note");
  if (data.red_flag) {
    banner.classList.remove("hidden");
    banner.innerText = `⚠ RED FLAG raised during intake: ${data.red_flag_reason}`;
  } else {
    banner.classList.add("hidden");
  }

  renderSummary(data.summary);
  document.getElementById("action-row").style.display = "flex";
}

function renderSummary(summary) {
  const container = document.getElementById("summary-container");
  container.innerHTML = "";
  FIELDS.forEach(([key, label]) => {
    const section = document.createElement("div");
    section.className = "summary-section";
    section.innerHTML = `<h3>${label}</h3><textarea data-key="${key}">${summary[key] || ""}</textarea>`;
    container.appendChild(section);
  });

  if (summary.ayush_parameters) {
    const section = document.createElement("div");
    section.className = "summary-section";
    section.innerHTML = `<h3>AYUSH — Dashavidha Pariksha</h3>
      <textarea data-key="ayush_parameters">${JSON.stringify(summary.ayush_parameters, null, 2)}</textarea>`;
    container.appendChild(section);
  }

  const note = document.createElement("p");
  note.style.fontSize = ".85rem";
  note.style.color = "#7a8a9a";
  note.innerText = summary.ai_confidence_note || "";
  container.appendChild(note);
}

function collectEditedSummary() {
  const edited = {};
  document.querySelectorAll("#summary-container textarea").forEach(ta => {
    edited[ta.dataset.key] = ta.value;
  });
  return edited;
}

async function decide(decision) {
  const edited = collectEditedSummary();
  const res = await fetch(`${API_BASE}/consult/${currentSessionId}/finalize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: currentSessionId, edited_summary_json: edited, decision }),
  });
  const data = await res.json();
  const note = document.getElementById("result-note");
  if (decision === "rejected") {
    note.innerHTML = `<strong>Draft rejected.</strong> Nothing was pushed to HIS/ABDM.`;
  } else {
    note.innerHTML = `<strong>Decision: ${decision}.</strong>
      HIS push: ${JSON.stringify(data.his_result)}<br/>
      ABHA link: ${JSON.stringify(data.abha_result)}`;
  }
}

document.getElementById("btn-accept").addEventListener("click", () => decide("accepted"));
document.getElementById("btn-amend").addEventListener("click", () => decide("amended"));
document.getElementById("btn-reject").addEventListener("click", () => decide("rejected"));
