// Greybeard frontend: no build step, plain ES modules, no dependencies.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const WO_RE = /WO-\d{4}-\d{3}/g;

const state = { tickets: [], selected: null, tab: "briefing", horizons: [], horizon: "fleet", highlight: null, cache: {}, timeline: null };

// Realistic close-outs for the live demo (the "technician finishes the job" moment).
const DEMO_CLOSEOUTS = {
  "WO-2609-114": { outcome: "fixed", root_cause: "SD-40 Quiet Mode (P-212) re-enabled on fan bank 2 after the Sep 15 factory reset",
    notes: "Skipped the coil wash and the panel fan hunt, since CH-02 has sealed SD-40 drives now. Checked the bank 2 drive parameters: P-212 Quiet Mode was ON again (reset to factory defaults on WO-2609-038). Fan bank 2 was capped at 85% above 35°C. Disabled P-212, verified all four banks at 100% at 36°C ambient. Discharge dropped from 1,580 to 1,330 kPa. Added a sticker inside the drive door: 'After any reset, disable P-212'. Sent Sudhakar sir a note.",
    parts: "", downtime_hours: 1.5, briefing_helpful: true, briefing_feedback: "Spot on. Went straight to P-212 and was done in 40 minutes." },
  "WO-2609-121": { outcome: "fixed", root_cause: "Moisture and corrosion in starter solenoid connector on DG-2 (harness routing had slipped back down)",
    notes: "Did not touch the batteries (25.2V, fine). Solenoid connector wet with fresh corrosion. The cable ties from WO-2508-003 had perished and the harness had dropped back to about 15 cm above the floor. Cleaned, re-greased, new boot, re-secured the harness with stainless ties 30 cm up. Five clean starts.",
    parts: "Dielectric grease, Heat-shrink boot, Stainless cable ties", downtime_hours: 1.0, briefing_helpful: true, briefing_feedback: "Saved a battery swap." },
  "WO-2609-127": { outcome: "fixed", root_cause: "Sill track debris on L3 and L4 landing doors; brush strips missing on L4",
    notes: "Went straight to the L3/L4 sills at lunch hour. Both packed with food debris and cling film. The brush strip on L4 was never installed. Cleaned the tracks, belt tension within spec. Zero DF-21 in 2 hours of observation. Raised a request to FM Anitha for the L4 brush strip and a daily housekeeping check.",
    parts: "", downtime_hours: 0.5, briefing_helpful: true, briefing_feedback: "Did not replace the light curtain, which saved Rs 38k." },
  "WO-2609-130": { outcome: "false_alarm", root_cause: "Discharge pressure transducer drift on circuit 1 (2019 batch, KX-1905 serial)",
    notes: "Low ambient trip. Put the manifold gauge on first: actual 1,180 kPa vs controller 1,590 kPa. Replaced the circuit 1 transducer and checked circuit 2 (reading 90 kPa high), replaced that too. This was the last unchecked 2019-batch unit.",
    parts: "2 x Pressure transducer PT-3000", downtime_hours: 1.0, briefing_helpful: true, briefing_feedback: "Gauge first. 20 minute diagnosis." },
  "WO-2609-133": { outcome: "fixed", root_cause: "Factory default Quiet Mode (P-212) enabled on new SD-40 drives",
    notes: "New unit, no history of its own, but it has the same SD-40 drives as ORB-CH-02. P-212 Quiet Mode was on for all four drives from the factory. Disabled it on all four and fan bank 2 is now at full speed. Commissioning contractor informed so they can update their checklist.",
    parts: "", downtime_hours: 0, briefing_helpful: true, briefing_feedback: "Would never have guessed a parameter on a brand new unit." },
};

// ============================================================================ utilities
async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    let msg = `${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json();
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 3000);
}

function countUp(el, to, dur = 1200) {
  to = Number(to) || 0;
  const from = Number(el.dataset.v || 0);
  el.dataset.v = to;
  if (REDUCED || from === to) { el.textContent = to.toLocaleString("en-IN"); return; }
  const t0 = performance.now();
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 4);
    el.textContent = Math.round(from + (to - from) * e).toLocaleString("en-IN");
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// Tiny, safe markdown renderer.
function md(src) {
  const lines = esc(src || "").split(/\n/);
  let html = "", list = false;
  const inline = (s) => s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<i>$2</i>")
    .replace(/(WO-\d{4}-\d{3})/g, '<button class="wo" data-wo="$1">$1</button>');
  for (const raw of lines) {
    const l = raw.trimEnd();
    const h = l.match(/^(#{1,4})\s+(.*)/);
    const li = l.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
    if (li) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(li[1])}</li>`; continue; }
    if (list) { html += "</ul>"; list = false; }
    if (h) html += `<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`;
    else if (l.trim()) html += `<p>${inline(l)}</p>`;
  }
  if (list) html += "</ul>";
  return html;
}

const woChips = (ids) => [...new Set((ids || []).filter(Boolean))].map((w) => `<button class="wo" data-wo="${esc(w)}">${esc(w)}</button>`).join("");

// Cursor spotlight on cards.
document.addEventListener("pointermove", (e) => {
  const card = e.target.closest?.(".ticket, .kb");
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
});

// Sliding indicator for any pill group.
function glide(container, activeSel, gliderSel) {
  const act = container && $(activeSel, container), g = container && $(gliderSel, container);
  if (!act || !g) return;
  const base = parseFloat(getComputedStyle(g).left) || 0;
  g.style.width = `${act.offsetWidth}px`;
  g.style.transform = `translateX(${act.offsetLeft - base}px)`;
}

// Mona-Sans-style variable letters: glyphs stretch and thicken as the cursor passes.
function variableType(el) {
  if (!el || REDUCED) return;
  const walk = (node) => {
    [...node.childNodes].forEach((n) => {
      if (n.nodeType === 3) {
        const frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(" ")); return; }
          const w = document.createElement("span"); w.className = "word";
          [...part].forEach((c) => { const s = document.createElement("span"); s.className = "ch"; s.textContent = c; w.appendChild(s); });
          frag.appendChild(w);
        });
        n.replaceWith(frag);
      } else if (n.nodeType === 1 && n.tagName !== "BR") walk(n);
    });
  };
  walk(el);
  const chars = $$(".ch", el);
  el.addEventListener("pointermove", (e) => {
    for (const c of chars) {
      const r = c.getBoundingClientRect(), d = Math.hypot(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
      const k = Math.max(0, 1 - d / 160);
      c.style.fontStretch = `${75 + 50 * (1 - k * 0.9)}%`;
      c.style.fontWeight = String(Math.round(800 + 100 * k));
      c.style.transform = `translateY(${-k * 6}px)`;
    }
  });
  el.addEventListener("pointerleave", () => chars.forEach((c) => { c.style.fontStretch = ""; c.style.fontWeight = ""; c.style.transform = ""; }));
}

