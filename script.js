// ===================== NAVIGATION =====================
const titles = {
  identify: ["Identify Patient", "Scan your ABHA ID or register in seconds"],
  converse: ["Converse", "AI-guided history taking, in your own words"],
  scan: ["Scan Documents", "Digitize prescriptions, labs and discharge summaries"],
  summary: ["Summary", "One structured history, ready for the physician"],
  consult: ["Consult", "The physician's view at the moment of consultation"],
};

document.querySelectorAll(".menu-item").forEach(btn => {
  btn.addEventListener("click", () => showScreen(btn.dataset.screen));
});

function showScreen(name){
  document.querySelectorAll(".menu-item").forEach(b => b.classList.toggle("active", b.dataset.screen === name));
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(`screen-${name}`).classList.add("active");
  document.getElementById("screenTitle").textContent = titles[name][0];
  document.getElementById("screenSub").textContent = titles[name][1];
  if(name === "summary") buildSummary();
  if(name === "consult") buildConsult();
}

// ===================== BOTTLE BUFFER =====================
const liquidRect = document.getElementById("liquidRect");
const bufferPercent = document.getElementById("bufferPercent");
const BOTTLE_TOP = 40, BOTTLE_BOTTOM = 250; // svg y-range of fillable body

function setBuffer(pct){
  pct = Math.max(0, Math.min(100, pct));
  const h = (pct/100) * (BOTTLE_BOTTOM - BOTTLE_TOP);
  liquidRect.setAttribute("y", BOTTLE_BOTTOM - h);
  liquidRect.setAttribute("height", h);
  bufferPercent.textContent = Math.round(pct) + "%";
}

function animateBuffer(durationMs, onDone){
  const start = performance.now();
  function tick(now){
    const t = Math.min(1, (now - start) / durationMs);
    setBuffer(t * 100);
    if(t < 1) requestAnimationFrame(tick);
    else if(onDone) onDone();
  }
  requestAnimationFrame(tick);
}

document.getElementById("btnIdentify").addEventListener("click", () => {
  setBuffer(0);
  animateBuffer(2200, () => {
    setTimeout(() => showScreen("converse"), 400);
  });
});

// ===================== CONVERSE (SOCRATES demo flow) =====================
const chatWindow = document.getElementById("chatWindow");
const chipRow = document.getElementById("chipRow");
const chatInput = document.getElementById("chatInput");
const historyList = document.getElementById("historyList");
const redFlag = document.getElementById("redFlag");

const flow = [
  { key:"complaint", bot:"What's bothering you today? You can speak or type freely.", chips:["Chest pain","Fever","Stomach ache","Headache"] },
  { key:"onset", bot:"Got it. When did this start?", chips:["A few hours ago","Since yesterday","2-3 days","Over a week"] },
  { key:"character", bot:"How would you describe it?", chips:["Sharp / stabbing","Dull / aching","Burning","Cramping"] },
  { key:"radiation", bot:"Does it spread anywhere else, like your arm, jaw or back?", chips:["No, stays in one place","Spreads to arm","Spreads to back","Not sure"] },
  { key:"severity", bot:"On a scale of 1 to 10, how severe is it right now?", chips:["Mild (2-3)","Moderate (5-6)","Severe (8-9)"] },
  { key:"ayush", bot:"For our Ayurvedic OPD: how would you describe your natural body constitution (Prakriti)?", chips:["Vata (light, quick)","Pitta (warm, sharp)","Kapha (steady, heavy)","Not sure"] },
];
let step = 0;

