// phase 1: ui shell only. wiring to /api/chat comes in phase 5.

const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const queryInput = document.getElementById("queryInput");
const sendBtn = document.getElementById("sendBtn");

let pending = [];

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

function bubble(role, html) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const b = document.createElement("div");
  b.className = "bubble";
  b.innerHTML = html;
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

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = queryInput.value.trim();
  if (!q && pending.length === 0) return;

  const parts = [];
  if (q) parts.push(`<p>${escapeHtml(q)}</p>`);
  if (pending.length) {
    parts.push(`<p style="color:#8b93a7;font-size:12px">attached: ${pending.map((f) => escapeHtml(f.name)).join(", ")}</p>`);
  }
  bubble("user", parts.join(""));

  queryInput.value = "";
  const attached = pending.slice();
  pending = [];
  renderChips();

  const loading = bubble("agent", `<p><span class="spinner"></span> extracting...</p>`);
  sendBtn.disabled = true;

  const fd = new FormData();
  fd.append("query", q);
  for (const f of attached) fd.append("files", f);

  try {
    const resp = await fetch("/api/chat", { method: "POST", body: fd });
    const json = await resp.json();
    // phase 2: dump raw extractor json. phase 5 replaces this with real panels.
    loading.innerHTML = `<p style="color:#8b93a7;font-size:12px">phase 2 raw extractor output</p>
      <pre style="margin:0;font-size:12px;overflow:auto;max-height:60vh;white-space:pre-wrap">${escapeHtml(JSON.stringify(json, null, 2))}</pre>`;
  } catch (err) {
    loading.innerHTML = `<p style="color:#ff6b6b">error: ${escapeHtml(err.message || String(err))}</p>`;
  } finally {
    sendBtn.disabled = false;
  }
});