// ============================================================================ neural background
const Neural = (() => {
  const c = $("#neural"), ctx = c.getContext("2d");
  let W, H, nodes = [], pulses = [], mouse = { x: -999, y: -999 }, dpr = Math.min(2, devicePixelRatio || 1);
  const resize = () => {
    W = c.width = innerWidth * dpr; H = c.height = innerHeight * dpr;
    c.style.width = innerWidth + "px"; c.style.height = innerHeight + "px";
    const n = Math.round((innerWidth * innerHeight) / 26000);
    nodes = Array.from({ length: n }, () => ({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .18 * dpr, vy: (Math.random() - .5) * .18 * dpr, r: (Math.random() * 1.4 + .6) * dpr, a: Math.random() }));
  };
  addEventListener("resize", resize); resize();
  addEventListener("pointermove", (e) => { mouse.x = e.clientX * dpr; mouse.y = e.clientY * dpr; });
  const link = 140 * dpr;
  function frame() {
    ctx.clearRect(0, 0, W, H);
    for (const n of nodes) {
      n.x += n.vx; n.y += n.vy;
      if (n.x < 0 || n.x > W) n.vx *= -1;
      if (n.y < 0 || n.y > H) n.vy *= -1;
    }
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d = Math.hypot(dx, dy);
        if (d < link) { ctx.strokeStyle = `rgba(163,113,247,${(1 - d / link) * .14})`; ctx.lineWidth = dpr * .7; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); }
      }
      const md = Math.hypot(a.x - mouse.x, a.y - mouse.y), near = md < 180 * dpr ? 1 - md / (180 * dpr) : 0;
      ctx.fillStyle = near ? `rgba(247,120,186,${.35 + near * .6})` : `rgba(210,205,195,${.18 + a.a * .2})`;
      ctx.beginPath(); ctx.arc(a.x, a.y, a.r + near * 1.6 * dpr, 0, Math.PI * 2); ctx.fill();
    }
    pulses = pulses.filter((p) => p.t < 1);
    for (const p of pulses) {
      p.t += .012;
      const x = p.a.x + (p.b.x - p.a.x) * p.t, y = p.a.y + (p.b.y - p.a.y) * p.t;
      ctx.fillStyle = `rgba(210,168,255,${1 - p.t})`; ctx.shadowColor = "#a371f7"; ctx.shadowBlur = 12 * dpr;
      ctx.beginPath(); ctx.arc(x, y, 2.2 * dpr, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
    }
    if (!REDUCED) requestAnimationFrame(frame);
  }
  frame();
  return {
    burst(n = 14) {
      for (let k = 0; k < n; k++) {
        const a = nodes[Math.floor(Math.random() * nodes.length)];
        let best = null, bd = 1e9;
        for (const b of nodes) { const d = Math.hypot(a.x - b.x, a.y - b.y); if (b !== a && d < bd && d > 30 * dpr) { bd = d; best = b; } }
        if (best) pulses.push({ a, b: best, t: Math.random() * -.4 });
      }
    },
  };
})();

// ============================================================================ memory core (header)
async function refreshStats(pulse = false) {
  try {
    const { fleet } = await api("/api/stats");
    $("#core").classList.toggle("off", !fleet.bank_id);
    countUp($("#st-docs"), fleet.total_documents ?? 0);
    countUp($("#st-facts"), fleet.total_nodes ?? 0);
    countUp($("#st-obs"), fleet.total_observations ?? 0);
    if (pulse) { $("#core").classList.remove("pulse"); void $("#core").offsetWidth; $("#core").classList.add("pulse"); }
  } catch { $("#core").classList.add("off"); }
}

// ============================================================================ board
async function loadTickets() {
  state.tickets = await api("/api/tickets");
  renderBoard();
}

function renderBoard() {
  $("#tickets").innerHTML = state.tickets.map((t, i) => `
    <button class="ticket ${t.wo_id === state.selected ? "active" : ""} ${t.status === "closed" ? "closed" : ""}" data-wo="${t.wo_id}" style="animation-delay:${i * 70}ms">
      <div class="ticket-row">
        <span class="prio ${t.priority}">${t.priority}</span>
        <span class="ticket-asset">${esc(t.asset_id)}</span>
        ${t.alarm_code ? `<span class="alarm">${esc(t.alarm_code)}</span>` : ""}
        ${t.status === "closed" ? '<span class="status-closed">✓ LEARNED</span>' : ""}
      </div>
      <div class="ticket-sym">${esc(t.symptom)}</div>
      <div class="ticket-meta"><span>${esc(t.site.name)}</span><span>·</span><span>${esc(t.asset.model)}</span><span>·</span><span class="mono">${esc(t.wo_id)}</span></div>
    </button>`).join("");
  $$("#tickets .ticket").forEach((b) => b.addEventListener("click", () => selectTicket(b.dataset.wo)));
}

function selectTicket(wo) {
  const changed = state.selected !== wo;
  state.selected = wo;
  state.tab = "briefing";
  state.highlight = null;
  $$("#tickets .ticket").forEach((b) => b.classList.toggle("active", b.dataset.wo === wo));
  if (changed) state.timeline = null;
  renderWork();
  Neural.burst(8);
}

// ============================================================================ work area
const current = () => state.tickets.find((t) => t.wo_id === state.selected);
const TABS = [["briefing", "Repair advice"], ["inspector", "Supporting evidence"], ["history", "Repair history"], ["closeout", "Record the outcome"]];

