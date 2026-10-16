/* EA/ATLAS POC UI — modular single file: api client, state, per-page
   renderers, event bindings. All API strings are escaped before HTML. */
"use strict";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;",
          "'": "&#39;" }[c]));

const api = {
  async decode(r) {
    const text = await r.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      const unavailable = r.status === 502 || r.status === 503;
      throw new Error(unavailable
        ? "The POC server is unavailable. Refresh after it restarts."
        : `The server returned an unexpected ${r.status} response.`);
    }
    if (!r.ok) throw new Error(data.error?.message || r.statusText);
    return data;
  },
  async get(path) {
    const r = await fetch(path);
    return this.decode(r);
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body) });
    return this.decode(r);
  },
};

const state = {
  persona: localStorage.getItem("persona") || "consumer",
  conversationId: null,
  selectedTags: new Set(),
};

const EXAMPLES = [
  "Show the latest Insurance technology strategy",
  "Find the current ARB submission template",
  "What is the approved API strategy?",
  "What is our policy on quantum computing hardware?",
];

const TRANSITIONS = {
  DRAFT: { target: "REVIEW", label: "Submit for review",
           personas: ["contributor", "owner", "admin"] },
  REVIEW: { target: "APPROVED", label: "Approve",
            personas: ["approver", "admin"] },
  APPROVED: { target: "SUPERSEDED", label: "Supersede",
              personas: ["owner", "approver", "admin"] },
  SUPERSEDED: { target: "ARCHIVED", label: "Archive",
                personas: ["curator", "admin"] },
};

function bytesToBase64(bytes) {
  let binary = "";
  const size = 0x8000;
  for (let i = 0; i < bytes.length; i += size) {
    binary += String.fromCharCode(...bytes.subarray(i, i + size));
  }
  return btoa(binary);
}

/* ----------------------------------------------------------- chrome */
async function initChrome() {
  const sel = document.getElementById("persona");
  const { personas } = await api.get("/api/personas");
  sel.innerHTML = personas.map(p =>
    `<option value="${esc(p.id)}">${esc(p.display_name)}</option>`).join("");
  sel.value = state.persona;
  sel.addEventListener("change", () => {
    state.persona = sel.value;
    localStorage.setItem("persona", sel.value);
    state.conversationId = null;
    renderPage(currentPage());
  });
  const integ = await api.get("/api/integrations");
  const cl = document.getElementById("int-claude");
  cl.textContent = integ.claude_configured ? "Claude configured"
                                          : "Local synthesis";
  cl.classList.toggle("on", integ.claude_configured);
  const sp = document.getElementById("int-sp");
  sp.textContent = integ.sharepoint_configured ? "Graph configured"
                                               : "SharePoint mock";
  sp.classList.toggle("on", integ.sharepoint_configured);
  drawMotif();
}

function drawMotif() {
  const svg = document.getElementById("motif");
  const dots = [], lines = [];
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 14; i++)
    dots.push([20 + rnd() * 300, 15 + rnd() * 190]);
  for (let i = 0; i < dots.length - 4; i += 2)
    lines.push(`<line x1="${dots[i][0]}" y1="${dots[i][1]}"
      x2="${dots[i + 3][0]}" y2="${dots[i + 3][1]}"
      stroke="#6F8191" stroke-width="0.6"/>`);
  for (const [x, y] of dots)
    lines.push(`<circle cx="${x}" cy="${y}" r="${2 + rnd() * 2}"
      fill="none" stroke="#31C6D4" stroke-width="1"/>`);
  svg.innerHTML = lines.join("");
}

function currentPage() {
  return document.querySelector(".tab.active").dataset.page;
}

function renderPage(name) {
  ({ ask: renderAsk, discover: renderDiscover,
     contribute: () => {}, govern: renderGovern,
     reports: renderReports })[name]?.();
}

