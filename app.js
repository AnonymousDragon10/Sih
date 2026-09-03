// MediKiosk patient-facing kiosk logic.
// Voice: uses the browser's built-in Web Speech API (SpeechRecognition / speechSynthesis)
// as the ASR/TTS SWAP POINT for the demo. In a real deployment this call is replaced by
// Bhashini/AI4Bharat ASR + TTS models (see README "Swapping in real ASR/TTS").

const API_BASE = "http://localhost:8000";

const state = {
  sessionId: null,
  language: "en",
  department: "allopathic",
};

// ---------- screen navigation ----------
function showScreen(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

document.querySelectorAll(".lang-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");
    state.language = btn.dataset.lang;
  });
});

document.getElementById("btn-start").addEventListener("click", () => showScreen("screen-identify"));

// ---------- Step 1: Identify ----------
document.getElementById("form-identify").addEventListener("submit", async (e) => {
  e.preventDefault();
  state.department = document.getElementById("in-department").value;
  const payload = {
    patient_name: document.getElementById("in-name").value,
    age: parseInt(document.getElementById("in-age").value, 10),
    sex: document.getElementById("in-sex").value,
    preferred_language: state.language,
    department: state.department,
    abha_id: document.getElementById("in-abha").value || null,
  };
  const res = await fetch(`${API_BASE}/identify`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  const data = await res.json();
  state.sessionId = data.session_id;
  showScreen("screen-consent");
});

// ---------- Step 1b: Consent ----------
document.getElementById("btn-play-audio").addEventListener("click", () => {
  const text = document.getElementById("consent-audio-text").innerText;
  speak(text);
});

document.getElementById("btn-consent-continue").addEventListener("click", async () => {
  const payload = {
    session_id: state.sessionId,
    consent_capture_history: document.getElementById("c-capture").checked,
    consent_share_with_his: document.getElementById("c-his").checked,
    consent_link_abha: document.getElementById("c-abha").checked,
  };
  await fetch(`${API_BASE}/identify/consent`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  showScreen("screen-converse");
  startConversation();
});

// ---------- Step 2: Converse ----------
const chatWindow = document.getElementById("chat-window");
const quickReplies = document.getElementById("quick-replies");

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerText = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderQuickReplies(options) {
  quickReplies.innerHTML = "";
  (options || []).forEach(opt => {
    const btn = document.createElement("button");
    btn.innerText = opt;
    btn.addEventListener("click", () => sendAnswer(opt, "touch"));
    quickReplies.appendChild(btn);
  });
}

function handleRedFlag(flagged, reason) {
  const banner = document.getElementById("red-flag-banner");
  if (flagged) {
    banner.classList.remove("hidden");
    banner.innerText = `⚠ ${reason || "Urgent symptom detected"} — please inform staff immediately.`;
  }
}

async function startConversation() {
  const res = await fetch(`${API_BASE}/converse/start/${state.sessionId}`, { method: "POST" });
  const data = await res.json();
  addMessage("assistant", data.next_question);
  renderQuickReplies(data.quick_reply_options);
  speak(data.next_question);
}

async function sendAnswer(text, mode) {
  if (!text) return;
  addMessage("patient", text);
  document.getElementById("in-answer").value = "";
  quickReplies.innerHTML = "";

  const res = await fetch(`${API_BASE}/converse/turn`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: state.sessionId, input_mode: mode, text }),
  });
  const data = await res.json();
  addMessage("assistant", data.next_question);
  renderQuickReplies(data.quick_reply_options);
  handleRedFlag(data.red_flag_suspected, data.red_flag_reason);
  speak(data.next_question);
}

document.getElementById("btn-send").addEventListener("click", () => {
  sendAnswer(document.getElementById("in-answer").value.trim(), "touch");
});
document.getElementById("in-answer").addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendAnswer(document.getElementById("in-answer").value.trim(), "touch");
});

document.getElementById("btn-converse-done").addEventListener("click", async () => {
  await fetch(`${API_BASE}/converse/finish/${state.sessionId}`, { method: "POST" });
  showScreen("screen-scan");
});

// ---- Voice input (Web Speech API — swap point for Bhashini ASR in production) ----
const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
const micBtn = document.getElementById("btn-mic");

if (SpeechRecognitionImpl) {
  recognizer = new SpeechRecognitionImpl();
  recognizer.continuous = false;
  recognizer.interimResults = false;

  micBtn.addEventListener("click", () => {
    recognizer.lang = languageToBCP47(state.language);
    micBtn.classList.add("recording");
    recognizer.start();
  });
  recognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    sendAnswer(transcript, "voice");
  };
  recognizer.onend = () => micBtn.classList.remove("recording");
  recognizer.onerror = () => micBtn.classList.remove("recording");
} else {
  micBtn.addEventListener("click", () => alert("Voice input isn't supported in this browser. Please type your answer."));
}

function languageToBCP47(lang) {
  return { en: "en-IN", hi: "hi-IN", bn: "bn-IN", ta: "ta-IN" }[lang] || "en-IN";
}

function speak(text) {
  if (!window.speechSynthesis) return;
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = languageToBCP47(state.language);
  window.speechSynthesis.speak(utter);
}

// ---------- Step 3: Scan documents ----------
document.getElementById("btn-upload").addEventListener("click", async () => {
  const fileInput = document.getElementById("in-file");
  if (!fileInput.files.length) { alert("Please choose a photo first."); return; }

  const formData = new FormData();
  formData.append("session_id", state.sessionId);
  formData.append("doc_type", document.getElementById("in-doctype").value);
  formData.append("file", fileInput.files[0]);

  const res = await fetch(`${API_BASE}/documents/upload`, { method: "POST", body: formData });
  const data = await res.json();
  renderDocCard(data);
  fileInput.value = "";
});

function renderDocCard(doc) {
  const card = document.createElement("div");
  card.className = "doc-card";
  const lowConf = doc.low_confidence_fields || [];
  card.innerHTML = `
    <strong>${doc.doc_type_guess || "document"}</strong> (dated ${doc.document_date_guess || "unknown"})<br/>
    Diagnoses: ${(doc.diagnoses || []).join(", ") || "none detected"}<br/>
    Medications: ${(doc.medications || []).map(m => `${m.name} ${m.dose} ${m.frequency}`).join("; ") || "none detected"}<br/>
    ${lowConf.length ? `<span class="low-conf">⚠ Please show this document to the doctor — ${lowConf.length} field(s) need verification.</span>` : ""}
  `;
  document.getElementById("doc-list").appendChild(card);
}

document.getElementById("btn-scan-done").addEventListener("click", async () => {
  await fetch(`${API_BASE}/consult/${state.sessionId}/generate-summary`, { method: "POST" });
  document.getElementById("final-session-id").innerText = state.sessionId;
  showScreen("screen-done");
});

document.getElementById("btn-restart").addEventListener("click", () => window.location.reload());