function renderWork() {
  const t = current();
  if (!t) return;
  const a = t.asset, s = t.site, tech = t.tech;
  $("#work").innerHTML = `
    <div class="job">
      <div class="job-head">
        <div>
          <div class="job-title">
            <span class="prio ${t.priority}">${t.priority}</span>
            <span class="asset-id">${esc(a.id)}</span>
            ${t.alarm_code ? `<span class="alarm">${esc(t.alarm_code)}</span>` : ""}
            <span class="muted small mono">${esc(t.wo_id)} · opened ${esc(t.opened_at.slice(11, 16))}</span>
          </div>
          <div class="job-sym">${esc(t.symptom)}</div>
          <div class="facts">
            <span>Model <b>${esc(a.model)}</b></span><span>Serial <b class="mono">${esc(a.serial)}</b></span>
            <span>Installed <b>${esc(a.installed)}</b></span><span>Site <b>${esc(s.name)}</b>, ${esc(s.locality)}</span>
          </div>
        </div>
        <div class="tech-card">
          <div class="eyebrow">Assigned</div>
          <div class="name">${esc(tech.name)}</div>
          <div class="muted small">${esc(tech.role)}</div>
          ${tech.years < 2 ? `<span class="tag-rookie">${Math.round(tech.years * 12)} months in the field</span>` : ""}
        </div>
      </div>
      <div class="timeline" id="timeline"><div class="skeleton" style="width:40%"></div><div class="skeleton"></div><div class="skeleton" style="width:80%"></div></div>
      <div class="tabs">${TABS.map(([k, l]) => `<button class="tab ${state.tab === k ? "active" : ""}" data-tab="${k}">${k === "closeout" && t.status === "closed" ? "Closed ✓" : l}</button>`).join("")}<span class="tab-ink"></span></div>
      <div id="tab-body"></div>
    </div>`;
  $$(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));
  moveInk();
  drawTimeline(t);
  renderTab(t);
}

function switchTab(k) {
  state.tab = k;
  $$(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === k));
  moveInk();
  renderTab(current());
}
function moveInk() {
  const a = $(".tab.active"), ink = $(".tab-ink");
  if (a && ink) { ink.style.width = `${a.offsetWidth - 20}px`; ink.style.transform = `translateX(${a.offsetLeft + 10}px)`; }
}
function renderTab(t) {
  ({ briefing: renderBriefingTab, inspector: renderInspector, history: renderHistory, closeout: renderCloseout })[state.tab](t);
}

// ============================================================================ memory timeline (signature visual)
const T0 = new Date("2025-03-01").getTime(), T1 = new Date("2026-09-30").getTime();
const TL = { w: 1000, left: 96, right: 14, top: 18, row: 24 };
const tx = (d) => TL.left + ((new Date(d).getTime() - T0) / (T1 - T0)) * (TL.w - TL.left - TL.right);
const OUTCOME_COLOR = { fixed: "var(--green)", not_fixed: "var(--red)", false_alarm: "var(--blue)", advisory: "var(--orange)", pm: "rgba(255,255,255,.28)" };