/* ----------------------------------------------------------- Ask */
function renderAsk() {
  const chips = document.getElementById("chips");
  chips.innerHTML = EXAMPLES.map(e =>
    `<button class="chip">${esc(e)}</button>`).join("");
  chips.querySelectorAll(".chip").forEach(c =>
    c.addEventListener("click", () => {
      document.getElementById("q").value = c.textContent;
      ask();
    }));
}

async function ask() {
  const q = document.getElementById("q").value.trim();
  if (!q) return;
  const tr = document.getElementById("transcript");
  tr.insertAdjacentHTML("afterbegin",
    `<div class="qa"><div class="q">${esc(q)}</div>
     <div class="a"><em>Retrieving authorized evidence…</em></div></div>`);
  const node = tr.firstElementChild;
  try {
    const a = await api.post("/api/agent/query", {
      persona: state.persona, question: q,
      conversation_id: state.conversationId });
    state.conversationId = a.conversation_id;
    const cites = a.citations.map(c => `
      <div class="cite">
        <div class="t">${esc(c.title)} · v${esc(c.version)}</div>
        <div class="e">${esc(c.excerpt)}</div>
        <a href="${esc(c.source_url)}" target="_blank"
           rel="noopener">${esc(c.source_url)}</a>
      </div>`).join("");
    node.innerHTML = `
      <div class="q">${esc(q)}</div>
      <span class="status-pill status-${esc(a.status)}">${esc(
        a.status === "grounded" ? "GROUNDED" : "ABSTAINED")}</span>
      <div class="a">${esc(a.answer)}</div>${cites}
      <div class="meta">provider: ${esc(a.provider)} · audit
        ${esc(a.audit_id.slice(0, 8))}</div>`;
  } catch (e) {
    node.querySelector(".a").textContent = "Error: " + e.message;
  }
}

/* ------------------------------------------------------- Discover */
async function renderDiscover() {
  const { tags } = await api.get(
    `/api/tags?persona=${state.persona}`);
  const tagrow = document.getElementById("tagrow");
  tagrow.innerHTML = tags.map(t =>
    `<button class="tag${state.selectedTags.has(t.tag) ? " sel" : ""}"
      data-tag="${esc(t.tag)}">${esc(t.tag)} · ${t.count}</button>`)
    .join("");
  tagrow.querySelectorAll(".tag").forEach(b =>
    b.addEventListener("click", () => {
      const t = b.dataset.tag;
      state.selectedTags.has(t) ? state.selectedTags.delete(t)
                                : state.selectedTags.add(t);
      loadArtifacts();
    }));
  await loadArtifacts();
}

async function loadArtifacts() {
  const p = new URLSearchParams({
    persona: state.persona,
    query: document.getElementById("dq").value,
    status: document.getElementById("dstatus").value,
    audience: document.getElementById("daudience").value,
    sort: document.getElementById("dsort").value,
    tags: [...state.selectedTags].join(","),
  });
  const { artifacts } = await api.get(`/api/artifacts?${p}`);
  document.getElementById("results").innerHTML = artifacts.map(a => `
    <div class="acard" data-id="${esc(a.id)}">
      <h3>${esc(a.title)}</h3>
      <div class="sub">
        <span class="pill pill-${esc(a.lifecycle_status)}">${esc(
          a.lifecycle_status)}</span>
        ${a.is_current_approved ? '<span class="pill pill-cur">CURRENT APPROVED</span>' : ""}
        v${esc(a.version)} · ${esc(a.audience)}
      </div>
      <div class="sub">Owner: ${esc(a.owner || "—")} · uploaded
        ${esc((a.uploaded_at || "").slice(0, 10))}</div>
      <div class="taglist">${a.tags.map(esc).join(" · ")}</div>
    </div>`).join("") ||
    "<p class='lede'>No artifacts visible for this persona/filter.</p>";
  document.querySelectorAll(".acard").forEach(c =>
    c.addEventListener("click", () => openArtifact(c.dataset.id)));
}

