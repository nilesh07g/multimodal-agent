// phase 5 — real ui: three panels per agent turn, markdown answer, plan trace,
// follow-up flow (client-side session context), drag-drop file upload.

const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const queryInput = document.getElementById("queryInput");
const sendBtn = document.getElementById("sendBtn");
const dropOverlay = document.getElementById("dropOverlay");

let pending = [];
let pendingFollowUp = null; // {question, priorQuery, priorFilesNote} — set when agent asks a follow-up

// --- file staging ---
fileInput.addEventListener("change", (e) => {
  for (const f of e.target.files) pending.push(f);
  fileInput.value = "";
  renderChips();
});

function renderChips() {
  fileList.innerHTML = "";
  pending.forEach((f, i) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.innerHTML = `${escapeHtml(f.name)} <span class="x" data-i="${i}">&times;</span>`;
    fileList.appendChild(chip);
  });
  fileList.querySelectorAll(".x").forEach((x) => {
    x.addEventListener("click", () => {
      pending.splice(parseInt(x.dataset.i, 10), 1);
      renderChips();
    });
  });
}

// --- drag & drop anywhere on the page ---
let dragDepth = 0;
document.addEventListener("dragenter", (e) => {
  if (!e.dataTransfer?.types?.includes("Files")) return;
  dragDepth++;
  dropOverlay.classList.add("show");
});
document.addEventListener("dragleave", () => {
  dragDepth = Math.max(0, dragDepth - 1);
  if (dragDepth === 0) dropOverlay.classList.remove("show");
});
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  dropOverlay.classList.remove("show");
  if (!e.dataTransfer?.files) return;
  for (const f of e.dataTransfer.files) pending.push(f);
  renderChips();
});

// --- helpers ---
function bubble(role, contentEl) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const b = document.createElement("div");
  b.className = "bubble";
  if (typeof contentEl === "string") b.innerHTML = contentEl;
  else b.appendChild(contentEl);
  wrap.appendChild(b);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return b;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c]
  ));
}