async function drawTimeline(t) {
  if (!state.timeline || state.timeline.asset !== t.asset.id) {
    try { state.timeline = { asset: t.asset.id, ...(await api(`/api/fleet/timeline?asset_id=${encodeURIComponent(t.asset.id)}`)) }; }
    catch { $("#timeline").innerHTML = ""; return; }
  }
  if (state.selected !== t.wo_id) return;
  const { assets, jobs } = state.timeline;
  const H = TL.top + assets.length * TL.row + 22;
  const months = [];
  for (let d = new Date(T0); d.getTime() <= T1; d.setMonth(d.getMonth() + 3)) months.push(new Date(d));
  const rowY = (id) => TL.top + assets.indexOf(id) * TL.row + TL.row / 2;
  const selfCount = jobs.filter((j) => j.asset_id === t.asset.id).length;
  $("#timeline").innerHTML = `
    <div class="tl-head">
      <div class="tl-title">Fleet memory · ${esc(t.asset.model)} · ${jobs.length} jobs across ${assets.length} unit${assets.length > 1 ? "s" : ""}${selfCount ? "" : " · this unit has no history yet"}</div>
      <div class="tl-legend"><span><i style="background:var(--green)"></i>fixed</span><span><i style="background:var(--red)"></i>didn't work</span><span><i style="background:var(--blue)"></i>false alarm</span><span><i style="background:var(--orange)"></i>advisory</span><span><i style="background:rgba(255,255,255,.3)"></i>routine PM</span><span><i style="background:var(--cite)"></i>cited by Greybeard</span></div>
    </div>
    <svg viewBox="0 0 ${TL.w} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Timeline of past jobs">
      <defs>
        <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="rgba(14,15,18,.55)"/><line x1="0" y1="0" x2="0" y2="6" stroke="rgba(255,255,255,.05)" stroke-width="2"/></pattern>
        <linearGradient id="scan" x1="0" x2="1"><stop offset="0" stop-color="rgba(245,165,36,0)"/><stop offset=".8" stop-color="rgba(245,165,36,.18)"/><stop offset="1" stop-color="rgba(245,165,36,0)"/></linearGradient>
      </defs>
      ${months.map((m) => `<line x1="${tx(m)}" x2="${tx(m)}" y1="${TL.top - 6}" y2="${H - 18}" stroke="rgba(255,255,255,.04)"/><text class="tl-axis" x="${tx(m)}" y="${H - 4}" text-anchor="middle">${m.toLocaleDateString("en-IN", { month: "short", year: "2-digit" })}</text>`).join("")}
      ${assets.map((id) => `<text class="tl-row-label ${id === t.asset.id ? "self" : ""}" x="0" y="${rowY(id) + 3.5}">${esc(id)}</text><line class="tl-track" x1="${TL.left}" x2="${TL.w - TL.right}" y1="${rowY(id)}" y2="${rowY(id)}"/>`).join("")}
      <rect class="tl-scan" id="tl-scan" x="${TL.left}" y="${TL.top - 6}" width="120" height="${assets.length * TL.row + 6}"/>
      ${jobs.map((j) => { const big = j.outcome !== "pm"; return `<circle class="tl-ring" data-ring="${j.wo_id}" cx="${tx(j.opened_at)}" cy="${rowY(j.asset_id)}" r="6"/><circle class="tl-dot" data-wo="${j.wo_id}" data-date="${j.opened_at}" cx="${tx(j.opened_at)}" cy="${rowY(j.asset_id)}" r="${big ? 4.6 : 2.4}" fill="${OUTCOME_COLOR[j.outcome] || "#888"}" ${big ? 'stroke="rgba(0,0,0,.5)" stroke-width="1"' : ""}/>`; }).join("")}
      <rect class="tl-future" id="tl-future" x="${TL.w - TL.right}" y="${TL.top - 8}" width="0" height="${assets.length * TL.row + 10}"/>
      <g id="tl-h"><line class="tl-horizon" x1="0" x2="0" y1="${TL.top - 10}" y2="${H - 18}"/><text class="tl-horizon-label" x="4" y="${TL.top - 10}">memory horizon</text></g>
    </svg>`;
  const tip = $("#tip");
  $$("#timeline .tl-dot").forEach((d) => {
    const j = jobs.find((x) => x.wo_id === d.dataset.wo);
    d.addEventListener("pointerenter", () => {
      tip.innerHTML = `<b>${esc(j.wo_id)}</b> · ${esc(j.asset_id)} · ${esc(j.opened_at.slice(0, 10))}<br><span class="outcome ${esc(j.outcome)}">${esc(j.outcome.replace("_", " "))}</span> ${esc(j.symptom)}<div class="muted" style="margin-top:4px">${esc(j.root_cause)}</div>`;
      tip.classList.add("show");
    });
    d.addEventListener("pointermove", (e) => { tip.style.left = `${Math.min(innerWidth - 340, e.clientX + 14)}px`; tip.style.top = `${e.clientY + 14}px`; });
    d.addEventListener("pointerleave", () => tip.classList.remove("show"));
    d.addEventListener("click", () => { state.highlight = j.wo_id; if (j.asset_id === t.asset.id) switchTab("history"); });
  });
  applyHorizon();
  const cached = state.cache[`${t.wo_id}:${state.horizon}`];
  if (cached) markCited(citedIds(cached));
}

function applyHorizon() {
  const h = state.horizons.find((x) => x.key === state.horizon);
  if (!h || !$("#tl-future")) return;
  const until = h.until === "0000" ? "2025-03-01" : h.until || "2026-09-30";
  const x = Math.min(TL.w - TL.right, Math.max(TL.left, tx(until)));
  const f = $("#tl-future");
  f.setAttribute("x", x); f.setAttribute("width", TL.w - TL.right - x);
  $("#tl-h").style.transform = `translateX(${x}px)`;
  $("#tl-h").style.transition = "transform .7s cubic-bezier(.2,.8,.2,1)";
  $(".tl-horizon-label").textContent = h.key === "fleet" ? "today" : h.key === "day1" ? "day 1: nothing remembered" : `memory as of ${h.label}`;
  $(".tl-horizon-label").setAttribute("text-anchor", x > TL.w - 180 ? "end" : "start");
  $(".tl-horizon-label").setAttribute("x", x > TL.w - 180 ? -4 : 4);
  $$("#timeline .tl-dot").forEach((d) => d.classList.toggle("dim", d.dataset.date >= until));
}

function markRecalled(ids) { const set = new Set(ids); $$("#timeline .tl-dot").forEach((d) => d.classList.toggle("recalled", set.has(d.dataset.wo))); }
function markCited(ids) {
  const set = new Set(ids);
  $$("#timeline .tl-dot").forEach((d) => {
    const on = set.has(d.dataset.wo);
    d.classList.toggle("cited", on);
    d.classList.remove("recalled");
    if (on) { d.setAttribute("r", 6); d.setAttribute("fill", "var(--cite)"); }
  });
  $$("#timeline .tl-ring").forEach((r, i) => { const on = set.has(r.dataset.ring); r.classList.toggle("go", on); if (on) r.style.animationDelay = `${(i % 6) * 0.2}s`; });
}
function scanning(on) { $("#tl-scan")?.classList.toggle("go", on); }
function citedIds(r) {
  const b = JSON.stringify(r.briefing || {}) + " " + (r.text || "");
  return [...new Set([...(b.match(WO_RE) || []), ...(r.evidence || []).flatMap((e) => e.wo_ids || [])])];
}

// ============================================================================ briefing tab
function renderBriefingTab(t) {
  const key = (h) => `${t.wo_id}:${h}`;
  $("#tab-body").innerHTML = `
    <div class="actions">
      <button class="btn primary" id="run">Compare repair advice <span aria-hidden="true">→</span></button>
      <span class="muted small">One repair. Two perspectives. See what past experience adds.</span>
    </div>
    <div class="compare">
      <div class="col day1">
        <div class="col-head"><div><h3><span class="badge-none">NO MEMORY</span> Starting from scratch</h3><div class="src" id="base-src">Generic advice from manuals and common practice</div></div></div>
        <div class="col-body" id="base-body"><p class="placeholder">General troubleshooting, without knowing what happened to this equipment before.</p></div>
      </div>
      <div class="col memory" id="mem-col">
        <div class="col-head">
          <div><h3><span class="badge-mem">HINDSIGHT</span> Greybeard</h3><div class="src">Learning from <span id="bank-name"></span></div></div>
          <div class="seg" id="horizon"><span class="seg-glider"></span>${state.horizons.map((h) => `<button data-h="${h.key}" class="${h.key === state.horizon ? "on" : ""}" title="Memory as of ${esc(h.label)}">${esc(h.label)}</button>`).join("")}</div>
        </div>
        <div class="col-body" id="mem-body"><p class="placeholder">Recalls this unit's history, the same model across the fleet, failed fixes, what changed since, and site rules, then reasons over them.</p></div>
        <div id="mem-evidence"></div>
      </div>
    </div>`;
  const seg = $("#horizon");
  const setBank = () => { const h = state.horizons.find((x) => x.key === state.horizon); $("#bank-name").textContent = h ? (h.key === "fleet" ? "the full repair history" : h.label) : ""; glide(seg, "button.on", ".seg-glider"); };
  requestAnimationFrame(setBank);
  $$("#horizon button").forEach((b) => b.addEventListener("click", () => {
    state.horizon = b.dataset.h; $$("#horizon button").forEach((x) => x.classList.toggle("on", x === b)); setBank(); applyHorizon();
    const c = state.cache[key(state.horizon)];
    if (c) paintMemory(c, false); else runMemory(t);
  }));
  $("#run").addEventListener("click", () => { runBaseline(t); runMemory(t); });
  if (state.cache[key("base")]) paintBaseline(state.cache[key("base")], false);
  if (state.cache[key(state.horizon)]) paintMemory(state.cache[key(state.horizon)], false);

  async function runBaseline(t) {
    $("#base-body").innerHTML = `<div class="stream-head"><span class="orbit"></span>Thinking without memory…</div><div class="skeleton" style="width:85%"></div><div class="skeleton"></div><div class="skeleton" style="width:70%"></div><div class="skeleton" style="width:90%"></div>`;
    try { const r = await api(`/api/tickets/${t.wo_id}/baseline`, { method: "POST" }); state.cache[key("base")] = r; if (state.selected === t.wo_id && state.tab === "briefing") paintBaseline(r, true); }
    catch (e) { if (state.selected !== t.wo_id || state.tab !== "briefing") return; $("#base-body").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
  }

  async function runMemory(t) {
    const h = state.horizon, col = $("#mem-col");
    col.classList.add("thinking"); scanning(true); Neural.burst(24);
    $("#mem-evidence").innerHTML = "";
    $("#mem-body").innerHTML = `<div class="stream-head"><span class="orbit"></span><span class="phase" id="phase">recall · ${esc(t.asset.id)}</span></div><div class="stream" id="stream"></div>`;
    const phases = [`recall · ${t.asset.id} history`, `recall · every ${t.asset.model} in the fleet`, "graph · linking entities across jobs", "temporal · what changed since", "reflect · applying directives", "reflect · writing the briefing"];
    let pi = 0; const ph = setInterval(() => { const el = $("#phase"); if (el) el.textContent = phases[Math.min(++pi, phases.length - 1)]; }, 2200);
    // Stream real recall hits while reflect thinks (only for the live fleet bank).
    if (h === "fleet") api(`/api/tickets/${t.wo_id}/recall`).then(async (r) => {
      const hits = [...r.asset, ...r.fleet].slice(0, 10);
      markRecalled(hits.flatMap((x) => x.wo_ids));
      for (const [i, hit] of hits.entries()) {
        const st = $("#stream"); if (!st) return;
        st.insertAdjacentHTML("afterbegin", `<div class="stream-card"><span class="type ${esc(hit.type)}">${esc(hit.type)}</span>${esc(hit.text)}</div>`);
        $$(".stream-card", st).slice(4).forEach((c) => c.classList.add("fade"));
        $$(".stream-card", st).slice(7).forEach((c) => c.remove());
        await sleep(650 + i * 60);
      }
    }).catch(() => {});
    try {
      const r = await api(`/api/tickets/${t.wo_id}/briefing?bank=${h}`, { method: "POST" });
      state.cache[key(h)] = r;
      if (state.horizon === h && state.selected === t.wo_id && state.tab === "briefing") paintMemory(r, true);
    } catch (e) { $("#mem-body").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
    finally { clearInterval(ph); col?.classList.remove("thinking"); scanning(false); }
  }

  function paintBaseline(r, animate) { $("#base-src").textContent = r.source || "Starting from scratch"; $("#base-body").innerHTML = briefingHTML(r.briefing, r.text); finishPaint($("#base-body"), animate); }
  function paintMemory(r, animate) {
    $("#mem-body").innerHTML = briefingHTML(r.briefing, r.text);
    const ev = r.evidence || [];
    $("#mem-evidence").innerHTML = `
      <details class="evidence-summary">
        <summary>Reasoned over ${ev.length} memories${r.mental_models?.length ? ` + ${r.mental_models.length} fleet knowledge page${r.mental_models.length > 1 ? "s" : ""}` : ""}${r.directives?.length ? ` · ${r.directives.length} directive${r.directives.length > 1 ? "s" : ""} applied` : ""}</summary>
        ${(r.mental_models || []).map((m) => `<div class="ev"><span class="type model">mental model</span>${esc(m.name)}</div>`).join("")}
        ${(r.directives || []).map((d) => `<div class="ev"><span class="type model">directive</span>${esc(d)}</div>`).join("")}
        ${ev.map((m) => `<div class="ev"><span class="type ${esc(m.type)}">${esc(m.type)}</span>${esc(m.text)} ${woChips(m.wo_ids)}</div>`).join("")}
      </details>`;
    finishPaint($("#mem-body"), animate);
    markCited(citedIds(r));
    if (animate) Neural.burst(30);
  }
}

function finishPaint(root, animate) {
  bindWo();
  const kids = [...root.children];
  if (animate && !REDUCED) {
    root.classList.add("reveal");
    kids.forEach((k, i) => (k.style.animationDelay = `${150 + i * 110}ms`));
    const hl = $(".headline-text", root);
    if (hl) { const full = hl.textContent; hl.textContent = ""; hl.parentElement.classList.add("caret"); let i = 0; const tick = () => { hl.textContent = full.slice(0, (i += 2)); if (i < full.length) setTimeout(tick, 12); else hl.parentElement.classList.remove("caret"); }; setTimeout(tick, 120); }
  }
  setTimeout(() => $$(".bar i", root).forEach((b) => (b.style.width = b.dataset.w + "%")), animate ? 500 : 30);
}

function briefingHTML(b, fallbackText) {
  if (!b || !Object.keys(b).length) return `<div class="markdown">${md(fallbackText || "No briefing returned.")}</div>`;
  const list = (arr) => (Array.isArray(arr) ? arr : []).filter(Boolean);
  const steps = (arr, cls, render) => `<ol class="steps ${cls}">${list(arr).map(render).join("")}</ol>`;
  let html = "";
  if (b.headline) html += `<div class="headline">${b.confidence ? `<span class="conf ${esc(b.confidence)}">${esc(b.confidence)}</span>` : ""}<span class="headline-text">${esc(b.headline)}</span></div>`;
  if (list(b.check_first).length) html += `<div class="block"><div class="block-title">Check first</div>${steps(b.check_first, "", (s) => `
      <li>${s.minutes ? `<span class="mins">~${esc(s.minutes)} min</span>` : ""}<div class="step-main">${esc(s.step)}</div>${s.why ? `<div class="step-why">${esc(s.why)}</div>` : ""}${woChips(s.evidence)}</li>`)}</div>`;
  if (list(b.superseded).length) html += `<div class="block"><div class="block-title time">Superseded: the equipment changed since</div>${steps(b.superseded, "superseded", (s) => `
      <li><div class="step-main"><s>${esc(s.old_advice)}</s></div><div class="step-why">${esc(s.why_obsolete)}</div>${woChips(s.evidence)}</li>`)}</div>`;
  if (list(b.avoid).length) html += `<div class="block"><div class="block-title warn">Don't repeat: tried before, didn't work</div>${steps(b.avoid, "avoid", (s) => `
      <li><div class="step-main">${esc(s.action)}</div><div class="step-why">${esc(s.why)}</div>${woChips(s.evidence)}</li>`)}</div>`;
  if (list(b.likely_causes).length) html += `<div class="block"><div class="block-title">Likely causes</div>${list(b.likely_causes).map((c) => {
      const p = Math.max(0, Math.min(100, Number(c.likelihood) || 0));
      return `<div class="cause"><div>${esc(c.cause)} ${woChips(c.evidence)}</div><div class="pct">${p}%</div><div class="bar"><i data-w="${p}"></i></div></div>`; }).join("")}</div>`;
  if (list(b.parts_to_carry).length) html += `<div class="block"><div class="block-title">Carry</div><ul class="plain">${list(b.parts_to_carry).map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
  if (list(b.site_notes).length) html += `<div class="block"><div class="block-title">Site notes</div><ul class="plain">${list(b.site_notes).map((p) => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
  if (list(b.call_if_stuck).length) html += `<div class="block"><div class="block-title">Call if stuck</div><ul class="plain">${list(b.call_if_stuck).map((p) => `<li><b>${esc(p.name)}</b>: ${esc(p.why)}</li>`).join("")}</ul></div>`;
  return html;
}

function bindWo() {
  $$(".wo").forEach((b) => (b.onclick = () => {
    const wo = b.dataset.wo;
    state.highlight = wo;
    const tl = state.timeline, j = tl?.jobs.find((x) => x.wo_id === wo);
    if (current() && j && j.asset_id === current().asset.id) switchTab("history");
    else if (j) toast(`${wo} is from ${j.asset_id}: ${j.root_cause}`);
  }));
  $$(".wo").forEach((b) => {
    b.onmouseenter = () => { const d = $(`#timeline .tl-dot[data-wo="${b.dataset.wo}"]`); if (d) { d.setAttribute("r", 8); } };
    b.onmouseleave = () => { const d = $(`#timeline .tl-dot[data-wo="${b.dataset.wo}"]`); if (d) d.setAttribute("r", d.classList.contains("cited") ? 6 : 4.6); };
  });
}