async function openArtifact(id) {
  const { artifact: a } = await api.get(
    `/api/artifacts/${id}?persona=${state.persona}`);
  const { versions } = await api.get(
    `/api/artifacts/${id}/versions?persona=${state.persona}`);
  const hist = (a.lifecycle_events || []).map(e =>
    `<div class="vrow">${esc(e.at.slice(0, 10))} ·
      ${esc(e.from_status || "—")} → <strong>${esc(e.to_status)}</strong>
      by ${esc(e.actor_persona)}${e.note ? " · " + esc(e.note) : ""}</div>`
  ).join("");
  const vers = versions.map(v =>
    `<div class="vrow">v${esc(v.version)} ·
      <span class="pill pill-${esc(v.lifecycle_status)}">${esc(
        v.lifecycle_status)}</span>
      ${v.is_current_approved ? "CURRENT" : ""}</div>`).join("");
  document.getElementById("drawer-body").innerHTML = `
    <h2>${esc(a.title)}</h2>
    <p class="sub">v${esc(a.version)} · ${esc(a.segment)} ·
      ${esc(a.domain)} · ${esc(a.content_type)} · ${esc(a.audience)}</p>
    <p>${esc(a.description)}</p>
    <p style="margin:12px 0">${esc((a.content_text || "").slice(0, 800))}</p>
    <p><a href="${esc(a.source_url)}" target="_blank"
      rel="noopener">${esc(a.source_url)}</a></p>
    <h3 style="margin-top:18px">Versions</h3>${vers}
    <h3 style="margin-top:18px">Lifecycle history</h3>${hist}`;
  document.getElementById("drawer").hidden = false;
}

/* ------------------------------------------------------ Contribute */
function bindContribute() {
  document.getElementById("contrib").addEventListener("submit",
    async (ev) => {
      ev.preventDefault();
      const f = ev.target, msg = document.getElementById("contrib-msg");
      msg.className = "msg"; msg.textContent = "";
      const fd = new FormData(f);
      const payload = {
        persona: state.persona,
        title: fd.get("title"), owner: fd.get("owner"),
        version: fd.get("version"), segment: fd.get("segment"),
        domain: fd.get("domain"), content_type: fd.get("content_type"),
        audience: fd.get("audience"), review_date: fd.get("review_date"),
        source_url: fd.get("source_url"),
        tags: fd.get("tags").split(",").map(s => s.trim()).filter(Boolean),
        allowed_groups: fd.get("allowed_groups").split(",")
          .map(s => s.trim()).filter(Boolean),
        description: fd.get("description"), content: fd.get("content"),
      };
      const file = f.file.files[0];
      if (file) {
        if (file.size > 3.5 * 1024 * 1024) {
          msg.className = "msg err";
          msg.textContent = "File exceeds the 3.5 MB demo limit; " +
            "register it as a link or paste its text instead.";
          return;
        }
        const buf = await file.arrayBuffer();
        payload.filename = file.name;
        payload.file_base64 = bytesToBase64(new Uint8Array(buf));
      }
      try {
        const r = await api.post("/api/artifacts", payload);
        msg.classList.add("ok");
        msg.textContent = "Created DRAFT artifact " +
          r.artifact_id.slice(0, 8) +
          (r.warnings?.length ? " — " + r.warnings.join(" ") : "");
        f.reset();
      } catch (e) {
        msg.classList.add("err");
        msg.textContent = e.message;
      }
    });
}