function truncate(s, n) {
  s = String(s || "");
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function renderMarkdown(s) {
  if (window.marked) return window.marked.parse(String(s || ""));
  return `<p>${escapeHtml(s)}</p>`;
}

// --- agent turn renderer ---
function renderAgentTurn(json) {
  const wrap = document.createElement("div");
  wrap.className = "agent-turn";

  // follow-up short-circuits everything else
  if (json.follow_up) {
    const fu = document.createElement("div");
    fu.className = "follow-up";
    fu.innerHTML = `
      <div class="fu-label">i need a bit more info</div>
      <div class="fu-question">${escapeHtml(json.follow_up)}</div>
      <div class="fu-hint">type your answer below and hit send</div>`;
    wrap.appendChild(fu);
    pendingFollowUp = {
      question: json.follow_up,
      priorQuery: json.query || "",
      priorFilesNote: (json.extracted?.files || []).map(f => f.filename).filter(Boolean).join(", "),
    };
    return wrap;
  }

  // 1. extracted panel (collapsible per file)
  const files = json.extracted?.files || [];
  if (files.length || (json.extracted?.urls || []).length) {
    const panel = document.createElement("details");
    panel.className = "panel extracted";
    panel.open = false;
    let header = `<summary><span class="tag">extracted</span> ${files.length} file${files.length === 1 ? "" : "s"}`;
    const yts = json.extracted?.youtube_urls || [];
    if (yts.length) header += ` · ${yts.length} youtube url${yts.length === 1 ? "" : "s"} detected`;
    header += "</summary>";
    let body = "";
    files.forEach((f, i) => {
      body += `<div class="file-block">`;
      body += `<div class="file-head">${escapeHtml(f.filename || `file ${i+1}`)} · <span class="muted">${escapeHtml(f.kind || "?")}</span></div>`;
      if (f.error) {
        body += `<div class="file-err">${escapeHtml(f.error)}</div>`;
      } else {
        const r = f.result || {};
        const text = r.text || "";
        const meta = [];
        if (r.avg_confidence !== undefined) meta.push(`ocr conf ${r.avg_confidence}`);
        if (r.word_count !== undefined) meta.push(`${r.word_count} words`);
        if (r.total_pages !== undefined) meta.push(`${r.total_pages} pages`);
        if (r.ocr_pages) meta.push(`${r.ocr_pages} via ocr`);
        if (r.duration_sec !== undefined) meta.push(`${r.duration_sec}s`);
        if (r.language) meta.push(r.language);
        if (meta.length) body += `<div class="file-meta">${meta.join(" · ")}</div>`;
        body += `<pre class="file-text">${escapeHtml(text)}</pre>`;
      }
      body += `</div>`;
    });
    if (yts.length) {
      body += `<div class="file-block"><div class="file-head">detected urls</div>`;
      yts.forEach(y => { body += `<div class="url-line">▶ ${escapeHtml(y.url)}</div>`; });
      body += `</div>`;
    }
    panel.innerHTML = header + body;
    wrap.appendChild(panel);
  }

  // 2. answer panel
  const answer = document.createElement("div");
  answer.className = "panel answer";
  answer.innerHTML = `<div class="answer-body">${renderMarkdown(json.answer || "")}</div>`;
  wrap.appendChild(answer);

  // 3. plan trace panel
  const trace = json.plan_trace || [];
  if (trace.length) {
    const p = document.createElement("details");
    p.className = "panel trace";
    p.open = false;
    let hdr = `<summary><span class="tag">plan trace</span> ${trace.length} step${trace.length === 1 ? "" : "s"}`;
    if (json.plan?.overall_reason) hdr += ` · <span class="muted">${escapeHtml(truncate(json.plan.overall_reason, 60))}</span>`;
    hdr += "</summary>";
    let body = "";
    trace.forEach((s) => {
      const badge = s.status === "ok" ? "ok" : "err";
      body += `<div class="trace-row">
        <div class="trace-line">
          <span class="idx">${s.step_number}.</span>
          <span class="tool">${escapeHtml(s.tool)}</span>
          <span class="status ${badge}">${badge}</span>
          <span class="dur">${s.duration_ms}ms</span>
        </div>`;
      if (s.reason) body += `<div class="trace-reason">${escapeHtml(s.reason)}</div>`;
      if (s.output_preview) body += `<div class="trace-preview">${escapeHtml(truncate(s.output_preview, 240))}</div>`;
      if (s.error) body += `<div class="trace-err">${escapeHtml(s.error)}</div>`;
      body += `</div>`;
    });
    p.innerHTML = hdr + body;
    wrap.appendChild(p);
  }

  return wrap;
}

// --- submit ---
composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  let q = queryInput.value.trim();
  if (!q && pending.length === 0 && !pendingFollowUp) return;

  // if we owed a follow-up answer, weave the prior context into this query
  if (pendingFollowUp && q) {
    q = `earlier you asked: "${pendingFollowUp.question}"\nmy prior request was: "${pendingFollowUp.priorQuery}"\nmy answer to your follow-up: ${q}`;
    pendingFollowUp = null;
  }

  // user bubble
  const userWrap = document.createElement("div");
  if (queryInput.value.trim()) userWrap.innerHTML = `<p>${escapeHtml(queryInput.value.trim())}</p>`;
  if (pending.length) userWrap.innerHTML += `<p class="muted small">attached: ${pending.map(f => escapeHtml(f.name)).join(", ")}</p>`;
  bubble("user", userWrap);

  queryInput.value = "";
  const attached = pending.slice();
  pending = [];
  renderChips();

  // loading bubble
  const loading = bubble("agent", `<div class="loading"><span class="spinner"></span> extracting &amp; planning…</div>`);
  sendBtn.disabled = true;

  const fd = new FormData();
  fd.append("query", q);
  for (const f of attached) fd.append("files", f);

  try {
    const resp = await fetch("/api/chat", { method: "POST", body: fd });
    if (!resp.ok) throw new Error(`server returned ${resp.status}`);
    const json = await resp.json();
    loading.innerHTML = "";
    loading.appendChild(renderAgentTurn(json));
  } catch (err) {
    loading.innerHTML = `<div class="err">error: ${escapeHtml(err.message || String(err))}</div>`;
  } finally {
    sendBtn.disabled = false;
    queryInput.focus();
  }
});

queryInput.focus();