function addMsg(text, who){
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderChips(list){
  chipRow.innerHTML = "";
  list.forEach(label => {
    const c = document.createElement("button");
    c.className = "chip";
    c.textContent = label;
    c.addEventListener("click", () => handleAnswer(label));
    chipRow.appendChild(c);
  });
}

function fillHistory(key, value){
  const li = historyList.querySelector(`li[data-key="${key}"] .hv`);
  if(li){ li.textContent = value; li.closest("li").classList.add("filled"); }
}

function checkRedFlag(text){
  const t = text.toLowerCase();
  if(t.includes("chest pain") || t.includes("spreads to arm") || t.includes("severe")){
    redFlag.hidden = false;
  }
}

function askNext(){
  if(step >= flow.length){
    chipRow.innerHTML = "";
    addMsg("Thank you — your history is complete. You can review the live draft on the right, then move to Scan Docs.", "bot");
    return;
  }
  const q = flow[step];
  addMsg(q.bot, "bot");
  renderChips(q.chips);
}

function handleAnswer(text){
  addMsg(text, "user");
  const key = flow[step].key;
  fillHistory(key, text);
  checkRedFlag(text);
  step++;
  setTimeout(askNext, 550);
}

document.getElementById("chatSend").addEventListener("click", sendTyped);
chatInput.addEventListener("keydown", e => { if(e.key === "Enter") sendTyped(); });
function sendTyped(){
  const val = chatInput.value.trim();
  if(!val) return;
  handleAnswer(val);
  chatInput.value = "";
}

const micBtn = document.getElementById("micBtn");
micBtn.addEventListener("click", () => {
  micBtn.classList.add("listening");
  setTimeout(() => {
    micBtn.classList.remove("listening");
    if(flow[step]) handleAnswer(flow[step].chips[0]);
  }, 1400);
});

askNext(); // kick off conversation on load

// ===================== SCAN DOCS =====================
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const uploadList = document.getElementById("uploadList");
const timeline = document.getElementById("timeline");
let docsExtracted = [];

dropzone.addEventListener("click", () => fileInput.click());
["dragover","dragenter"].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave","drop"].forEach(evt => dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", e => handleFiles(e.dataTransfer.files));
fileInput.addEventListener("change", e => handleFiles(e.target.files));

const mockExtracts = [
  { title:"Prescription — 12 Jun 2025", body:"Metformin 500mg BD, Amlodipine 5mg OD. Dr. R. Sen, City Hospital." },
  { title:"Lab report — CBC, 03 Jan 2026", body:"Hemoglobin 10.8 g/dL (low). WBC normal.", flag:true },
  { title:"Discharge summary — 20 Feb 2025", body:"Admitted for viral fever, 3 days. Discharged stable." },
];

function handleFiles(files){
  Array.from(files).forEach((file, i) => {
    const item = document.createElement("div");
    item.className = "upload-item";
    item.innerHTML = `<span>${file.name || "Scanned document"}</span><div class="upload-bar"><div class="upload-bar-fill"></div></div>`;
    uploadList.appendChild(item);
    const fill = item.querySelector(".upload-bar-fill");
    requestAnimationFrame(() => fill.style.width = "100%");

    setTimeout(() => {
      const mock = mockExtracts[(docsExtracted.length) % mockExtracts.length];
      docsExtracted.push(mock);
      renderTimeline();
    }, 1200);
  });
}

function renderTimeline(){
  if(!docsExtracted.length) return;
  timeline.innerHTML = "";
  docsExtracted
    .slice()
    .forEach(doc => {
      const el = document.createElement("div");
      el.className = "tl-item";
      el.innerHTML = `<h4>${doc.title}</h4><p>${doc.body}${doc.flag ? ' <span class="tl-flag">⚠ out of range</span>' : ''}</p>`;
      timeline.appendChild(el);
    });
}

// ===================== SUMMARY =====================
function buildSummary(){
  const complaint = historyList.querySelector('li[data-key="complaint"] .hv').textContent;
  const onset = historyList.querySelector('li[data-key="onset"] .hv').textContent;
  const character = historyList.querySelector('li[data-key="character"] .hv').textContent;
  const radiation = historyList.querySelector('li[data-key="radiation"] .hv').textContent;
  const severity = historyList.querySelector('li[data-key="severity"] .hv').textContent;

  document.getElementById("sumComplaint").textContent = complaint === "—" ? "Not captured yet — visit Converse." : complaint;

  if(onset !== "—"){
    document.getElementById("sumHpi").textContent =
      `Onset: ${onset}. Character: ${character}. Radiation: ${radiation}. Severity: ${severity}.`;
  }

  if(docsExtracted.length){
    document.getElementById("sumLabs").textContent = docsExtracted.map(d => d.title).join(" · ");
  }
}

document.getElementById("regenBtn").addEventListener("click", () => {
  const btn = document.getElementById("regenBtn");
  btn.textContent = "Regenerating…";
  setTimeout(() => { btn.textContent = "Regenerate"; buildSummary(); }, 900);
});

document.getElementById("pushBtn").addEventListener("click", () => {
  const status = document.getElementById("pushStatus");
  status.textContent = "Pushing to HIS…";
  setTimeout(() => { status.textContent = "✓ Synced to HIS and ABHA record"; }, 1300);
});

// ===================== CONSULT =====================
function buildConsult(){
  const complaint = historyList.querySelector('li[data-key="complaint"] .hv').textContent;
  document.getElementById("cComplaint").textContent = complaint === "—" ? "Pending intake" : complaint;
  document.getElementById("cPatient").textContent = document.querySelector('#screen-identify input').value || "New patient";
}