// ============================================================================ inspector
async function renderInspector(t) {
  $("#tab-body").innerHTML = `<div class="stream-head"><span class="orbit"></span>Running two recalls against Hindsight…</div><div class="skeleton"></div><div class="skeleton" style="width:70%"></div>`;
  scanning(true);
  try {
    const r = await api(`/api/tickets/${t.wo_id}/recall`);
    if (state.tab !== "inspector") return;
    markRecalled([...r.asset, ...r.fleet].flatMap((x) => x.wo_ids));
    const col = (title, sub, hits) => `<div class="lens"><div class="lens-head"><h3>${title}</h3><span class="muted small mono">${hits.length} hits</span></div><p class="muted small">${sub}</p>${hits.length ? hits.map((h, i) => `
      <div class="hit" style="animation-delay:${i * 60}ms"><span class="type ${esc(h.type)}">${esc(h.type)}</span>${esc(h.text)}
        <div class="hit-meta">${h.when ? `<span>${esc(h.when.slice(0, 10))}</span>` : ""}${woChips(h.wo_ids)}${(h.tags || []).slice(0, 4).map((g) => `<span class="tagchip">${esc(g)}</span>`).join("")}</div></div>`).join("")
      : '<p class="muted">No memories. This is what a brand-new asset looks like, and why the fleet lens matters.</p>'}</div>`;
    $("#tab-body").innerHTML = `
      <div class="query-box"><b>recall</b>("${esc(r.query)}")<br/>semantic + BM25 + entity graph + temporal · fused with reciprocal rank + cross-encoder rerank</div>
      <div class="inspector">
        ${col("This unit", `tags: asset:${esc(t.asset.id)} · any_strict`, r.asset)}
        ${col("The fleet", `tags: model:${esc(t.asset.model.toLowerCase().replace(/[^a-z0-9]+/g, "-"))} OR site:${esc(t.asset.site)}`, r.fleet)}
      </div>`;
    bindWo();
  } catch (e) { $("#tab-body").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
  finally { scanning(false); }
}

// ============================================================================ history
async function renderHistory(t) {
  $("#tab-body").innerHTML = `<div class="skeleton"></div><div class="skeleton" style="width:80%"></div>`;
  const rows = await api(`/api/assets/${t.asset.id}/history`);
  if (state.tab !== "history") return;
  const words = rows.reduce((n, r) => n + (r.notes || "").split(/\s+/).length, 0);
  $("#tab-body").innerHTML = `
    <div class="callout"><span class="num" data-count>0</span><div>entries (~<b>${words.toLocaleString()} words</b>) for this unit alone, and none of the other ${esc(t.asset.model)} units. This is what ${esc(t.tech.name.split(" ")[0])} would otherwise scroll through on a phone in a 41°C plant room. <span style="color:var(--cite)">Violet rows</span> are cited by Greybeard.</div></div>
    <div class="history">${rows.map((r) => `
      <div class="hrow ${r.wo_id === state.highlight ? "hl" : ""}" id="h-${r.wo_id}">
        <div><div class="mono">${esc(r.wo_id)}</div><div class="muted small">${esc(r.opened_at.slice(0, 10))}</div></div>
        <div class="outcome ${esc(r.outcome)}">${esc(r.outcome.replace("_", " "))}</div>
        <div class="muted small">${esc(r.technician)}${r.alarm_code ? ` · <span class="mono">${esc(r.alarm_code)}</span>` : ""}</div>
        <div><b>${esc(r.symptom)}</b><div class="muted">${esc(r.notes)}</div></div>
      </div>`).join("") || '<p class="muted" style="padding:16px">No entries. Brand-new asset.</p>'}</div>`;
  countUp($(".callout .num"), rows.length, 900);
  if (state.highlight) setTimeout(() => document.getElementById(`h-${state.highlight}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
}

// ============================================================================ close-out
function renderCloseout(t) {
  if (t.status === "closed") {
    $("#tab-body").innerHTML = `<div class="retained"><svg class="check" viewBox="0 0 44 44"><circle cx="22" cy="22" r="20"/><path d="M13 22.5l6 6 12-13"/></svg><div><b>Closed and retained into memory.</b><div class="muted small">Hindsight is extracting facts and consolidating this job into the fleet's observations. Open another ticket on the same model and watch the briefing change.</div></div></div>
      <pre class="query-box" style="white-space:pre-wrap;margin-top:16px">${esc(JSON.stringify(t.closeout, null, 2))}</pre>`;
    return;
  }
  const demo = DEMO_CLOSEOUTS[t.wo_id];
  $("#tab-body").innerHTML = `
    <form class="form" id="co">
      <div class="field"><label>Outcome</label>
        <div class="seg" id="outcome"><span class="seg-glider"></span>${[["fixed", "Fixed"], ["false_alarm", "False alarm"], ["not_fixed", "Not fixed / came back"]].map(([k, l], i) => `<button type="button" data-v="${k}" class="${i === 0 ? "on" : ""}">${l}</button>`).join("")}</div></div>
      <div class="field"><label>Root cause</label><input name="root_cause" required minlength="3" placeholder="What was actually wrong?" /></div>
      <div class="field"><label>What you did, including anything that didn't work <button type="button" class="mic" id="mic">● Dictate</button></label>
        <textarea name="notes" required minlength="10" placeholder="Readings, steps, what worked, what didn't…"></textarea></div>
      <div class="row2">
        <div class="field"><label>Parts used (comma separated)</label><input name="parts" /></div>
        <div class="field"><label>Downtime (hours)</label><input name="downtime_hours" type="number" step="0.5" min="0" value="0" /></div>
      </div>
      <div class="field"><label>Was Greybeard's briefing right?</label>
        <div class="seg" id="helpful"><span class="seg-glider"></span><button type="button" data-v="true" class="on">Yes, it helped</button><button type="button" data-v="false">No, it was wrong</button><button type="button" data-v="">Didn't use it</button></div></div>
      <div class="field"><label>Feedback for Greybeard (optional)</label><input name="briefing_feedback" /></div>
      <div class="actions" style="margin:4px 0 0"><button class="btn primary" type="submit">Close job &amp; teach Greybeard</button>${demo ? '<button class="btn" type="button" id="fill">Fill demo close-out</button>' : ""}</div>
    </form>`;
  const seg = (id) => { const el = $(`#${id}`); requestAnimationFrame(() => glide(el, "button.on", ".seg-glider")); $$(`#${id} button`).forEach((b) => b.addEventListener("click", () => { $$(`#${id} button`).forEach((x) => x.classList.toggle("on", x === b)); glide(el, "button.on", ".seg-glider"); })); };
  seg("outcome"); seg("helpful");
  const f = $("#co");
  $("#fill")?.addEventListener("click", async () => {
    $$("#outcome button").forEach((b) => b.classList.toggle("on", b.dataset.v === demo.outcome)); glide($("#outcome"), "button.on", ".seg-glider");
    const type = async (el, text) => { el.value = ""; for (let i = 0; i <= text.length; i += 4) { el.value = text.slice(0, i); await sleep(4); } el.value = text; };
    await type(f.root_cause, demo.root_cause); await type(f.notes, demo.notes);
    f.parts.value = demo.parts; f.downtime_hours.value = demo.downtime_hours; f.briefing_feedback.value = demo.briefing_feedback;
  });
  setupDictation($("#mic"), f.notes);
  f.addEventListener("submit", async (e) => {
    e.preventDefault();
    const helpful = $("#helpful .on").dataset.v;
    const body = {
      outcome: $("#outcome .on").dataset.v, root_cause: f.root_cause.value.trim(), notes: f.notes.value.trim(),
      parts: f.parts.value.split(",").map((s) => s.trim()).filter(Boolean), downtime_hours: Number(f.downtime_hours.value || 0),
      briefing_helpful: helpful === "" ? null : helpful === "true", briefing_feedback: f.briefing_feedback.value.trim() || null,
    };
    const btn = f.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "Retaining into memory…";
    try {
      await api(`/api/tickets/${t.wo_id}/close`, { method: "POST", body: JSON.stringify(body) });
      f.classList.add("absorb"); Neural.burst(40);
      await sleep(850);
      refreshStats(true);
      toast(`${t.wo_id} retained. Greybeard just learned something.`);
      Object.keys(state.cache).forEach((k) => { if (!k.startsWith(t.wo_id)) delete state.cache[k]; });
      state.timeline = null;
      await loadTickets(); renderWork(); switchTab("closeout");
      setTimeout(() => refreshStats(true), 6000);
    } catch (err) { btn.disabled = false; btn.textContent = "Close job & teach Greybeard"; toast(err.message); }
  });
}

function setupDictation(btn, target) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { btn.style.display = "none"; return; }
  let rec = null;
  btn.addEventListener("click", () => {
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = "en-IN"; rec.continuous = true; rec.interimResults = false;
    rec.onresult = (e) => { for (let i = e.resultIndex; i < e.results.length; i++) target.value += (target.value ? " " : "") + e.results[i][0].transcript; };
    rec.onend = () => { rec = null; btn.classList.remove("rec"); btn.textContent = "● Dictate"; };
    rec.start(); btn.classList.add("rec"); btn.textContent = "■ Stop";
  });
}

// ============================================================================ knowledge
const KB_ICON = { "failure-patterns": "⚙", "failed-fixes": "✕", "site-playbook": "⌂", "expertise-map": "☍" };
async function loadKnowledge() {
  $("#kb").innerHTML = [0, 1, 2, 3].map(() => `<article class="kb" style="animation-delay:0ms"><div class="kb-body"><div class="skeleton" style="width:50%"></div><div class="skeleton"></div><div class="skeleton" style="width:85%"></div><div class="skeleton" style="width:70%"></div></div></article>`).join("");
  try {
    const models = await api("/api/knowledge");
    $("#kb").innerHTML = models.map((m, i) => `
      <article class="kb" style="animation-delay:${i * 90}ms">
        <div class="kb-head"><div style="display:flex;align-items:center"><span class="kb-icon">${KB_ICON[m.id] || "◆"}</span><h3>${esc(m.name)}</h3></div><button class="btn" data-refresh="${esc(m.id)}">Refresh</button></div>
        <div class="kb-body markdown">${m.content ? md(m.content) : '<p class="muted">Hindsight is writing this page…</p><div class="skeleton"></div><div class="skeleton" style="width:70%"></div>'}</div>
        <div class="kb-foot"><span>${m.last_refreshed_at ? "Rewritten " + new Date(m.last_refreshed_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "Not yet generated"}</span>${m.is_stale ? "<span>new memories pending</span>" : '<span class="live">live</span>'}</div>
      </article>`).join("") || '<p class="muted">Knowledge is still being prepared. Return here once the fleet memory is ready.</p>';
    $$("[data-refresh]").forEach((b) => b.addEventListener("click", async () => {
      b.disabled = true; b.textContent = "Rewriting…";
      try { await api(`/api/knowledge/${b.dataset.refresh}/refresh`, { method: "POST" }); toast("Refresh queued. Hindsight is rewriting the page."); setTimeout(loadKnowledge, 9000); }
      catch (e) { toast(e.message); b.disabled = false; b.textContent = "Refresh"; }
    }));
    bindWo();
  } catch (e) { $("#kb").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
  try {
    const obs = await api("/api/observations");
    $("#observations").innerHTML = obs.slice(0, 16).map((o, i) => `<div class="hit" style="animation-delay:${i * 50}ms"><span class="type observation">observation</span><span class="markdown">${md(o.text)}</span></div>`).join("") || '<p class="muted">No observations yet.</p>';
    bindWo();
  } catch {}
}

// ============================================================================ ask
async function ask(q) {
  const chat = $("#chat");
  chat.insertAdjacentHTML("beforeend", `<div class="msg user">${esc(q)}</div>`);
  const id = "a" + Date.now();
  chat.insertAdjacentHTML("beforeend", `<div class="msg bot" id="${id}"><div class="typing"><i></i><i></i><i></i></div> <span class="muted small">recalling and reflecting over fleet memory…</span></div>`);
  $("#" + id).scrollIntoView({ behavior: "smooth", block: "end" });
  Neural.burst(20);
  try {
    const r = await api("/api/ask", { method: "POST", body: JSON.stringify({ question: q }) });
    $("#" + id).innerHTML = `<div class="markdown">${md(r.answer)}</div>${r.evidence?.length ? `<details class="evidence-summary" style="margin:12px -16px -14px;border-radius:0 0 16px 16px"><summary>Based on ${r.evidence.length} memories</summary>${r.evidence.map((m) => `<div class="ev"><span class="type ${esc(m.type)}">${esc(m.type)}</span>${esc(m.text)}</div>`).join("")}</details>` : ""}`;
    bindWo();
  } catch (e) { $("#" + id).innerHTML = `<div class="error">${esc(e.message)}</div>`; }
}

// ============================================================================ bootstrap (first run)
async function checkBootstrap() {
  const box = $("#bootstrap");
  if (!box) return;
  let st;
  try { st = await api("/api/bootstrap/status"); } catch { return; }
  if (!st.configured) {
    box.innerHTML = `<div class="boot err"><div><b>Memory isn't connected.</b><div class="muted">The owner is connecting the live memory service. You can explore the jobs and repair history in the meantime.</div></div></div>`;
    return;
  }
  if (!st.reachable) {
    box.innerHTML = `<div class="boot err"><div><b>Can't reach Hindsight.</b><div class="muted">The memory service is temporarily unavailable. You can still explore the repair history.</div></div></div>`;
    return;
  }
  if (st.documents === 0 && st.pending === 0 && st.setup_allowed === false) {
    box.innerHTML = `<div class="boot"><div><b>Fleet memory is being prepared.</b><div class="muted">Explore the sample jobs and their repair history while the owner completes setup.</div></div></div>`;
    return;
  }
  if (st.documents === 0 && st.pending === 0) {
    box.innerHTML = `<div class="boot"><div><b>Fleet memory is empty.</b><div class="muted">Load 18 months of work orders into Hindsight. Takes about a minute to queue, then Hindsight extracts and consolidates in the background.</div></div><button class="btn primary" id="boot-go">Prepare fleet memory</button></div>`;
    $("#boot-go").addEventListener("click", async (e) => {
      e.target.disabled = true; e.target.textContent = "Queuing 18 months of jobs…"; Neural.burst(40);
      try { await api("/api/bootstrap?snapshots=true", { method: "POST" }); toast("History queued. Hindsight is learning."); pollBootstrap(); }
      catch (err) { e.target.disabled = false; e.target.textContent = "Prepare fleet memory"; toast(err.message); }
    });
    return;
  }
  if (st.pending > 0) pollBootstrap();
}

async function pollBootstrap() {
  const box = $("#bootstrap"), total = 201;
  const paint = (st) => {
    const pct = Math.min(100, Math.round((st.documents / total) * 100));
    box.innerHTML = `<div class="boot"><div style="flex:1"><b>Hindsight is learning the fleet…</b><div class="muted">${st.documents} of ${total} jobs extracted · ${st.observations} patterns consolidated · ${st.pending} operations pending</div><div class="boot-bar"><i style="width:${pct}%"></i></div></div></div>`;
  };
  for (;;) {
    let st; try { st = await api("/api/bootstrap/status"); } catch { await sleep(5000); continue; }
    paint(st); refreshStats();
    if (st.pending === 0 && st.documents > 0) { box.innerHTML = ""; toast("Memory ready. Pick a job."); return; }
    await sleep(6000);
  }
}

// ============================================================================ boot
function switchView(v) {
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
  glide($(".nav"), ".nav-btn.active", ".nav-glider");
  $$(".view").forEach((el) => el.classList.toggle("active", el.id === `view-${v}`));
  if (v === "knowledge") loadKnowledge();
  if (v === "dispatch") requestAnimationFrame(moveInk);
}

async function boot() {
  $$(".nav-btn").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
  requestAnimationFrame(() => glide($(".nav"), ".nav-btn.active", ".nav-glider"));
  addEventListener("resize", () => { glide($(".nav"), ".nav-btn.active", ".nav-glider"); moveInk(); });
  $$("#ask-suggest .chip").forEach((c) => c.addEventListener("click", () => ask(c.textContent)));
  $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); const v = $("#ask-input").value.trim(); if (v) { $("#ask-input").value = ""; ask(v); } });
  $("#reset-demo").addEventListener("click", async () => { await api("/api/demo/reset", { method: "POST" }); state.cache = {}; await loadTickets(); if (state.selected) renderWork(); toast("Demo board reset"); });
  $("#home").addEventListener("click", (e) => { e.preventDefault(); location.reload(); });
  $$(".hero [data-count]").forEach((el, i) => setTimeout(() => countUp(el, el.dataset.to, 1600), 400 + i * 120));
  // Headlines stay stable so they remain readable with pointer and keyboard input.
  state.horizons = await api("/api/horizons");
  await loadTickets();
  $("#start").addEventListener("click", () => { selectTicket(state.tickets[0]?.wo_id); $("#work").scrollIntoView({behavior: REDUCED ? "instant" : "smooth", block:"start"}); });
  refreshStats(); setInterval(refreshStats, 15000);
  checkBootstrap();
}

boot().catch(() => toast("The workspace could not load. Please refresh and try again."));
