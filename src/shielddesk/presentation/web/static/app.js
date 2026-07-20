"use strict";

// ShieldDesk web UI — vanilla JS, nessuna dipendenza esterna (resta offline).

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const RISK_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE"];
const RISK_ASC = ["SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

// Stato di sessione della schermata Analisi Chat (client-side).
const chat = { timeline: [], filter: "ALL" };

// --------------------------------------------------------------- HTTP helper
async function api(path, { method = "GET", body, form } = {}) {
  const opts = { method: form ? "POST" : method };
  if (form) {
    opts.body = form; // multipart: il browser imposta da sé il Content-Type + boundary
  } else if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = `Errore ${res.status}`;
    try {
      const data = await res.json();
      if (data && data.detail) detail = data.detail;
    } catch (_) { /* corpo non-JSON */ }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

// --------------------------------------------------------------- Toast
let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("err", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3800);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

async function withBusy(btn, fn) {
  if (btn) btn.disabled = true;
  try {
    return await fn();
  } catch (err) {
    toast(err.message || "Operazione non riuscita", true);
    throw err;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// --------------------------------------------------------------- Tabs
function showTab(name) {
  $$(".tab").forEach((t) => t.setAttribute("aria-selected", String(t.dataset.tab === name)));
  $$(".panel").forEach((p) => { p.hidden = p.id !== `panel-${name}`; });
  if (name === "vault") loadVault();
  if (name === "dashboard") loadStatus();
}
$$(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

// --------------------------------------------------------------- Message card
function messageCard(m, { showSave = false, showContext = false, focused = false } = {}) {
  const a = m.analysis;
  const risk = a.riskLevel;
  const conf = a.topConfidence != null
    ? ` · ${a.topCategory ?? "rischio"} ${(a.topConfidence * 100).toFixed(0)}%`
    : "";
  const saveBtn = showSave
    ? (m.saved
        ? `<span class="saved-tag">✓ Salvato</span>`
        : `<button class="btn primary save" data-save="${m.index}">Salva come prova</button>`)
    : "";
  const ctxBtn = showContext
    ? `<button class="btn ghost ctx" data-context="${m.index}">🔍 Contesto</button>`
    : "";
  return `
    <article class="msg ${risk}${focused ? " focused" : ""}">
      <div class="msg-head">
        <span class="msg-sender">${escapeHtml(m.sender)}</span>
        <span class="badge ${risk}">${risk}</span>
        <span class="msg-time">${escapeHtml(m.timestamp)}</span>
      </div>
      <p class="msg-text">${escapeHtml(m.text)}</p>
      <div class="msg-foot">
        <span class="msg-model">${escapeHtml(a.tier)} · ${escapeHtml(a.modelId)}${escapeHtml(conf)}</span>
        ${ctxBtn}
        ${saveBtn}
      </div>
    </article>`;
}

// --------------------------------------------------------------- Dashboard tab
async function loadStatus() {
  try {
    const s = await api("/api/status");
    $("#status-line").textContent = s.statusText;
    const v = await api("/api/vault/evidence");
    $("#stat-evidence").textContent = v.count;
  } catch (err) {
    $("#status-line").textContent = "Non connesso";
  }
  try {
    const t = await api("/api/chat/timeline");
    $("#stat-timeline").textContent = t.count;
  } catch (_) { /* ignore */ }
}

// --------------------------------------------------------------- Chat: dashboard
function summarize(timeline) {
  const counts = Object.fromEntries(RISK_ORDER.map((r) => [r, 0]));
  const senders = new Set();
  timeline.forEach((m) => {
    counts[m.analysis.riskLevel] = (counts[m.analysis.riskLevel] || 0) + 1;
    senders.add(m.sender);
  });
  return {
    counts,
    total: timeline.length,
    participants: senders.size,
    first: timeline[0]?.timestamp,
    last: timeline[timeline.length - 1]?.timestamp,
  };
}

function distributionBar(s) {
  const segs = RISK_ASC.filter((r) => s.counts[r] > 0).map((r) => {
    const pct = ((s.counts[r] / s.total) * 100).toFixed(2);
    return `<span class="seg ${r}" style="width:${pct}%" title="${r}: ${s.counts[r]}"></span>`;
  }).join("");
  return `<div class="distbar">${segs}</div>`;
}

function filterChips(s) {
  const chip = (level, label, count) => {
    const active = chat.filter === level ? " active" : "";
    const cls = level === "ALL" ? "all" : level;
    return `<button class="chip ${cls}${active}" data-filter="${level}">${label} <b>${count}</b></button>`;
  };
  let chips = chip("ALL", "Tutti", s.total);
  RISK_ORDER.forEach((r) => { if (s.counts[r] > 0) chips += chip(r, r, s.counts[r]); });
  return `<div class="chips" role="tablist" aria-label="Filtra per rischio">${chips}</div>`;
}

function renderChatResults() {
  const box = $("#chat-results");
  const t = chat.timeline;
  $("#stat-timeline").textContent = t.length;
  if (!t.length) {
    box.innerHTML = `<div class="empty">Nessun messaggio analizzato. Incolla una chat o carica un file .txt, poi premi <strong>Analizza</strong>.</div>`;
    return;
  }
  const s = summarize(t);
  const period = s.first && s.last
    ? (s.first === s.last ? s.first : `${s.first} → ${s.last}`) : "—";

  const dashboard = `
    <div class="card dash">
      <div class="stat-row">
        <div class="stat"><span class="stat-num">${s.total}</span><span class="stat-lbl">Messaggi</span></div>
        <div class="stat"><span class="stat-num">${s.participants}</span><span class="stat-lbl">Partecipanti</span></div>
        <div class="stat crit"><span class="stat-num">${s.counts.CRITICAL}</span><span class="stat-lbl">Critici</span></div>
        <div class="stat high"><span class="stat-num">${s.counts.HIGH}</span><span class="stat-lbl">Alti</span></div>
      </div>
      <div class="period">${escapeHtml(period)}</div>
      ${distributionBar(s)}
      ${filterChips(s)}
    </div>`;

  const visible = chat.filter === "ALL"
    ? t : t.filter((m) => m.analysis.riskLevel === chat.filter);
  const list = visible.length
    ? visible.map((m) => messageCard(m, { showSave: true, showContext: true })).join("")
    : `<div class="empty">Nessun messaggio con rischio ${chat.filter}.</div>`;

  box.innerHTML = dashboard + `<div class="timeline">${list}</div>`;

  box.querySelectorAll("[data-filter]").forEach((b) =>
    b.addEventListener("click", () => { chat.filter = b.dataset.filter; renderChatResults(); }));
  box.querySelectorAll("[data-save]").forEach((b) =>
    b.addEventListener("click", () => saveEvidence(Number(b.dataset.save), b)));
  box.querySelectorAll("[data-context]").forEach((b) =>
    b.addEventListener("click", () => openContext(Number(b.dataset.context))));
}

// --------------------------------------------------------------- Chat: context focus
function openContext(index) {
  const start = Math.max(0, index - 5);
  const end = Math.min(chat.timeline.length, index + 6); // +5 dopo, inclusivo
  const slice = chat.timeline.slice(start, end);
  $("#context-title").textContent = `Contesto del messaggio #${index + 1}`;
  $("#context-list").innerHTML = slice
    .map((m) => messageCard(m, { focused: m.index === index })).join("");
  $("#context-modal").hidden = false;
}
function closeContext() { $("#context-modal").hidden = true; }

// --------------------------------------------------------------- Chat: actions
const ANALYZING_MSG =
  "Analisi in corso… con l'analisi contestuale può richiedere qualche secondo per messaggio.";

function setChatLoading(message) {
  $("#chat-results").innerHTML =
    `<div class="loading"><span class="spinner" aria-hidden="true"></span><span>${escapeHtml(message)}</span></div>`;
}

async function runAnalysis(btn, call, onDone) {
  setChatLoading(ANALYZING_MSG);
  try {
    const data = await withBusy(btn, call);
    chat.timeline = data.timeline;
    chat.filter = "ALL";
    renderChatResults();
    onDone(data);
  } catch (_) {
    // withBusy ha già mostrato il toast d'errore; ripristino l'area risultati.
    renderChatResults();
  }
}

async function analyzeChat(btn) {
  const raw = $("#chat-input").value.trim();
  if (!raw) { toast("Incolla prima il testo di una chat o carica un file.", true); return; }
  await runAnalysis(btn, () => api("/api/chat/analyze", { method: "POST", body: { rawText: raw } }),
    (data) => { if (!data.count) toast("Nessun messaggio riconosciuto nel testo.", true); });
}

async function analyzeFile(file) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  await runAnalysis($("#btn-analyze"), () => api("/api/chat/analyze-file", { form }),
    (data) => toast(
      data.count ? `File analizzato: ${data.count} messaggi.` : "Nessun messaggio riconosciuto nel file.",
      !data.count));
}

async function saveEvidence(index, btn) {
  const data = await withBusy(btn, () =>
    api("/api/chat/save-evidence", { method: "POST", body: { index } }));
  chat.timeline = data.timeline;
  renderChatResults();
  toast("Messaggio salvato in cassaforte.");
}

// --------------------------------------------------------------- Vault tab
async function loadVault() {
  try {
    renderVault(await api("/api/vault/evidence"));
  } catch (err) {
    toast(err.message, true);
  }
}
function renderVault(data) {
  $("#vault-count").textContent = data.count;
  $("#stat-evidence").textContent = data.count;
  const box = $("#vault-list");
  box.innerHTML = data.items.length
    ? data.items.map((m) => messageCard(m)).join("")
    : `<div class="empty">La cassaforte è vuota. Salva prove dall'<strong>Analisi chat</strong> o usa i pulsanti qui sopra.</div>`;
}
async function vaultAction(path, btn, okMsg) {
  const data = await withBusy(btn, () => api(path, { method: "POST" }));
  renderVault(data);
  if (okMsg) toast(okMsg);
}

// --------------------------------------------------------------- Export modal
let exportTarget = null;
function openExport(target) {
  exportTarget = target;
  $("#export-password").value = "";
  $("#export-redact").checked = true;
  $("#export-modal").hidden = false;
  $("#export-password").focus();
}
function closeExport() { $("#export-modal").hidden = true; }
async function confirmExport(btn) {
  const zipPassword = $("#export-password").value;
  const redact = $("#export-redact").checked;
  if (!zipPassword) { toast("Inserisci una password per lo ZIP.", true); return; }
  const path = exportTarget === "chat" ? "/api/chat/export" : "/api/vault/export";
  const res = await withBusy(btn, () =>
    api(path, { method: "POST", body: { zipPassword, redact } }));
  closeExport();
  toast(`Report esportato: ${res.path}`);
}

// --------------------------------------------------------------- File upload wiring
function wireUpload() {
  const input = $("#file-input");
  const zone = $("#dropzone");
  $("#btn-pick-file").addEventListener("click", () => input.click());
  input.addEventListener("change", () => { if (input.files[0]) analyzeFile(input.files[0]); input.value = ""; });
  ["dragenter", "dragover"].forEach((ev) =>
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) =>
    zone.addEventListener(ev, (e) => { e.preventDefault(); zone.classList.remove("over"); }));
  zone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) analyzeFile(file);
  });
}

// --------------------------------------------------------------- Wiring
$("#btn-analyze").addEventListener("click", (e) => analyzeChat(e.currentTarget));
$("#btn-chat-export").addEventListener("click", () => openExport("chat"));
wireUpload();

$("#btn-refresh").addEventListener("click", (e) => withBusy(e.currentTarget, loadVault));
$("#btn-process").addEventListener("click", (e) =>
  vaultAction("/api/vault/process-simulated", e.currentTarget, "Notifiche simulate processate."));
$("#btn-demo").addEventListener("click", (e) =>
  vaultAction("/api/vault/demo-evidence", e.currentTarget, "Prova demo aggiunta."));
$("#btn-vault-export").addEventListener("click", () => openExport("vault"));

$("#btn-export-cancel").addEventListener("click", closeExport);
$("#btn-export-confirm").addEventListener("click", (e) => confirmExport(e.currentTarget));
$("#export-modal").addEventListener("click", (e) => { if (e.target.id === "export-modal") closeExport(); });

$("#btn-context-close").addEventListener("click", closeContext);
$("#context-modal").addEventListener("click", (e) => { if (e.target.id === "context-modal") closeContext(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeExport(); closeContext(); } });

// --------------------------------------------------------------- Boot
loadStatus();