/* --------------------------------------------------------- Govern */
async function renderGovern() {
  const lede = document.getElementById("govern-lede");
  if (state.persona === "consumer") {
    lede.textContent = "Consumers have read-only access. Lifecycle " +
      "actions require contributor, owner, approver, curator or admin " +
      "personas.";
  } else {
    lede.textContent = "Lifecycle queue for the " + state.persona +
      " persona. Buttons appear only where your role can transition.";
  }
  const { artifacts } = await api.get(
    `/api/artifacts?persona=${state.persona}&sort=updated_desc`);
  const items = artifacts.length ? artifacts : [];
  const { artifacts: superseded } = await api.get(
    `/api/artifacts?persona=${state.persona}&status=SUPERSEDED`);
  const all = [...items, ...superseded];
  document.getElementById("govern-list").innerHTML = all.map(a => {
    const step = TRANSITIONS[a.lifecycle_status];
    return `<div class="grow">
      <div class="info">
        <strong>${esc(a.title)}</strong> · v${esc(a.version)}
        <span class="pill pill-${esc(a.lifecycle_status)}">${esc(
          a.lifecycle_status)}</span>
        <div class="sub">owner ${esc(a.owner || "—")} · review
          ${esc(a.review_date || "—")}</div>
      </div>
      ${step && step.personas.includes(state.persona)
        ? `<button class="gbtn" data-id="${esc(a.id)}"
           data-target="${step.target}">${step.label}</button>`
        : '<span class="sub">No action for this persona</span>'}
    </div>`;
  }).join("") || "<p class='lede'>No artifacts in scope.</p>";
  document.querySelectorAll(".gbtn").forEach(b =>
    b.addEventListener("click", async () => {
      try {
        await api.post(`/api/artifacts/${b.dataset.id}/transition`, {
          persona: state.persona, target_status: b.dataset.target,
          note: "demo transition" });
        renderGovern();
      } catch (e) { alert(e.message); }
    }));
}

/* -------------------------------------------------------- Reports */
async function renderReports() {
  const r = await api.get(
    `/api/reports/quality?persona=${state.persona}`);
  document.getElementById("report-note").textContent = r.details_visible
    ? "Item-level remediation detail is visible to curator/admin personas."
    : "Aggregate counts only — item-level detail requires curator or " +
      "admin. Unauthorized content is never listed.";
  const labels = {
    review_overdue: "Review overdue / stale", unowned: "Unowned",
    superseded: "Superseded retained",
    duplicate_candidates: "Duplicate candidates",
    broken_links: "Broken links" };
  document.getElementById("report-cards").innerHTML =
    Object.entries(r.counts).map(([k, v]) => `
      <div class="acard"><h3>${v}</h3>
        <div class="sub">${labels[k] || k}</div></div>`).join("");
  let html = "";
  if (r.items) {
    for (const [k, arr] of Object.entries(r.items)) {
      if (!arr.length) continue;
      html += `<h3 style="margin:22px 0 8px">${labels[k] || k}</h3>` +
        arr.map(i => `<div class="vrow">${esc(i.title || i.url ||
          i.content_hash || i.id)}${i.version ? " · v" + esc(i.version)
          : ""}${i.review_date ? " · due " + esc(i.review_date) : ""}
          </div>`).join("");
    }
  }
  document.getElementById("report-items").innerHTML = html;
}

/* ----------------------------------------------------------- init */
document.querySelectorAll(".tab").forEach(t =>
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x =>
      x.classList.remove("active"));
    document.querySelectorAll(".page").forEach(x =>
      x.classList.remove("active"));
    t.classList.add("active");
    document.getElementById("page-" + t.dataset.page)
      .classList.add("active");
    renderPage(t.dataset.page);
  }));

document.getElementById("ask-btn").addEventListener("click", ask);
document.getElementById("q").addEventListener("keydown",
  e => { if (e.key === "Enter") ask(); });
["dq", "dstatus", "daudience", "dsort"].forEach(id =>
  document.getElementById(id).addEventListener("input", loadArtifacts));
document.getElementById("drawer-close").addEventListener("click",
  () => document.getElementById("drawer").hidden = true);
document.getElementById("drawer").addEventListener("click", e => {
  if (e.target.id === "drawer") e.target.hidden = true; });

bindContribute();
initChrome().then(() => renderAsk()).catch(e => {
  document.getElementById("main").innerHTML = `
    <section class="page active">
      <h1>POC service unavailable</h1>
      <p class="lede">${esc(e.message)}</p>
      <p class="lede">Refresh this page after the local server is running.</p>
    </section>`;
});
