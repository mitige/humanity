/* =====================================================================
 * Humanity — "Instrument" dashboard logic.
 * Vanilla JS, no framework, no build, no CDNs. Same-origin fetch.
 *
 * FUNCTIONAL NOTE: this drives a good-faith THEORETICAL attempt at the
 * mechanisms major scientific theories of consciousness propose. Nothing
 * here implies the agent IS conscious. All "introspective"/"moment" text
 * is generated from internal variables exposed by the API (AST/HOT).
 * ===================================================================== */
(() => {
  "use strict";

  // routes are mounted at the app root; UI is served from /ui -> use "../"
  const API = "..";
  const POLL_MS = 350;
  const HIST = 60;            // sparkline history length
  const STREAM_MAX = 48;      // stream bars kept client-side
  const IGNITION_HISTORY_MAX = 120;
  const SOURCE_COLORS = {
    perception: "#d8a84e", memory: "#7fb5a6", self: "#9b86c8",
    emotion: "#c87463", goal: "#80a85e", imagination: "#739bc5",
    dream: "#755c9f", social: "#c98ba7", inner_speech: "#d0b674",
    wandering: "#69a9ad", language: "#b69462", unknown: "#7b7870",
  };
  const HORIZON_FLAGS = [
    "phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
    "vector_memory_enabled", "td_learning_enabled", "mind_wandering_enabled",
    "world_dynamics_enabled", "tasks_enabled",
  ];

  // ---------- helpers ----------
  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, html) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  };
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => {
    const n = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  };
  const clamp01 = (x) => Math.max(0, Math.min(1, x));
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const num = (x) => (typeof x === "number" && isFinite(x) ? x : 0);
  const f3 = (x) => num(x).toFixed(3);
  const f2 = (x) => num(x).toFixed(2);
  const f0 = (x) => Math.round(num(x)).toString();
  const pctTxt = (x) => (clamp01(x) * 100).toFixed(0) + "%";
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function api(path, opts) {
    const res = await fetch(`${API}/${path}`, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    const ct = res.headers.get("content-type") || "";
    return ct.includes("application/json") ? res.json() : null;
  }
  const postJSON = (path, body) =>
    api(path, { method: "POST", body: JSON.stringify(body || {}) });

  // ---------- settings persistence (localStorage) ----------
  // The Settings panel's choices persist across reloads under one key, so the
  // instrument stays as the user last set it instead of resetting to hardcoded
  // defaults every load. All access is guarded: if localStorage is unavailable
  // (private mode) we silently fall back to defaults and never throw.
  const SETTINGS_KEY = "humanity.settings";
  function loadSettings() {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (e) { return null; }
  }
  function saveSettings(obj) {
    try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(obj)); } catch (e) { /* ignore */ }
  }
  function persistSetting(patch) {
    saveSettings({ ...(loadSettings() || {}), ...patch });
  }

  // ---------- state ----------
  let running = false;
  let pollTimer = null;
  let refreshInFlight = false;
  let refreshQueued = false;
  let refreshDrainPromise = null;
  let stepInFlight = false;
  let lastGrid = 12;
  let lastTick = -1;
  // most recent CycleTrace (from POST /tick) — holds Phase-2 imagination/sleep detail
  let lastTrace = null;

  // client-side metric history for sparklines
  const HISTORY = {};
  const pushHist = (key, v) => {
    const a = HISTORY[key] || (HISTORY[key] = []);
    a.push(num(v));
    if (a.length > HIST) a.shift();
  };
  // client-side stream of ConsciousMoment {ignited, awareness_level}
  let streamData = [];
  let ignitionHistory = [];
  let memoryGraphCache = { nodes: [], edges: [] };
  let lastMemoryGraphTick = -1;
  let memoryGraphRequest = null;
  let memoryGraphSelection = -1;
  let horizonGeneration = 0;

  function resetHorizonClientState() {
    horizonGeneration += 1;
    for (const key in HISTORY) delete HISTORY[key];
    streamData = [];
    ignitionHistory = [];
    memoryGraphCache = { nodes: [], edges: [] };
    lastMemoryGraphTick = -1;
    memoryGraphRequest = null;
    memoryGraphSelection = -1;
    lastTrace = null;
    lastTick = -1;

    const searchResults = $("#memory-search-results");
    if (searchResults) searchResults.replaceChildren();
    const searchButton = $("#memory-search-form button[type='submit']");
    if (searchButton) searchButton.disabled = false;
    const tooltip = $("#memory-graph-tooltip");
    if (tooltip) tooltip.hidden = true;
    const selection = $("#memory-graph-selection");
    if (selection) selection.textContent = "";

    renderStream(null);
    renderHorizonStream([]);
    renderIgnitionDynamics(null, -1);
    drawMemoryGraph(memoryGraphCache);
    renderHorizon(null, null);
  }

  // ============================================================
  //  STATUS + THEME
  // ============================================================
  function setStatus(kind, text) {
    const pill = $("#status-pill");
    pill.className = "pill pill-" + kind;
    $("#status-label").textContent = text;
  }
  function setRunningUI(isRunning) {
    running = isRunning;
    $("#btn-start").disabled = isRunning;
    $("#btn-pause").disabled = !isRunning;
    setStatus(isRunning ? "running" : "idle", isRunning ? "Running" : "Paused");
  }

  (function initTheme() {
    const saved = localStorage.getItem("cws-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    $("#btn-theme").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("cws-theme", next);
      if (currentWorldSnap) drawWorld(currentWorldSnap); // re-tint canvas
      renderIgnitionDynamics(null, lastTick);
      drawMemoryGraph(memoryGraphCache);
    });
  })();

  // read CSS vars so the canvas matches the active theme
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // ============================================================
  //  WORLD CANVAS
  // ============================================================
  let currentWorldSnap = null;
  let worldCursor = { x: null, y: null };
  let worldStimulusPending = false;

  function drawWorldCursor(ctx, cell, grid) {
    if (worldCursor.x == null || worldCursor.y == null) {
      worldCursor = { x: Math.floor(grid / 2), y: Math.floor(grid / 2) };
    }
    worldCursor.x = clamp(Math.round(worldCursor.x), 0, grid - 1);
    worldCursor.y = clamp(Math.round(worldCursor.y), 0, grid - 1);
    const inset = Math.max(2, cell * 0.08);
    const x = worldCursor.x * cell + inset;
    const y = worldCursor.y * cell + inset;
    const size = Math.max(1, cell - inset * 2);
    ctx.save();
    ctx.fillStyle = cssVar("--accent");
    ctx.globalAlpha = 0.08;
    ctx.fillRect(x, y, size, size);
    ctx.globalAlpha = 0.95;
    ctx.strokeStyle = cssVar("--accent-bright");
    ctx.lineWidth = Math.max(1.5, cell * 0.045);
    ctx.setLineDash([Math.max(3, cell * 0.12), Math.max(2, cell * 0.08)]);
    ctx.strokeRect(x, y, size, size);
    ctx.restore();
  }

  function mapWorldPointToGrid(ev) {
    const canvas = $("#world-canvas");
    const rect = canvas.getBoundingClientRect();
    const grid = Math.max(1, Math.round(lastGrid || 12));
    const relativeX = rect.width ? (ev.clientX - rect.left) / rect.width : 0;
    const relativeY = rect.height ? (ev.clientY - rect.top) / rect.height : 0;
    return {
      x: clamp(Math.floor(relativeX * grid), 0, grid - 1),
      y: clamp(Math.floor(relativeY * grid), 0, grid - 1),
    };
  }

  function drawWorld(snapshot) {
    currentWorldSnap = snapshot;
    const canvas = $("#world-canvas");
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const kindColor = {
      food: cssVar("--pos"),
      hazard: cssVar("--neg"),
      tool: cssVar("--cool"),
      curio: cssVar("--curio"),
    };
    const lineCol = cssVar("--line");
    const agentCol = cssVar("--accent");
    const bgInset = cssVar("--bg-inset");

    const grid = num(snapshot && snapshot.grid_size) || lastGrid || 12;
    lastGrid = grid;
    const cell = W / grid;

    // hairline grid
    ctx.strokeStyle = lineCol;
    ctx.globalAlpha = 0.5;
    ctx.lineWidth = 1;
    for (let i = 0; i <= grid; i++) {
      const p = Math.round(i * cell) + 0.5;
      ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, H); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(W, p); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    const center = (c) => c * cell + cell / 2;
    const agent = (snapshot && snapshot.agent) ||
      { x: Math.floor(grid / 2), y: Math.floor(grid / 2), energy: 0 };

    // perception radius ring
    const radius = num(snapshot && snapshot.radius) || 3;
    ctx.beginPath();
    ctx.arc(center(agent.x), center(agent.y), (radius + 0.5) * cell, 0, Math.PI * 2);
    ctx.strokeStyle = agentCol;
    ctx.globalAlpha = 0.22;
    ctx.setLineDash([4, 6]);
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // objects: size hints novelty, opacity hints danger
    const objs = (snapshot && snapshot.objects) || [];
    objs.forEach((o) => {
      const color = kindColor[o.kind] || cssVar("--ink-faint");
      const novelty = clamp01(num(o.novelty));
      const danger = clamp01(num(o.danger));
      const r = cell * (0.18 + 0.2 * novelty);
      const alpha = 0.4 + 0.5 * Math.max(danger, o.kind === "hazard" ? 0.35 : 0.18);
      ctx.globalAlpha = Math.min(1, alpha);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(center(o.x), center(o.y), r, 0, Math.PI * 2);
      ctx.fill();
      if (danger > 0.4) {
        ctx.globalAlpha = 0.85;
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = kindColor.hazard;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    });

    // agent marker — a ringed dot, sober
    const ax = center(agent.x), ay = center(agent.y);
    ctx.beginPath();
    ctx.arc(ax, ay, cell * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = agentCol;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = bgInset;
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(ax, ay, cell * 0.13, 0, Math.PI * 2);
    ctx.fillStyle = bgInset;
    ctx.fill();

    // The selected cell remains visible for both pointer and keyboard users.
    drawWorldCursor(ctx, cell, grid);
  }

  // ============================================================
  //  HERO — CONSCIOUS MOMENT + STREAM
  // ============================================================
  function renderConsciousness(c) {
    if (!c) return;
    const hero = $(".panel-hero");
    const ws = c.workspace || {};
    const cm = c.conscious_moment || {};
    const ast = c.attention_schema || {};
    const meta = c.metacognition || {};
    const integ = c.integration || {};

    const ignited = !!(cm.ignited != null ? cm.ignited : ws.ignited);
    hero.classList.toggle("is-ignited", ignited);

    $("#ignition-state").textContent = ignited ? "Global access" : "Subliminal";
    $("#ignition-sub").textContent = ignited
      ? "global access — conscious (content broadcast)"
      : "present but subliminal (weakly conscious)";

    // ignition gate: score vs effective threshold (GET /agent/workspace)
    renderIgnitionGate(ws);

    const contents = cm.contents || ws.winner_content || "—";
    const q = $("#moment-contents");
    if (q.textContent !== contents) {
      q.textContent = contents;
      q.classList.remove("flash"); void q.offsetWidth; q.classList.add("flash");
    }

    const aw = num(cm.awareness_level != null ? cm.awareness_level : ast.awareness_level);
    $("#aw-fill").style.width = pctTxt(aw);
    $("#aw-val").textContent = f3(aw);

    const val = num(cm.valence);
    // bipolar meter: -1..1 mapped to half-widths from center
    const vf = $("#val-fill");
    const half = clamp01(Math.abs(val)) * 50;
    if (val >= 0) { vf.style.left = "50%"; vf.style.width = half + "%"; }
    else { vf.style.left = (50 - half) + "%"; vf.style.width = half + "%"; }
    vf.style.background = val >= 0 ? cssVar("--pos") : cssVar("--neg");
    $("#val-val").textContent = (val >= 0 ? "+" : "") + f2(val);

    const phi = num(cm.phi_proxy != null ? cm.phi_proxy : integ.phi_proxy);
    $("#phi-fill").style.width = pctTxt(phi);
    $("#phi-val").textContent = f3(phi);

    // AST panel — aware_of is ALWAYS populated (graded awareness). Render the
    // real dominant content; dim it when subliminal, full accent when ignited.
    const awareEl = $("#ast-aware");
    awareEl.textContent = ast.aware_of || "—";
    awareEl.classList.toggle("aware-conscious", ignited);
    awareEl.classList.toggle("aware-subliminal", !ignited);
    awareEl.style.opacity = (0.55 + 0.45 * clamp01(aw)).toFixed(2);
    $("#ast-stab-fill").style.width = pctTxt(num(ast.stability));
    $("#ast-stab-val").textContent = f3(ast.stability);
    $("#ast-attributed").textContent = ast.attributed_self || "—";

    // HOT panel — gauges
    setGauge("#g-meta", "#meta-conf-val", num(meta.meta_confidence));
    setGauge("#g-perc", "#perc-rel-val", num(meta.perception_reliability));
    setGauge("#g-pred", "#pred-rel-val", num(meta.prediction_reliability));
    $("#hot-report").textContent = meta.higher_order_report || "—";
  }

  // ignition gate — ignition_score vs effective_threshold (GET /agent/workspace).
  // Shows how close the system sits to conscious access; marker = effective cutoff.
  function renderIgnitionGate(ws) {
    if (!ws) return;
    const score = clamp01(num(ws.ignition_score));
    const eff = clamp01(num(ws.effective_threshold != null ? ws.effective_threshold : ws.threshold));
    const fill = $("#ig-fill");
    if (fill) {
      fill.style.width = (score * 100).toFixed(1) + "%";
      fill.classList.toggle("over", score >= eff);
    }
    const thr = $("#ig-thresh");
    if (thr) thr.style.left = (eff * 100).toFixed(1) + "%";
    if ($("#ig-score")) $("#ig-score").textContent = f3(score);
    if ($("#ig-eff")) $("#ig-eff").textContent = f3(eff);
  }

  // arousal / vigilance bar — GET /state.arousal (or /metrics), baseline marker.
  function renderArousal(arousal, baseline) {
    const a = clamp01(num(arousal));
    const fill = $("#arousal-fill");
    if (fill) fill.style.width = (a * 100).toFixed(1) + "%";
    if ($("#arousal-val")) $("#arousal-val").textContent = f3(a);
    const mark = $("#arousal-baseline-mark");
    if (mark && baseline != null) mark.style.left = (clamp01(num(baseline)) * 100).toFixed(1) + "%";
  }

  // half-circle gauge: dasharray 132 ≈ arc length
  function setGauge(pathSel, valSel, v) {
    const len = 132;
    $(pathSel).style.strokeDashoffset = (len * (1 - clamp01(v))).toFixed(1);
    $(valSel).textContent = f2(v);
  }

  function renderWorkspace(ws) {
    if (!ws) return;
    const box = $("#coalitions");
    // effective (arousal-modulated, homeostatic) cutoff — the live bar the
    // ignition_score must clear. Falls back to the nominal threshold.
    const threshold = clamp01(
      num(ws.effective_threshold != null ? ws.effective_threshold : ws.threshold) || 0.30
    );

    // keep the threshold line element, rebuild coalition rows
    box.querySelectorAll(".coalition").forEach((n) => n.remove());

    $("#ws-broadcast").textContent = f3(ws.broadcast_strength);
    // aware_of is always populated now: always show the dominant content.
    // dim it when subliminal (not ignited) to reflect graded awareness.
    const winnerEl = $("#ws-winner");
    winnerEl.textContent = ws.winner_content
      ? (ws.winner_source ? ws.winner_source + " · " : "") + ws.winner_content
      : "empty perceptual field (no content available)";
    winnerEl.classList.toggle("subliminal", !ws.ignited);
    $("#threshold-val").textContent = f3(threshold);

    // mirror arousal + ignition gate from the same workspace payload
    renderArousal(ws.arousal, configValue("arousal_baseline"));
    renderIgnitionGate(ws);

    const coalitions = (ws.competition || []).slice();
    // sort descending by activation for a clean ranked readout
    coalitions.sort((a, b) => num(b.activation) - num(a.activation));
    const maxAct = Math.max(0.001, ...coalitions.map((c) => num(c.activation)));

    const frag = document.createDocumentFragment();
    coalitions.forEach((c) => {
      // the dominant coalition is always marked; "winner" (full accent) only
      // when ignited, "dominant" (dimmed accent) when present-but-subliminal.
      const isDominant = c.source === ws.winner_source;
      const cls = isDominant ? (ws.ignited ? " winner" : " dominant") : "";
      const row = el("div", "coalition" + cls);
      const label = el("div", "co-label",
        `<span class="co-src">${esc(c.source)}</span>${esc(c.content || "")}`);
      const barWrap = el("div", "co-bar");
      const fill = el("div", "co-fill");
      // scale bar width to the strongest activation so differences read clearly
      fill.style.width = (clamp01(num(c.activation) / maxAct) * 100).toFixed(1) + "%";
      barWrap.appendChild(fill);
      const val = el("div", "co-val", f3(c.activation));
      row.appendChild(label); row.appendChild(barWrap); row.appendChild(val);
      frag.appendChild(row);
    });
    box.appendChild(frag);

    // place threshold line across the bar column.
    // The coalition bars show softmax SHARES (scaled to maxAct) — a different
    // scale from the absolute ignition_score the effective_threshold gates.
    // The canonical score-vs-threshold comparison lives in the hero ignition
    // gate; here we mark the effective cutoff as a direct fraction of the bar
    // area (0..1), a sober homeostatic reference that drifts with arousal.
    const line = $("#threshold-line");
    const barFrac = clamp01(threshold);
    // 124px label + 10px gap = 134px offset, bar then flexes; value col 44px + 10px gap.
    line.style.left = `calc(134px + (100% - 134px - 54px) * ${barFrac})`;
  }

  function renderStream(moments) {
    if (Array.isArray(moments) && moments.length) {
      streamData = moments.slice(-STREAM_MAX);
    }
    const track = $("#stream-track");
    track.innerHTML = "";
    const frag = document.createDocumentFragment();
    streamData.forEach((m) => {
      const bar = el("div", "spark" + (m.ignited ? " ignited" : ""));
      const aw = clamp01(num(m.awareness_level));
      bar.style.height = (10 + aw * 30).toFixed(0) + "px";
      bar.title = `t${num(m.tick)} · arousal ${f2(m.awareness_level)} · Φ ${f2(m.phi_proxy)}` +
        (m.contents ? `\n${m.contents}` : "");
      frag.appendChild(bar);
    });
    track.appendChild(frag);
    track.scrollLeft = track.scrollWidth;
  }

  // ============================================================
  //  METRICS STRIP (sparklines)
  // ============================================================
  // [key, label, tone, formatter, normalizer(value->0..1 for spark scaling)]
  const METRIC_DEFS = [
    ["phi_proxy", "Φ proxy", "accent", f3, (v) => clamp01(v)],
    ["arousal", "Arousal / vigilance", "cool", f3, (v) => clamp01(v)],
    ["free_energy", "Free energy", "neg", f3, null],   // can be negative; auto-scaled
    ["prediction_error", "Prediction err.", "neg", f3, (v) => clamp01(v)],
    ["self_coherence", "Self-coherence", "pos", f3, (v) => clamp01(v)],
    ["meta_confidence", "Meta-confidence", "accent", f3, (v) => clamp01(v)],
    ["energy", "Energy", "pos", f2, null],
    ["phi_causal", "Causal Φ", "accent", f3, null],
    ["vfe", "Variational free E.", "neg", f3, null],
    ["wandering_occupancy", "Default-mode occupancy", "cool", f3, (v) => clamp01(v)],
    ["task_progress", "Task progress", "pos", f3, (v) => clamp01(v)],
  ];

  function ensureMetricCells() {
    const grid = $("#metric-grid");
    if (grid.childElementCount) return;
    METRIC_DEFS.forEach(([key, label, tone]) => {
      const cell = el("div", "metric-cell tone-" + tone);
      cell.dataset.key = key;
      cell.innerHTML =
        `<div class="mc-top"><span class="mc-label">${esc(label)}</span>` +
        `<span class="mc-val" data-val>—</span></div>` +
        `<svg class="mc-spark" viewBox="0 0 100 26" preserveAspectRatio="none">` +
        `<path class="area" data-area></path><path data-line></path></svg>`;
      grid.appendChild(cell);
    });
  }

  function sparkPath(values) {
    // auto-scale to min/max of the window so any range (incl. negatives) reads
    const n = values.length;
    if (n === 0) return { line: "", area: "" };
    let lo = Math.min(...values), hi = Math.max(...values);
    if (hi - lo < 1e-9) { hi += 0.5; lo -= 0.5; }
    const W = 100, H = 26, pad = 3;
    const sx = (i) => (n === 1 ? W / 2 : (i / (n - 1)) * W);
    const sy = (v) => H - pad - ((v - lo) / (hi - lo)) * (H - 2 * pad);
    let line = "";
    values.forEach((v, i) => { line += (i ? "L" : "M") + sx(i).toFixed(1) + " " + sy(v).toFixed(1) + " "; });
    const area = line + `L${W} ${H} L0 ${H} Z`;
    return { line: line.trim(), area };
  }

  function renderMetrics(metrics, consciousness) {
    ensureMetricCells();
    // assemble a merged view of metric values from both sources
    const m = metrics || {};
    const cm = (consciousness && consciousness.conscious_moment) || {};
    const integ = (consciousness && consciousness.integration) || {};
    const meta = (consciousness && consciousness.metacognition) || {};
    const phiCausal = (consciousness && consciousness.phi_causal) || {};
    const hierarchy = (consciousness && consciousness.hierarchy) || {};
    const wandering = (consciousness && consciousness.wandering) || {};
    const task = (consciousness && consciousness.task) || {};
    const merged = {
      phi_proxy: m.phi_proxy != null ? m.phi_proxy : integ.phi_proxy,
      arousal: m.arousal != null ? m.arousal : cm.arousal,
      free_energy: m.free_energy != null ? m.free_energy : cm.free_energy,
      prediction_error: m.prediction_error,
      self_coherence: m.self_coherence,
      meta_confidence: m.meta_confidence != null ? m.meta_confidence : meta.meta_confidence,
      energy: m.energy,
      phi_causal: m.phi_causal != null ? m.phi_causal : phiCausal.phi_causal,
      vfe: m.vfe != null ? m.vfe : hierarchy.vfe,
      wandering_occupancy: m.wandering_occupancy != null
        ? m.wandering_occupancy : wandering.occupancy,
      task_progress: m.task_progress != null ? m.task_progress : task.progress,
    };

    METRIC_DEFS.forEach(([key, , , fmt]) => {
      const v = merged[key];
      if (v == null) return;
      pushHist(key, v);
      const cell = $(`.metric-cell[data-key="${key}"]`);
      if (!cell) return;
      cell.querySelector("[data-val]").textContent = fmt(v);
      const sp = sparkPath(HISTORY[key]);
      cell.querySelector("[data-line]").setAttribute("d", sp.line);
      cell.querySelector("[data-area]").setAttribute("d", sp.area);
    });
  }

  // ============================================================
  //  SELF-MODEL
  // ============================================================
  function renderSelfModel(s) {
    const box = $("#self-model");
    box.innerHTML = "";
    if (!s) { box.appendChild(el("div", "empty", "Self-model unavailable.")); return; }
    const pairs = [
      ["Identity", esc(s.identity)],
      ["Age (ticks)", f0(s.age_ticks)],
      ["Energy", f2(s.energy)],
      ["Confidence", f3(s.confidence)],
      ["Mood", f3(s.mood)],
      ["Coherence", f3(s.coherence)],
    ];
    pairs.forEach(([k, v]) => {
      box.appendChild(el("span", "k", k));
      box.appendChild(el("span", "v", v));
    });

    // relational self (social mirror) — only present when social_mirror_enabled
    // AND the agent has observers; the self-model is shaped by how others regard it.
    const rs = s.relational_self;
    if (rs) {
      box.appendChild(el("span", "k", "Social mirror"));
      box.appendChild(el("span", "v",
        `regarded ${f2(rs.reflected_appraisal)} · seen by ${f0(rs.n_observers)} · presence ${f2(rs.social_presence)}`));
    }

    const goals = $("#self-goals");
    goals.innerHTML = "";
    const list = s.active_goals || [];
    if (!list.length) goals.appendChild(el("span", "chip chip-empty", "no goal"));
    else list.forEach((g) => goals.appendChild(el("span", "chip", esc(g))));

    $("#self-narrative").textContent = s.narrative || "";
  }

  // ============================================================
  //  INTROSPECTION
  // ============================================================
  const INTRO_FIELDS = [
    ["perceive", "What I perceive"],
    ["attend", "What I am attending to"],
    ["predict", "What I predict"],
    ["intend", "What I intend to do"],
    ["why", "Why"],
    ["remember", "What I remember"],
    ["self_state", "What my self-model indicates"],
  ];
  function renderIntrospection(r) {
    const box = $("#introspection");
    box.innerHTML = "";
    if (!r) { box.appendChild(el("div", "empty", "No report.")); return; }
    INTRO_FIELDS.forEach(([key, label]) => {
      if (!r[key]) return;
      const item = el("div", "report-item");
      item.appendChild(el("div", "ri-key", esc(label)));
      item.appendChild(el("div", "ri-text", esc(r[key])));
      box.appendChild(item);
    });
  }

  // ============================================================
  //  WORKING MEMORY + MEMORIES
  // ============================================================
  const kindClass = (k) => "kind-" + (k || "curio");

  function renderWorkingMemory(items, load) {
    $("#wm-load-fill").style.width = pctTxt(load);
    $("#wm-load-val").textContent = pctTxt(load);
    const box = $("#working-memory");
    box.innerHTML = "";
    if (!items || !items.length) { box.appendChild(el("div", "empty", "Working memory empty.")); return; }
    items.forEach((it) => {
      const p = it.percept || {};
      const row = el("div", "row");
      const top = el("div", "row-top");
      top.appendChild(el("span", "row-title " + kindClass(p.kind),
        esc(p.kind || "?") + " #" + (p.object_id != null ? p.object_id : "?")));
      top.appendChild(el("span", "row-tag", "sal " + f2(it.saliency)));
      row.appendChild(top);
      row.appendChild(el("div", "row-sub",
        `dist ${f2(p.distance)} · danger ${f2(p.danger)} · novelty ${f2(p.novelty)} · seen t${num(it.last_seen_tick)}`));
      box.appendChild(row);
    });
  }

  function renderMemories(records) {
    const box = $("#recent-memories");
    box.innerHTML = "";
    if (!records || !records.length) { box.appendChild(el("div", "empty", "No memory recorded.")); return; }
    records.slice().reverse().forEach((r) => {
      const row = el("div", "row");
      const top = el("div", "row-top");
      top.appendChild(el("span", "row-title", esc(r.action) + (r.target_id != null ? " #" + r.target_id : "")));
      top.appendChild(el("span", "row-tag", "t" + num(r.tick) + " · imp " + f2(r.importance)));
      row.appendChild(top);
      if (r.summary) row.appendChild(el("div", "row-sub", esc(r.summary)));
      row.appendChild(el("div", "row-sub",
        `ΔE ${f2(r.result_energy_delta)} · err ${f2(r.prediction_error)}`));
      box.appendChild(row);
    });
  }

  // ============================================================
  //  DEEP CONSCIOUSNESS (Phase 2) — circadian / sleep / agency / curiosity
  // ============================================================
  // The six Phase-2 flags + four Phase-3 flags default to ON so the live
  // instrument shows the deep + learning/personality layers. These are the
  // hardcoded first-run defaults for the Settings-panel toggles; once the user
  // changes anything, the persisted set (localStorage) supersedes them.
  const SETTINGS_DEFAULTS = {
    circadian_enabled: true, sleep_enabled: true, dream_enabled: true,
    imagination_enabled: true, curiosity_enabled: true, agency_enabled: true,
    learning_enabled: true, concepts_enabled: true,
    meta_learning_enabled: true, personality_enabled: true,
    satiation_enabled: true,
    social_mirror_enabled: true,
    self_opacity_enabled: true,
    individuation_enabled: true,
    // Phase 5 — the asymptote (all level-2; never level 1)
    recurrence_enabled: true, reality_monitor_enabled: true,
    intero_inference_enabled: true, temporality_enabled: true,
    inner_speech_enabled: true, phi_ar_enabled: true,
    priming_enabled: true,
    // Phase 6 — the invention of language (naming games)
    language_drive_enabled: true,
    // Phase 7 — the horizon (core defaults remain off for compatibility)
    phi_causal_enabled: true, hierarchy_enabled: true, planning_enabled: true,
    vector_memory_enabled: true, td_learning_enabled: true,
    mind_wandering_enabled: true, world_dynamics_enabled: true, tasks_enabled: true,
  };

  // applyControlStates — reflect a config object into the Settings-panel DOM so
  // the controls visually match what's actually applied. Flags -> checkboxes;
  // slider values -> range inputs (+ their printed value badge). Only keys
  // present in cfg are touched, so partial saved sets leave other controls alone.
  function applyControlStates(cfg) {
    if (!cfg) return;
    document.querySelectorAll(".panel-config input[data-flag]").forEach((box) => {
      const flag = box.dataset.flag;
      if (Object.prototype.hasOwnProperty.call(cfg, flag)) box.checked = !!cfg[flag];
    });
    document.querySelectorAll("#config-sliders .slider-row").forEach((row) => {
      const key = row.dataset.key;
      if (!Object.prototype.hasOwnProperty.call(cfg, key)) return;
      const input = row.querySelector("input");
      const valEl = row.querySelector(".slider-val");
      if (input) input.value = cfg[key];
      if (valEl) valEl.textContent = fmtSlider(row.dataset.fmt, cfg[key]);
    });
  }

  // applyDeepDefaults — on load, apply the DEFAULTS overlaid with the SAVED
  // settings (so newly-shipped mechanisms default ON even for users with an
  // older saved set, while every choice the user actually made still wins).
  // The desired set is DIFFED against the live backend config first and only
  // the differing keys are posted — a plain reload no longer resets (and,
  // combined with the backend resume, never pauses) a running simulation.
  async function applyDeepDefaults() {
    const saved = loadSettings();
    const cfg = { ...SETTINGS_DEFAULTS, ...(saved || {}) };
    try {
      let patch = cfg;
      try {
        const live = (await api("config")) || {};
        const liveCfg = live.config || {};
        patch = {};
        for (const k in cfg) {
          if (liveCfg[k] !== cfg[k]) patch[k] = cfg[k];
        }
      } catch (e) { /* no GET /config: post the full set */ }
      if (Object.keys(patch).length) await postJSON("config", patch);
      saveSettings(cfg);   // persist the merged set (adds newly-shipped keys)
    } catch (e) { /* non-fatal: panel just stays at defaults */ }
    applyControlStates(cfg);
  }

  // circadian dial: a ring with a lit arc proportional to daylight (1 = noon).
  function drawCircadianDial(daylight) {
    const cv = $("#circadian-dial");
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const W = cv.width, H = cv.height;
    ctx.clearRect(0, 0, W, H);
    const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 10;
    const lit = clamp01(num(daylight));

    // night track (full ring)
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.lineWidth = 9;
    ctx.strokeStyle = cssVar("--bg-inset");
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.lineWidth = 1;
    ctx.strokeStyle = cssVar("--line");
    ctx.stroke();

    // lit (daylight) arc — starts at top (-90°), spans clockwise by daylight fraction
    if (lit > 0) {
      const start = -Math.PI / 2;
      const end = start + lit * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, start, end);
      ctx.lineWidth = 9;
      ctx.lineCap = "round";
      ctx.strokeStyle = cssVar("--accent");
      ctx.stroke();
      ctx.lineCap = "butt";
    }

    // center readout: sun (high daylight) vs moon (low)
    ctx.fillStyle = lit >= 0.5 ? cssVar("--accent") : cssVar("--cool");
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.38, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = cssVar("--ink");
    ctx.font = "600 14px " + (cssVar("--mono") || "monospace");
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = cssVar("--bg-inset");
    ctx.fillText((lit * 100).toFixed(0) + "%", cx, cy);
  }

  // refreshDeep — drives the deep-consciousness panel from the latest readings.
  // The Phase-2 scalars (daylight/is_sleeping/agency/boredom) live on the Metrics
  // payload, which /state nests under state.metrics and /tick exposes as
  // trace.metrics; accept either shape. The imagined plan / dream come from the
  // most recent /tick trace's imagination.best_first_action and sleep.dream.
  function refreshDeep(source, trace) {
    const src = source || {};
    // unwrap: prefer explicit metrics, else the object itself (it may already be metrics)
    const s = src.metrics || src;
    const tr = trace || lastTrace || {};

    drawCircadianDial(s.daylight != null ? s.daylight : 1);

    const asleep = !!s.is_sleeping;
    const ss = $("#sleep-state");
    if (ss) {
      ss.textContent = asleep ? "asleep" : "awake";
      ss.classList.toggle("is-asleep", asleep);
    }
    const dream = tr.sleep && tr.sleep.dream ? tr.sleep.dream : "";
    if ($("#dream-line")) $("#dream-line").textContent = dream;

    const agency = clamp01(num(s.agency));
    if ($("#agency-fill")) $("#agency-fill").style.width = (agency * 100).toFixed(1) + "%";
    if ($("#agency-val")) $("#agency-val").textContent = f2(agency);

    const boredom = clamp01(num(s.boredom));
    if ($("#boredom-fill")) $("#boredom-fill").style.width = (boredom * 100).toFixed(1) + "%";
    if ($("#boredom-val")) $("#boredom-val").textContent = f2(boredom);

    const plan = tr.imagination && tr.imagination.best_first_action;
    if ($("#imagined-plan")) $("#imagined-plan").textContent = plan ? String(plan) : "—";
  }

  // self-opacity (HOT, level-2) — a higher-order readout of how much of the tick
  // formed OUTSIDE the agent's access/control (the subliminal remainder, an
  // outcome it did not cause, an error it did not anticipate). Functional
  // measure only — NOT a claim of consciousness. Rides on lastTrace.self_opacity;
  // when null (flag off / no tick yet) the readout degrades to "—" / width 0.
  function renderSelfOpacity(trace) {
    const so = trace && trace.self_opacity;
    const fill = $("#opacity-fill");
    const val = $("#opacity-val");
    const rep = $("#opacity-report");
    if (!so) {
      if (fill) fill.style.width = "0";
      if (val) val.textContent = "—";
      if (rep) rep.textContent = "";
      return;
    }
    const frac = clamp01(num(so.uncontrolled_fraction));
    if (fill) fill.style.width = (frac * 100).toFixed(1) + "%";
    if (val) val.textContent = f2(frac);
    if (rep) rep.innerHTML = so.report ? esc(so.report) : "";
  }

  // individuation ("becoming someone", LEVEL-2 functional) — how far the agent
  // has grown into a coherent, distinctive, continuous, self-authoring self.
  // Rides on lastTrace.individuation; NOT a claim of phenomenal consciousness or
  // personhood. When null (flag off / no tick yet) the readout degrades to "—" /
  // width 0 / empty report, consistent with the other optional readouts.
  function renderIndividuation(trace) {
    const iv = trace && trace.individuation;
    // [id, value-key] for the four sub-meters
    const subs = [
      ["#indiv-coh", "coherence"],
      ["#indiv-dis", "distinctiveness"],
      ["#indiv-con", "continuity"],
      ["#indiv-agy", "agency"],
    ];
    const setBar = (id, v) => {
      const fill = $(id + "-fill");
      const val = $(id + "-val");
      if (fill) fill.style.width = v == null ? "0" : (clamp01(num(v)) * 100).toFixed(1) + "%";
      if (val) val.textContent = v == null ? "—" : f2(v);
    };
    const rep = $("#indiv-report");
    if (!iv) {
      setBar("#indiv", null);
      subs.forEach(([id]) => setBar(id, null));
      if (rep) rep.textContent = "";
      return;
    }
    setBar("#indiv", iv.index);
    subs.forEach(([id, key]) => setBar(id, iv[key]));
    if (rep) rep.textContent = iv.report || "";
  }

  // the asymptote (Phase 5, level-2) — recurrence (RPT) / reality monitoring
  // (PRM) / interoceptive presence / temporal thickness / inner speech / Φ_AR.
  // Accepts either a full CycleTrace or the GET /agent/consciousness payload
  // (both expose the same sub-object keys). Each readout degrades to "—" when
  // its flag is off. Functional variables only — never evidence of experience.
  function renderAsymptote(src) {
    const s = src || {};

    const intero = s.interoception;
    const pf = $("#presence-fill");
    if (pf) pf.style.width = intero ? (clamp01(num(intero.presence)) * 100).toFixed(1) + "%" : "0";
    if ($("#presence-val")) $("#presence-val").textContent =
      intero ? f2(intero.presence) + " · err " + f2(intero.error) : "—";

    const temp = s.temporality;
    if ($("#specious-val")) $("#specious-val").textContent =
      temp ? f2(temp.specious_width) + " moments wide" : "—";
    if ($("#protention-line")) $("#protention-line").textContent = temp
      ? ("leaning toward: " + (temp.protended_source || "—")
         + (temp.protention_error != null ? " · surprise " + f2(temp.protention_error) : ""))
      : "";

    const phi = s.phi_ar;
    if ($("#phi-ar-val")) $("#phi-ar-val").textContent =
      phi ? f3(phi.phi_ar) + " · " + num(phi.n_sources) + " sources" : "—";
    if ($("#phi-ar-mib")) $("#phi-ar-mib").textContent =
      phi && phi.mib ? "MIB " + phi.mib : "";

    const rec = s.recurrence;
    if ($("#recurrence-state")) $("#recurrence-state").textContent = rec
      ? (num(rec.n_refined) + " refined / " + num(rec.passes) + " passes"
         + (rec.stabilized ? " · stable" : " · settling"))
      : "—";

    const rm = s.reality_monitor;
    if ($("#reality-verdict")) $("#reality-verdict").textContent = rm
      ? (rm.judged + (rm.correct === false ? " — MISATTRIBUTED (actual: " + rm.actual + ")" : "")
         + " · accuracy " + f2(rm.accuracy))
      : "—";
    if ($("#reality-report")) $("#reality-report").textContent = (rm && rm.report) || "";

    const isd = s.inner_speech;
    if ($("#inner-speech-line")) $("#inner-speech-line").textContent = isd
      ? ("“" + isd.utterance + "”" + (isd.reentered ? " — re-entered global access" : ""))
      : "—";
    if ($("#reentry-count")) $("#reentry-count").textContent =
      isd ? "· re-entries: " + num(isd.reentry_count) : "";
  }

  // the horizon (Phase 7, level-2) — mechanism states remain explicitly
  // dormant until their flag is active and a cycle has populated them.
  function renderHorizon(trace, world) {
    const t = trace || {};
    const phi = t.phi_causal;
    const hierarchy = t.hierarchy;
    const planning = t.planning;
    const semantic = t.semantic_memory;
    const td = t.learning && t.learning.td_context ? t.learning : null;
    const wandering = t.wandering;
    const cells = [
      {
        label: "Causal Φ", state: phi,
        value: phi ? f3(phi.phi_causal) : "—",
        note: phi
          ? `exact coarse substrate · ${num(phi.n_nodes)} nodes · computed t${num(phi.computed_at_tick)}`
          : "dormant — enable causal Φ and accumulate its observation window",
      },
      {
        label: "Predictive level", state: hierarchy,
        value: hierarchy ? (hierarchy.regime || "unclassified") : "—",
        note: hierarchy
          ? `explicit VFE ${f3(hierarchy.vfe)} · precision ${f3(hierarchy.context_precision)}`
          : "dormant — predictive hierarchy has no current regime",
      },
      {
        label: "Policy horizon", state: planning,
        value: planning ? f0(planning.horizon) : "—",
        note: planning
          ? ((planning.best_sequence || []).length
              ? (planning.best_sequence || []).join(" → ")
              : "bounded search returned no action sequence")
          : "dormant — multi-step expected-free-energy search is off",
      },
      {
        label: "Semantic memory", state: semantic,
        value: semantic ? f0(semantic.index_size) : "—",
        note: semantic
          ? `${semantic.mode || "feature"} retrieval · mean cosine ${f3(semantic.mean_similarity)}`
          : "dormant — no vector-memory retrieval state this cycle",
      },
      {
        label: "TD(λ)", state: td,
        value: td ? f3(td.td_error) : "—",
        note: td
          ? `${td.td_context || "no context"} · ${num(td.n_contexts)} learned contexts`
          : "dormant — contextual TD learning has no active trace",
      },
      {
        label: "Default mode", state: wandering,
        value: wandering ? pctTxt(wandering.occupancy) : "—",
        note: wandering
          ? (wandering.active
              ? `associative episode active · pressure ${f3(wandering.pressure)}`
              : `externally coupled · pressure ${f3(wandering.pressure)}`)
          : "dormant — functional mind-wandering is disabled",
      },
    ];

    const host = $("#horizon-readouts");
    if (host) {
      host.innerHTML = cells.map((cell) =>
        `<article class="horizon-readout ${cell.state ? "is-live" : "is-dormant"}">` +
          `<span class="hr-label">${esc(cell.label)}</span>` +
          `<strong class="hr-value">${esc(cell.value)}</strong>` +
          `<span class="hr-note">${esc(cell.note)}</span>` +
        `</article>`
      ).join("");
    }

    const taskHost = $("#horizon-task");
    const task = t.task || (world && world.task);
    if (taskHost) {
      taskHost.innerHTML = task
        ? `<b>${esc(task.kind || "task")}</b> · ${esc(pctTxt(task.progress))} · ` +
          `${esc(task.description || "No task description supplied.")} · ` +
          `${esc(num(task.completed_total))} completed`
        : "World task system dormant — no structured task is active.";
    }
  }

  // Draw score and homeostatic threshold on their shared, honest 0..1 scale.
  // Repeated HTTP polls at the same simulation tick update rather than duplicate
  // a sample, so the x-axis remains simulation time rather than browser time.
  function renderIgnitionDynamics(workspace, tick) {
    if (workspace) {
      const sample = {
        tick: num(tick),
        score: clamp01(num(workspace.ignition_score)),
        effective_threshold: clamp01(num(
          workspace.effective_threshold != null
            ? workspace.effective_threshold : workspace.threshold
        )),
        ignited: !!(workspace.ignited != null ? workspace.ignited : workspace.ignition),
      };
      const previous = ignitionHistory[ignitionHistory.length - 1];
      if (previous && previous.tick === sample.tick) ignitionHistory[ignitionHistory.length - 1] = sample;
      else ignitionHistory.push(sample);
      if (ignitionHistory.length > IGNITION_HISTORY_MAX) {
        ignitionHistory.splice(0, ignitionHistory.length - IGNITION_HISTORY_MAX);
      }
    }

    const canvas = $("#ignition-chart");
    const summary = $("#ignition-chart-summary");
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const W = canvas.width, H = canvas.height;
    const left = 44, right = 16, top = 26, bottom = 32;
    const plotW = W - left - right, plotH = H - top - bottom;
    const n = ignitionHistory.length;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = cssVar("--bg-inset");
    ctx.fillRect(0, 0, W, H);
    ctx.font = "10px monospace";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const value = i / 4;
      const y = top + (1 - value) * plotH + 0.5;
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(W - right, y);
      ctx.strokeStyle = cssVar("--line");
      ctx.globalAlpha = i === 0 || i === 4 ? 0.72 : 0.38;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = cssVar("--ink-faint");
      ctx.textAlign = "right";
      ctx.fillText(value.toFixed(2), left - 7, y);
    }

    // Compact in-canvas legend; threshold is dashed, score is solid brass.
    ctx.textAlign = "left";
    ctx.fillStyle = cssVar("--accent");
    ctx.fillRect(left, 9, 18, 2);
    ctx.fillStyle = cssVar("--ink-soft");
    ctx.fillText("score", left + 24, 10);
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = cssVar("--ink-faint");
    ctx.beginPath(); ctx.moveTo(left + 78, 10); ctx.lineTo(left + 96, 10); ctx.stroke();
    ctx.restore();
    ctx.fillText("effective threshold", left + 102, 10);

    if (!n) {
      ctx.fillStyle = cssVar("--ink-faint");
      ctx.textAlign = "center";
      ctx.fillText("No access-dynamics samples yet", left + plotW / 2, top + plotH / 2);
      if (summary) summary.textContent = "No access-dynamics samples yet.";
      canvas.setAttribute("aria-label", "Ignition dynamics: no samples yet");
      return;
    }

    const xAt = (i) => left + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const yAt = (value) => top + (1 - clamp01(num(value))) * plotH;
    const drawLine = (key, color, dashed) => {
      ctx.save();
      ctx.beginPath();
      ignitionHistory.forEach((sample, i) => {
        const x = xAt(i), y = yAt(sample[key]);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = color;
      ctx.lineWidth = key === "score" ? 2 : 1.35;
      if (dashed) ctx.setLineDash([5, 4]);
      ctx.stroke();
      ctx.restore();
    };
    drawLine("effective_threshold", cssVar("--ink-faint"), true);
    drawLine("score", cssVar("--accent"), false);

    ignitionHistory.forEach((sample, i) => {
      if (!sample.ignited) return;
      ctx.beginPath();
      ctx.arc(xAt(i), yAt(sample.score), 2.7, 0, Math.PI * 2);
      ctx.fillStyle = cssVar("--accent-bright");
      ctx.fill();
      ctx.strokeStyle = cssVar("--bg-inset");
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    const first = ignitionHistory[0], latest = ignitionHistory[n - 1];
    ctx.fillStyle = cssVar("--ink-faint");
    ctx.textAlign = "left";
    ctx.fillText("t" + f0(first.tick), left, H - 13);
    ctx.textAlign = "right";
    ctx.fillText("t" + f0(latest.tick), W - right, H - 13);
    const ignitionCount = ignitionHistory.reduce((sum, sample) => sum + (sample.ignited ? 1 : 0), 0);
    const rate = ignitionCount / n;
    const summaryText = `Latest t${f0(latest.tick)}: score ${f3(latest.score)}, ` +
      `effective threshold ${f3(latest.effective_threshold)}; ignition rate ${pctTxt(rate)} across ${n} sample${n === 1 ? "" : "s"}.`;
    if (summary) summary.textContent = summaryText;
    canvas.setAttribute("aria-label", "Ignition score and effective-threshold history. " + summaryText);
  }

  function renderHorizonStream(moments) {
    const host = $("#horizon-stream");
    if (!host) return;
    const data = (Array.isArray(moments) ? moments : streamData).slice(-STREAM_MAX);
    host.innerHTML = "";
    const fragment = document.createDocumentFragment();
    const sources = new Set();
    let ignitedCount = 0;
    data.forEach((moment) => {
      const source = String(moment && moment.dominant_source || "unknown").toLowerCase();
      const color = SOURCE_COLORS[source] || SOURCE_COLORS.unknown;
      const awareness = clamp01(num(moment && moment.awareness_level));
      const ignited = !!(moment && moment.ignited);
      const tickLabel = "t" + f0(moment && moment.tick);
      const content = String(moment && moment.contents || "no content label");
      const description = `${tickLabel} · ${source} · awareness ${f3(awareness)} · ` +
        `${ignited ? "ignited" : "subliminal"} · ${content}`;
      const bar = el("span", "moment" + (ignited ? " ignited" : ""));
      bar.style.height = Math.max(4, awareness * 50).toFixed(1) + "px";
      bar.style.backgroundColor = color;
      bar.style.color = color;
      bar.title = description;
      bar.setAttribute("aria-label", description);
      fragment.appendChild(bar);
      sources.add(source);
      if (ignited) ignitedCount++;
    });
    host.appendChild(fragment);
    const latestSource = data.length
      ? String(data[data.length - 1].dominant_source || "unknown") : "none";
    host.setAttribute("aria-label", data.length
      ? `${data.length} recent workspace moments; ${ignitedCount} ignited; ` +
        `${sources.size} dominant sources; latest source ${latestSource}.`
      : "No dominant-source moments recorded yet.");
  }

  async function refreshMemoryGraph(force) {
    const requestedTick = num(lastTick);
    const generation = horizonGeneration;
    if (!force && (
      requestedTick < 0 ||
      (lastMemoryGraphTick >= 0 && requestedTick - lastMemoryGraphTick < 20)
    )) return memoryGraphCache;
    if (memoryGraphRequest) return memoryGraphRequest;
    if (!force) lastMemoryGraphTick = requestedTick;

    let request = null;
    request = (async () => {
      try {
        const graph = await api("agent/memory/graph?limit=60&edges=3");
        if (generation !== horizonGeneration) return memoryGraphCache;
        memoryGraphCache = {
          nodes: Array.isArray(graph && graph.nodes) ? graph.nodes : [],
          edges: Array.isArray(graph && graph.edges) ? graph.edges : [],
        };
        drawMemoryGraph(memoryGraphCache);
        return memoryGraphCache;
      } catch (e) {
        if (generation !== horizonGeneration) return memoryGraphCache;
        drawMemoryGraph(memoryGraphCache);
        const summary = $("#memory-graph-summary");
        if (summary) {
          summary.textContent = memoryGraphCache.nodes.length
            ? `Memory graph unavailable; showing ${memoryGraphCache.nodes.length} cached nodes.`
            : "Memory graph unavailable; no indexed memories could be loaded.";
        }
        return memoryGraphCache;
      } finally {
        if (memoryGraphRequest === request) memoryGraphRequest = null;
      }
    })();
    memoryGraphRequest = request;
    return request;
  }

  function drawGraphEdge(ctx, source, target, similarity) {
    if (!source || !target) return;
    const strength = clamp01((num(similarity) + 1) / 2);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(source.x, source.y);
    ctx.lineTo(target.x, target.y);
    ctx.strokeStyle = cssVar("--cool");
    ctx.globalAlpha = 0.06 + strength * 0.42;
    ctx.lineWidth = 0.45 + strength * 1.05;
    ctx.stroke();
    ctx.restore();
  }

  function graphNodeColor(node) {
    const valence = num(node && node.valence);
    if (valence > 0.12) return cssVar("--pos");
    if (valence < -0.12) return cssVar("--neg");
    const action = String(node && node.action || "").toLowerCase();
    if (action === "explore" || action === "analyze") return cssVar("--curio");
    if (action === "approach" || action === "interact") return cssVar("--accent");
    if (action === "avoid") return cssVar("--neg");
    if (action === "rest") return cssVar("--cool");
    return cssVar("--ink-soft");
  }

  function drawGraphNode(ctx, point, selected) {
    if (!point) return;
    ctx.save();
    ctx.beginPath();
    ctx.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
    ctx.fillStyle = graphNodeColor(point.node);
    ctx.globalAlpha = 0.84;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.strokeStyle = cssVar("--bg-inset");
    ctx.lineWidth = 1.2;
    ctx.stroke();
    if (selected) {
      ctx.beginPath();
      ctx.arc(point.x, point.y, point.radius + 4, 0, Math.PI * 2);
      ctx.strokeStyle = cssVar("--accent-bright");
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawMemoryGraph(graph) {
    const canvas = $("#memory-graph");
    const summary = $("#memory-graph-summary");
    if (!canvas || !canvas.getContext) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const nodes = Array.isArray(graph && graph.nodes) ? graph.nodes : [];
    const edges = Array.isArray(graph && graph.edges) ? graph.edges : [];
    const nodeList = $("#memory-graph-nodes");
    if (nodeList) {
      nodeList.replaceChildren();
      const listFragment = document.createDocumentFragment();
      nodes.forEach((node) => {
        const item = document.createElement("li");
        item.textContent = `${String(node && node.action || "memory")} at tick ${f0(node && node.tick)}; ` +
          `importance ${f2(node && node.importance)}; valence ${f2(node && node.valence)}; ` +
          `${String(node && node.summary || "No summary stored.")}`;
        listFragment.appendChild(item);
      });
      nodeList.appendChild(listFragment);
    }
    const edgeList = $("#memory-graph-edges");
    if (edgeList) {
      edgeList.replaceChildren();
      const edgeFragment = document.createDocumentFragment();
      const nodeById = new Map(nodes.map((node) => [String(node && node.id), node]));
      edges.forEach((edge) => {
        const source = nodeById.get(String(edge && edge.source));
        const target = nodeById.get(String(edge && edge.target));
        const sourceLabel = source
          ? `${String(source.action || "memory")} at tick ${f0(source.tick)}`
          : `memory ${String(edge && edge.source)}`;
        const targetLabel = target
          ? `${String(target.action || "memory")} at tick ${f0(target.tick)}`
          : `memory ${String(edge && edge.target)}`;
        const item = document.createElement("li");
        item.textContent = `${sourceLabel} is linked to ${targetLabel}; ` +
          `cosine similarity ${f3(edge && edge.similarity)}.`;
        edgeFragment.appendChild(item);
      });
      edgeList.appendChild(edgeFragment);
    }
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const maxRadius = Math.min(W, H) * 0.43;
    const goldenAngle = 2.399963229728653;
    const placed = new Map();

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = cssVar("--bg-inset");
    ctx.fillRect(0, 0, W, H);

    if (!nodes.length) {
      memoryGraphSelection = -1;
      canvas._placedNodes = [];
      const tooltip = $("#memory-graph-tooltip");
      if (tooltip) tooltip.hidden = true;
      const selection = $("#memory-graph-selection");
      if (selection) selection.textContent = "No memory node is available for selection.";
      ctx.fillStyle = cssVar("--ink-faint");
      ctx.font = "11px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("No indexed autobiographical memories", cx, cy);
      if (summary) summary.textContent = "No indexed memories yet.";
      canvas.setAttribute("aria-label", "Autobiographical memory graph: no indexed memories yet");
      return;
    }

    if (memoryGraphSelection >= nodes.length) memoryGraphSelection = nodes.length - 1;

    nodes.forEach((node, index) => {
      const tickPhase = (Math.abs(num(node && node.tick)) % 24) * 0.004;
      const angle = index * goldenAngle + tickPhase;
      const spiralRadius = Math.min(maxRadius, 18 + Math.sqrt(index + 1) * 24);
      const point = {
        x: cx + Math.cos(angle) * spiralRadius,
        y: cy + Math.sin(angle) * spiralRadius,
        radius: 3.5 + clamp01(num(node && node.importance)) * 5.5,
        node,
      };
      placed.set(node.id, point);
    });
    edges.forEach((edge) => drawGraphEdge(
      ctx, placed.get(edge.source), placed.get(edge.target), edge.similarity
    ));
    const placedNodes = Array.from(placed.values());
    placedNodes.forEach((point, index) => drawGraphNode(
      ctx, point, index === memoryGraphSelection
    ));
    canvas._placedNodes = placedNodes;
    if (memoryGraphSelection >= 0) {
      const selection = $("#memory-graph-selection");
      if (selection) selection.textContent =
        `Selected memory ${memoryGraphSelection + 1} of ${placedNodes.length}: ` +
        memoryGraphNodeDescription(placedNodes[memoryGraphSelection].node);
    }

    const summaryText = `${nodes.length} indexed memor${nodes.length === 1 ? "y" : "ies"} and ` +
      `${edges.length} similarity edge${edges.length === 1 ? "" : "s"}. ` +
      "Node radius encodes stored importance; colour encodes valence and action family.";
    if (summary) summary.textContent = summaryText;
    canvas.setAttribute("aria-label", "Autobiographical memory similarity graph. " + summaryText);
  }

  // the invention of language (Phase 6, level-2) — the agent-side readouts ride
  // on the trace/consciousness payload (language sub-object); the SOCIETY-side
  // dictionary + convergence come from GET /society/language. Emergent
  // naming-game conventions — never understanding, never experience.
  function renderLanguage(src) {
    const lang = (src || {}).language;
    const sf = $("#lang-success-fill"), sv = $("#lang-success-val");
    const df = $("#lang-deficit-fill"), dv = $("#lang-deficit-val");
    if (sf) sf.style.width = lang ? (clamp01(num(lang.success_rate)) * 100).toFixed(1) + "%" : "0";
    if (sv) sv.textContent = lang ? f2(lang.success_rate) + " · " + num(lang.n_exchanges) + " exchanges" : "—";
    if (df) df.style.width = lang ? (clamp01(num(lang.deficit)) * 100).toFixed(1) + "%" : "0";
    if (dv) dv.textContent = lang ? f2(lang.deficit) : "—";

    const ex = $("#lang-exchange");
    if (ex) {
      if (lang && lang.utterance) {
        ex.textContent = "spoke “" + lang.utterance.word + "” (" + lang.utterance.meaning + ")";
      } else if (lang && lang.heard && lang.heard.length) {
        const h = lang.heard[lang.heard.length - 1];
        ex.textContent = "heard “" + h.word + "” from agent " + h.sender_id
          + (h.inferred_meaning ? " → read as " + h.inferred_meaning : " → no context")
          + (h.understood ? " ✓" : "");
      } else {
        ex.textContent = "—";
      }
    }

    const vocab = $("#lang-vocab");
    if (vocab) {
      vocab.innerHTML = "";
      const entries = lang ? Object.entries(lang.vocabulary || {}) : [];
      if (!entries.length) {
        vocab.appendChild(el("span", "chip chip-empty", "no invented words yet"));
      } else {
        entries.forEach(([meaning, word]) => {
          vocab.appendChild(el("span", "chip lang-chip kind-" + esc(meaning),
            "“" + esc(word) + "” = " + esc(meaning)));
        });
      }
    }
  }

  async function refreshSocietyLanguage(generation) {
    const box = $("#lang-dictionary");
    if (!box) return;
    let d;
    try { d = await api("society/language"); } catch (e) { return; }
    if (generation != null && generation !== horizonGeneration) return;
    if ($("#lang-convergence")) {
      $("#lang-convergence").textContent =
        d.convergence != null ? f2(d.convergence) : "—";
    }
    if ($("#lang-distinct")) {
      $("#lang-distinct").textContent = d.n_meanings_named
        ? (d.n_meanings_named + " meaning(s) named · " + num(d.distinct_modal_words) + " distinct word(s)")
        : "";
    }
    box.innerHTML = "";
    const entries = Object.entries(d.dictionary || {});
    if (!entries.length) {
      box.appendChild(el("div", "empty", "No conventions yet — let the society talk."));
      return;
    }
    const frag = document.createDocumentFragment();
    entries.forEach(([meaning, e]) => {
      const row = el("div", "row");
      const top = el("div", "row-top");
      top.appendChild(el("span", "row-title kind-" + esc(meaning),
        "“" + esc(e.modal_word) + "” = " + esc(meaning)));
      top.appendChild(el("span", "row-tag",
        "agreement " + f2(e.agreement) + " · " + num(e.speakers) + " speaker(s)"));
      row.appendChild(top);
      const variants = Object.entries(e.variants || {})
        .map(([w, n]) => "“" + esc(w) + "”×" + n).join(" · ");
      row.appendChild(el("div", "row-sub", variants));
      frag.appendChild(row);
    });
    box.appendChild(frag);
  }

  // ============================================================
  //  LEARNING & PERSONALITY (Phase 3) — Q-values / concept / personality
  // ============================================================
  // refreshLearning — drives the Phase-3 panel from a CycleTrace. The learned
  // values (trace.learning.q_values), dominant concept (trace.concept) and the
  // emergent personality (trace.personality) only exist when the Phase-3 flags
  // are on; when learning is null the trace lacks the layer entirely, so the
  // panel keeps its placeholders rather than rendering empties.
  function refreshLearning(trace) {
    const tr = trace || {};

    // learned action values -> labeled bars, scaled to the largest |value|
    const learning = tr.learning;
    const qbox = $("#q-bars");
    if (qbox && learning && learning.q_values) {
      qbox.innerHTML = "";
      const entries = Object.entries(learning.q_values);
      // strongest-first so the dominant action reads at the top
      entries.sort((a, b) => num(b[1]) - num(a[1]));
      const maxAbs = Math.max(1e-6, ...entries.map(([, v]) => Math.abs(num(v))));
      if (!entries.length) {
        qbox.appendChild(el("div", "empty", "No learned values yet."));
      } else {
        const frag = document.createDocumentFragment();
        entries.forEach(([action, value]) => {
          const v = num(value);
          const row = el("div", "q-row");
          row.appendChild(el("span", "q-label", esc(action)));
          const barWrap = el("div", "q-bar");
          const fill = el("div", "q-fill" + (v < 0 ? " neg" : ""));
          fill.style.width = (clamp01(Math.abs(v) / maxAbs) * 100).toFixed(1) + "%";
          barWrap.appendChild(fill);
          row.appendChild(barWrap);
          row.appendChild(el("span", "q-val mono", f2(v)));
          frag.appendChild(row);
        });
        qbox.appendChild(frag);
      }
    }

    // dominant concept (id + match strength) and concept count
    const concept = tr.concept;
    const cstate = $("#concept-state");
    if (cstate) {
      if (concept) {
        const dom = concept.dominant_concept;
        cstate.textContent = (dom != null ? "#" + dom : "—") +
          " · match " + f2(concept.match) +
          " · " + num(concept.n_concepts) + " concepts";
      } else {
        cstate.textContent = "—";
      }
    }

    // effective learning rate — prefer metrics, fall back to the learning state
    const m = tr.metrics || {};
    const elr = m.effective_learning_rate != null
      ? m.effective_learning_rate
      : (learning ? learning.effective_lr : null);
    if ($("#elr-val")) $("#elr-val").textContent = elr != null ? f3(elr) : "—";

    // personality: label + the three named traits as small meters
    const p = tr.personality;
    const plabel = $("#personality-label");
    if (plabel) plabel.textContent = p && p.label ? p.label : "nascent";
    const ptraits = $("#personality-traits");
    if (ptraits) {
      ptraits.innerHTML = "";
      const traits = p
        ? [["openness", p.openness], ["caution", p.caution], ["novelty seeking", p.novelty_seeking]]
        : [["openness", null], ["caution", null], ["novelty seeking", null]];
      const frag = document.createDocumentFragment();
      traits.forEach(([name, val]) => {
        const t = clamp01(num(val));
        const row = el("div", "trait-row");
        row.appendChild(el("span", "trait-k", esc(name)));
        const meter = el("div", "meter");
        const fill = el("div", "meter-fill");
        fill.style.width = (t * 100).toFixed(1) + "%";
        meter.appendChild(fill);
        row.appendChild(meter);
        row.appendChild(el("span", "trait-v mono", val != null ? f2(t) : "—"));
        frag.appendChild(row);
      });
      ptraits.appendChild(frag);
    }
  }

  // ============================================================
  //  REFRESH (poll /state + agent endpoints)
  // ============================================================
  async function refreshAll() {
    refreshQueued = true;
    if (refreshInFlight) {
      return refreshDrainPromise;
    }
    refreshInFlight = true;
    refreshDrainPromise = (async () => {
      while (refreshQueued) {
        refreshQueued = false;
        await performRefreshAll();
      }
    })();
    try {
      await refreshDrainPromise;
    } finally {
      refreshInFlight = false;
      refreshDrainPromise = null;
    }
  }

  async function performRefreshAll() {
    const generation = horizonGeneration;
    try {
      const [state, metrics, consciousness, ws, stream, self, mem, intro] = await Promise.all([
        api("state").catch(() => null),
        api("metrics").catch(() => null),
        api("agent/consciousness").catch(() => null),
        api("agent/workspace").catch(() => null),
        api("agent/stream?limit=" + STREAM_MAX).catch(() => null),
        api("agent/self-model").catch(() => null),
        api("agent/memory?limit=20").catch(() => []),
        api("agent/introspection").catch(() => null),
      ]);
      if (generation !== horizonGeneration) return;

      let snap = null;
      let tick = lastTick;
      let tickChanged = false;
      if (state) {
        snap = state.world || state.snapshot || state;
        const incomingTick = num(
          snap.tick != null ? snap.tick : (metrics && metrics.tick));
        if (incomingTick < lastTick) return;
        tick = incomingTick;
        tickChanged = tick !== lastTick;
        drawWorld(snap);
        $("#world-meta").textContent = "tick " + tick + " · GET /state";
        lastTick = tick;
        // canonical arousal source: GET /state.arousal
        if (state.arousal != null) renderArousal(state.arousal, configValue("arousal_baseline"));
        if (typeof state.running === "boolean") {
          setRunningUI(state.running);
          // keep the poll loop in lockstep with the BACKEND's running state:
          // a run now survives page reloads and config patches, so polling
          // must follow the server, not only the local Start/Pause clicks.
          if (state.running && !pollTimer) startPolling();
          else if (!state.running && pollTimer) stopPolling();
        }
        renderWorkingMemory(state.working_memory || null, num(state.working_memory_load));
        if (state.self_model && !self) renderSelfModel(state.self_model);
        if (state.disclaimer) $("#footer-disclaimer").textContent = state.disclaimer;
        if (state.framing) $("#framing-text").textContent = state.framing;
      }

      renderMetrics(metrics, consciousness);
      if (consciousness) renderConsciousness(consciousness);
      if (ws) renderWorkspace(ws);
      else if (consciousness && consciousness.workspace) renderWorkspace(consciousness.workspace);
      if (stream) renderStream(stream);
      if (self) renderSelfModel(self);
      renderMemories(mem || []);
      if (intro) renderIntrospection(intro);
      // The optional trace sub-objects (learning, personality, sleep, opacity,
      // individuation, asymptote…) now ride on GET /agent/consciousness, so
      // every panel refreshes during BACKGROUND runs; a client-side CycleTrace
      // (manual Step) is only the fallback.
      const traceish = consciousness || lastTrace;
      const horizonWorkspace = ws || (consciousness && consciousness.workspace);
      try { renderHorizon(traceish, snap || (state && (state.world || state.snapshot))); } catch (e) { /* non-fatal */ }
      try { renderIgnitionDynamics(horizonWorkspace, tick); } catch (e) { /* non-fatal */ }
      try { renderHorizonStream(stream || streamData); } catch (e) { /* non-fatal */ }
      if (tickChanged) {
        try { await refreshMemoryGraph(false); } catch (e) { /* non-fatal */ }
        if (generation !== horizonGeneration) return;
      }
      // deep-consciousness panel (Phase 2) — guarded so it can't break the loop
      try { refreshDeep(state, traceish); } catch (e) { /* non-fatal */ }
      // learning & personality panel (Phase 3)
      try { refreshLearning(traceish); } catch (e) { /* non-fatal */ }
      // self-opacity readout (HOT, level-2)
      try { renderSelfOpacity(traceish); } catch (e) { /* non-fatal */ }
      // individuation ("becoming someone", level-2)
      try { renderIndividuation(traceish); } catch (e) { /* non-fatal */ }
      // the asymptote (Phase 5)
      try { renderAsymptote(traceish); } catch (e) { /* non-fatal */ }
      // the invention of language (Phase 6) — agent readouts + society dictionary
      try { renderLanguage(traceish); } catch (e) { /* non-fatal */ }
      try { await refreshSocietyLanguage(generation); } catch (e) { /* non-fatal */ }
      if (generation !== horizonGeneration) return;
      // laboratory time series (Phase 4) — guarded so it can't break the loop
      try { await refreshLabChart(generation); } catch (e) { /* non-fatal */ }
      if (generation !== horizonGeneration) return;
      // society view updates inside the same serialized network batch
      try { await refreshSociety(generation); } catch (e) { /* non-fatal */ }
    } catch (err) {
      console.error("refresh failed", err);
      setStatus("error", "API error");
    }
  }

  // After a manual tick we have a full CycleTrace — apply it for the richest update.
  function applyTrace(trace) {
    if (!trace) return;
    const traceTick = num(trace.tick);
    if (traceTick < lastTick) return;
    lastTrace = trace;  // retain for the deep panel (imagined plan / dream)
    lastTick = traceTick;
    $("#world-meta").textContent =
      "tick " + num(trace.tick) + " · synchronizing post-action world";
    // synthesize a consciousness view from the trace sub-objects
    const consc = {
      conscious_moment: trace.conscious_moment,
      workspace: trace.workspace,
      attention_schema: trace.attention_schema,
      metacognition: trace.metacognition,
      integration: trace.integration,
    };
    renderMetrics(trace.metrics, consc);
    if (trace.conscious_moment || trace.attention_schema) renderConsciousness(consc);
    if (trace.workspace) renderWorkspace(trace.workspace);
    if (trace.conscious_moment) {
      streamData.push(trace.conscious_moment);
      if (streamData.length > STREAM_MAX) streamData.shift();
      renderStream(null);
    }
    if (trace.self_model) renderSelfModel(trace.self_model);
    if (trace.introspection) renderIntrospection(trace.introspection);
    if (trace.working_memory) {
      const load = trace.metrics ? trace.metrics.working_memory_load
        : trace.working_memory.length / 5;
      renderWorkingMemory(trace.working_memory, load);
    }
    // deep panel: prefer trace.metrics (carries daylight/agency/boredom/is_sleeping)
    try { refreshDeep(trace.metrics, trace); } catch (e) { /* non-fatal */ }
    // learning & personality panel (Phase 3) — full trace carries learning/concept/personality
    try { refreshLearning(trace); } catch (e) { /* non-fatal */ }
    // self-opacity readout (HOT, level-2) — what escaped the agent's access/control
    try { renderSelfOpacity(trace); } catch (e) { /* non-fatal */ }
    // individuation ("becoming someone", level-2) — how far a coherent self has formed
    try { renderIndividuation(trace); } catch (e) { /* non-fatal */ }
    // the asymptote (Phase 5) — recurrence / PRM / interoception / temporality /
    // inner speech / Φ_AR ride on the full trace
    try { renderAsymptote(trace); } catch (e) { /* non-fatal */ }
    // the invention of language (Phase 6) — agent-side readouts
    try { renderLanguage(trace); } catch (e) { /* non-fatal */ }
    try { renderHorizon(trace, currentWorldSnap); } catch (e) { /* non-fatal */ }
    try { renderIgnitionDynamics(trace.workspace, trace.tick); } catch (e) { /* non-fatal */ }
    try { renderHorizonStream(streamData); } catch (e) { /* non-fatal */ }
  }

  // ============================================================
  //  POLLING
  // ============================================================
  function startPolling() { stopPolling(); pollTimer = setInterval(refreshAll, POLL_MS); }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  // ============================================================
  //  CONTROLS
  // ============================================================
  const INTERVENTION_ENDPOINTS = {
    ask: "/agent/ask",
    stimulus: "/world/stimulus",
    inject: "/agent/inject",
    attend: "/agent/attend",
    perturb: "/agent/perturb",
  };
  let interactionSequence = 0;
  let interventionPending = false;

  function compactLogValue(value) {
    let rendered;
    try { rendered = JSON.stringify(value, null, 2); }
    catch (e) { rendered = String(value); }
    return rendered.length > 1200 ? rendered.slice(0, 1197) + "..." : rendered;
  }

  function appendInterventionLog(kind, endpoint, payload, correlationId) {
    const host = $("#interaction-log");
    if (!host) return;
    const sequence = correlationId == null ? ++interactionSequence : correlationId;
    const entry = el("li", `interaction-entry is-${kind}`);
    const head = el("div", "interaction-entry-head");
    head.appendChild(el("span", "interaction-sequence mono", "#" + String(sequence).padStart(3, "0")));
    head.appendChild(el("strong", "interaction-kind", esc(kind)));
    head.appendChild(el("code", "interaction-endpoint", esc(endpoint)));
    entry.appendChild(head);
    const body = el("pre", "interaction-payload");
    body.textContent = compactLogValue(payload);
    entry.appendChild(body);
    host.appendChild(entry);
    while (host.children.length > 40) host.firstElementChild.remove();
    host.scrollTop = host.scrollHeight;
  }

  function setInterventionBusy(busy) {
    const panel = $("#experimental-interventions");
    if (panel) {
      if (busy) panel.setAttribute("aria-busy", "true");
      else panel.removeAttribute("aria-busy");
    }
    document.querySelectorAll(
      "#intervention-tabs button, .intervention-form button[type='submit'], #btn-clear-interactions"
    ).forEach((button) => { button.disabled = busy; });
  }

  function interventionPayload(name) {
    const value = (selector) => $(selector).value.trim();
    const number = (selector) => Number($(selector).value);
    if (name === "ask") {
      const payload = { question: value("#intervention-ask-question") };
      const intent = value("#intervention-ask-intent");
      if (intent) payload.intent = intent;
      return payload;
    }
    if (name === "stimulus") {
      const payload = {
        kind: value("#intervention-stimulus-kind"),
        intensity: number("#intervention-stimulus-intensity"),
      };
      const x = value("#intervention-stimulus-x");
      const y = value("#intervention-stimulus-y");
      if (x !== "") payload.x = Number(x);
      if (y !== "") payload.y = Number(y);
      return payload;
    }
    if (name === "inject") return {
      content: value("#intervention-inject-content"),
      activation: number("#intervention-inject-activation"),
      precision: number("#intervention-inject-precision"),
      ttl: number("#intervention-inject-ttl"),
    };
    if (name === "attend") return {
      target_id: number("#intervention-attend-target"),
      strength: number("#intervention-attend-strength"),
      ttl: number("#intervention-attend-ttl"),
    };
    return {
      type: value("#intervention-perturb-type"),
      magnitude: number("#intervention-perturb-magnitude"),
    };
  }

  function interventionResult(name, response) {
    if (name === "ask") return {
      intent: response && response.intent,
      answer: response && response.answer,
      grounding: response && response.grounding,
      disclaimer: response && response.disclaimer,
    };
    if (name === "stimulus") return { object: response && response.object };
    if (name === "perturb") return { effect: response && response.effect };
    return response;
  }

  async function submitIntervention(form) {
    if (interventionPending) return;
    const name = form.dataset.interventionPanel;
    const endpoint = INTERVENTION_ENDPOINTS[name];
    if (!endpoint) return;
    const payload = interventionPayload(name);
    const button = form.querySelector("button[type='submit']");
    const correlationId = ++interactionSequence;
    interventionPending = true;
    appendInterventionLog("request", endpoint, payload, correlationId);
    setInterventionBusy(true);
    if (button) button.disabled = true;
    form.setAttribute("aria-busy", "true");
    try {
      const response = await postJSON(endpoint.slice(1), payload);
      if (name === "perturb" && response && response.effect && response.effect.applied === false) {
        throw new Error(response.effect.reason || "perturbation was not applied");
      }
      appendInterventionLog(
        "result", endpoint, interventionResult(name, response), correlationId,
      );
      await refreshAll();
    } catch (error) {
      appendInterventionLog(
        "error", endpoint, { message: error.message || String(error) }, correlationId,
      );
      setStatus("error", "Intervention error");
    } finally {
      form.removeAttribute("aria-busy");
      interventionPending = false;
      setInterventionBusy(false);
      if (button) button.disabled = false;
    }
  }

  function activateIntervention(name, moveFocus) {
    const tabs = Array.from(document.querySelectorAll("#intervention-tabs [role='tab']"));
    const panels = Array.from(document.querySelectorAll("[data-intervention-panel]"));
    tabs.forEach((tab) => {
      const selected = tab.dataset.intervention === name;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      if (selected && moveFocus) tab.focus();
    });
    panels.forEach((panel) => { panel.hidden = panel.dataset.interventionPanel !== name; });
  }

  const interventionTabs = Array.from(document.querySelectorAll("#intervention-tabs [role='tab']"));
  interventionTabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateIntervention(tab.dataset.intervention, false));
    tab.addEventListener("keydown", (ev) => {
      let next = index;
      if (ev.key === "ArrowRight" || ev.key === "ArrowDown") next = (index + 1) % interventionTabs.length;
      else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") next = (index - 1 + interventionTabs.length) % interventionTabs.length;
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = interventionTabs.length - 1;
      else return;
      ev.preventDefault();
      activateIntervention(interventionTabs[next].dataset.intervention, true);
    });
  });
  document.querySelectorAll(".intervention-form").forEach((form) => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      void submitIntervention(form);
    });
  });
  $("#btn-clear-interactions")?.addEventListener("click", () => {
    $("#interaction-log").replaceChildren();
    interactionSequence = 0;
  });

  async function postWorldStimulusAt(x, y) {
    const status = $("#world-interaction-status");
    if (worldStimulusPending || interventionPending) {
      if (status) status.textContent = "Another intervention is still running.";
      return;
    }
    const payload = {
      kind: $("#world-stimulus-kind").value,
      x,
      y,
      intensity: Number($("#world-stimulus-intensity").value),
    };
    const correlationId = ++interactionSequence;
    worldStimulusPending = true;
    interventionPending = true;
    setInterventionBusy(true);
    if (status) status.textContent = `Injecting ${payload.kind} at (${x}, ${y})...`;
    appendInterventionLog("request", "/world/stimulus", payload, correlationId);
    try {
      const response = await postJSON("world/stimulus", payload);
      appendInterventionLog(
        "result", "/world/stimulus", { object: response && response.object }, correlationId,
      );
      if (status) status.textContent = `${payload.kind} injected at cell (${x}, ${y}).`;
      await refreshAll();
    } catch (error) {
      appendInterventionLog(
        "error", "/world/stimulus", { message: error.message || String(error) }, correlationId,
      );
      if (status) status.textContent = `Could not inject at cell (${x}, ${y}).`;
      setStatus("error", "Stimulus error");
    } finally {
      worldStimulusPending = false;
      interventionPending = false;
      setInterventionBusy(false);
    }
  }

  const worldCanvas = $("#world-canvas");
  worldCanvas.addEventListener("click", (ev) => {
    worldCursor = mapWorldPointToGrid(ev);
    if (currentWorldSnap) drawWorld(currentWorldSnap);
    void postWorldStimulusAt(worldCursor.x, worldCursor.y);
  });
  worldCanvas.addEventListener("keydown", (ev) => {
    const grid = Math.max(1, Math.round(lastGrid || 12));
    let handled = true;
    if (ev.key === "ArrowLeft") worldCursor.x = clamp((worldCursor.x ?? Math.floor(grid / 2)) - 1, 0, grid - 1);
    else if (ev.key === "ArrowRight") worldCursor.x = clamp((worldCursor.x ?? Math.floor(grid / 2)) + 1, 0, grid - 1);
    else if (ev.key === "ArrowUp") worldCursor.y = clamp((worldCursor.y ?? Math.floor(grid / 2)) - 1, 0, grid - 1);
    else if (ev.key === "ArrowDown") worldCursor.y = clamp((worldCursor.y ?? Math.floor(grid / 2)) + 1, 0, grid - 1);
    else if (ev.key === "Enter" || ev.key === " ") {
      void postWorldStimulusAt(worldCursor.x ?? Math.floor(grid / 2), worldCursor.y ?? Math.floor(grid / 2));
    } else handled = false;
    if (!handled) return;
    ev.preventDefault();
    if (currentWorldSnap) drawWorld(currentWorldSnap);
    const status = $("#world-interaction-status");
    if (status && ev.key !== "Enter" && ev.key !== " ") {
      status.textContent = `Selected cell (${worldCursor.x}, ${worldCursor.y}); press Enter to inject.`;
    }
  });

  $("#btn-step").addEventListener("click", async () => {
    if (stepInFlight) return;
    const generation = horizonGeneration;
    const stepButton = $("#btn-step");
    stepInFlight = true;
    stepButton.disabled = true;
    try {
      const trace = await postJSON("tick");
      if (generation !== horizonGeneration) return;
      applyTrace(trace);
      await refreshAll();
      if (generation !== horizonGeneration) return;
      await refreshMemoryGraph(true);
    } catch (e) { setStatus("error", "Tick error"); }
    finally {
      stepInFlight = false;
      stepButton.disabled = false;
    }
  });

  $("#btn-start").addEventListener("click", async () => {
    const tps = parseFloat($("#input-tps").value) || 4;
    try {
      await postJSON("run", { tps });
      setRunningUI(true);
      startPolling();
    } catch (e) { setStatus("error", "Run error"); }
  });

  $("#btn-pause").addEventListener("click", async () => {
    try {
      await postJSON("pause");
      setRunningUI(false);
      stopPolling();
      refreshAll();
    } catch (e) { setStatus("error", "Pause error"); }
  });

  $("#btn-reset").addEventListener("click", async () => {
    try {
      stopPolling();
      await postJSON("reset", currentConfigPatch());
      resetHorizonClientState();
      setRunningUI(false);
      await refreshAll();
      await refreshMemoryGraph(true);
    } catch (e) { setStatus("error", "Reset error"); }
  });

  // ---------- goal form ----------
  $("#goal-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = $("#goal-input");
    const goal = input.value.trim();
    if (!goal) return;
    try {
      const self = await postJSON("agent/goal", { goal });
      input.value = "";
      renderSelfModel(self);
    } catch (e) { setStatus("error", "Goal error"); }
  });

  // ---------- Phase-7 semantic memory search ----------
  $("#memory-search-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = $("#memory-search-input");
    const host = $("#memory-search-results");
    const button = ev.currentTarget.querySelector("button[type='submit']");
    if (!input || !host) return;
    const query = input.value.trim();
    if (!query) {
      host.innerHTML = '<div class="memory-search-status">Enter a search phrase to query stored episodes.</div>';
      input.focus();
      return;
    }
    const generation = horizonGeneration;
    host.innerHTML = '<div class="memory-search-status">Searching the deterministic semantic index…</div>';
    if (button) button.disabled = true;
    try {
      const payload = await api(`agent/memory/search?q=${encodeURIComponent(query)}&limit=8`);
      if (generation !== horizonGeneration) return;
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      host.innerHTML = results.length
        ? results.map((record) =>
            `<article class="memory-search-result">` +
              `<div class="msr-top">` +
                `<span class="msr-action">${esc(record.action || "unknown action")}</span>` +
                `<span class="msr-meta">t${esc(f0(record.tick))} · imp ${esc(f2(record.importance))} · sim ${esc(f3(record.similarity))}</span>` +
              `</div>` +
              `<div class="msr-summary">${esc(record.summary || "No summary stored.")}</div>` +
            `</article>`
          ).join("")
        : '<div class="memory-search-status">No stored episode matched this query.</div>';
    } catch (e) {
      if (generation !== horizonGeneration) return;
      host.innerHTML = '<div class="memory-search-status is-error">Memory search unavailable. The current run may have no index yet.</div>';
    } finally {
      if (generation === horizonGeneration && button) button.disabled = false;
    }
  });

  function memoryGraphNodeDescription(node) {
    const n = node || {};
    return `${String(n.action || "memory")} at tick ${f0(n.tick)}; ` +
      `importance ${f2(n.importance)}; valence ${f2(n.valence)}; ` +
      `${String(n.summary || "No summary stored.")}`;
  }

  function showMemoryGraphTooltip(canvas, point, clientX, clientY, announce) {
    const tooltip = $("#memory-graph-tooltip");
    if (!tooltip || !canvas || !point) return;
    const node = point.node || {};
    tooltip.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = `${String(node.action || "memory")} · t${f0(node.tick)}`;
    const summaryLine = document.createElement("span");
    summaryLine.textContent = String(node.summary || "No summary stored.");
    const metricLine = document.createElement("span");
    metricLine.textContent = `importance ${f2(node.importance)} · valence ${f2(node.valence)}`;
    tooltip.append(title, document.createElement("br"), summaryLine,
      document.createElement("br"), metricLine);

    const shellRect = canvas.parentElement.getBoundingClientRect();
    const canvasRect = canvas.getBoundingClientRect();
    const anchorX = clientX == null
      ? canvasRect.left - shellRect.left + point.x / canvas.width * canvasRect.width
      : clientX - shellRect.left;
    const anchorY = clientY == null
      ? canvasRect.top - shellRect.top + point.y / canvas.height * canvasRect.height
      : clientY - shellRect.top;
    tooltip.hidden = false;
    tooltip.style.left = "0px";
    tooltip.style.top = "0px";
    const tooltipWidth = tooltip.offsetWidth;
    const tooltipHeight = tooltip.offsetHeight;
    const maxLeft = Math.max(8, shellRect.width - tooltipWidth - 8);
    const maxTop = Math.max(8, shellRect.height - tooltipHeight - 8);
    let left = anchorX + 12;
    let top = anchorY + 12;
    if (left > maxLeft) left = anchorX - tooltipWidth - 12;
    if (top > maxTop) top = anchorY - tooltipHeight - 12;
    tooltip.style.left = clamp(left, 8, maxLeft).toFixed(0) + "px";
    tooltip.style.top = clamp(top, 8, maxTop).toFixed(0) + "px";

    if (announce) {
      const selection = $("#memory-graph-selection");
      const points = Array.isArray(canvas._placedNodes) ? canvas._placedNodes : [];
      if (selection) selection.textContent =
        `Selected memory ${memoryGraphSelection + 1} of ${points.length}: ` +
        memoryGraphNodeDescription(node);
    }
  }

  function selectMemoryGraphNode(index) {
    const canvas = $("#memory-graph");
    const points = canvas && Array.isArray(canvas._placedNodes) ? canvas._placedNodes : [];
    if (!canvas || !points.length) return;
    memoryGraphSelection = clamp(index, 0, points.length - 1);
    drawMemoryGraph(memoryGraphCache);
    showMemoryGraphTooltip(canvas, canvas._placedNodes[memoryGraphSelection], null, null, true);
  }

  // Pointer inspection is optional: the hidden ordered list and keyboard
  // selection expose the same graph without depending on pixels.
  $("#memory-graph")?.addEventListener("pointermove", (ev) => {
    const canvas = ev.currentTarget;
    const tooltip = $("#memory-graph-tooltip");
    const points = Array.isArray(canvas._placedNodes) ? canvas._placedNodes : [];
    if (!tooltip) return;
    if (!points.length) {
      tooltip.hidden = true;
      return;
    }
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) * canvas.width / Math.max(1, rect.width);
    const y = (ev.clientY - rect.top) * canvas.height / Math.max(1, rect.height);
    let hit = null;
    let nearest = Infinity;
    points.forEach((point) => {
      const distance = Math.hypot(point.x - x, point.y - y);
      if (distance <= point.radius + 7 && distance < nearest) {
        hit = point;
        nearest = distance;
      }
    });
    if (!hit) {
      tooltip.hidden = true;
      return;
    }
    showMemoryGraphTooltip(canvas, hit, ev.clientX, ev.clientY, false);
  });
  $("#memory-graph")?.addEventListener("pointerleave", () => {
    const tooltip = $("#memory-graph-tooltip");
    if (tooltip) tooltip.hidden = true;
  });
  $("#memory-graph")?.addEventListener("keydown", (ev) => {
    const canvas = ev.currentTarget;
    const points = Array.isArray(canvas._placedNodes) ? canvas._placedNodes : [];
    if (ev.key === "Escape") {
      ev.preventDefault();
      memoryGraphSelection = -1;
      const tooltip = $("#memory-graph-tooltip");
      if (tooltip) tooltip.hidden = true;
      const selection = $("#memory-graph-selection");
      if (selection) selection.textContent = "Memory graph selection cleared.";
      drawMemoryGraph(memoryGraphCache);
      return;
    }
    if (!points.length || ![
      "ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End",
    ].includes(ev.key)) return;
    ev.preventDefault();
    let next = memoryGraphSelection;
    if (ev.key === "Home") next = 0;
    else if (ev.key === "End") next = points.length - 1;
    else if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
      next = memoryGraphSelection < 0 ? 0 : (memoryGraphSelection + 1) % points.length;
    } else {
      next = memoryGraphSelection < 0
        ? points.length - 1
        : (memoryGraphSelection - 1 + points.length) % points.length;
    }
    selectMemoryGraphNode(next);
  });

  // ============================================================
  //  CONFIG SLIDERS -> POST /config
  // ============================================================
  function fmtSlider(fmt, v) {
    if (fmt === "int" || fmt === "f0") return f0(v);
    if (fmt === "f2") return f2(v);
    return f3(v);
  }
  function configValue(key) {
    const row = document.querySelector(`#config-sliders .slider-row[data-key="${key}"]`);
    if (!row) return null;
    return parseFloat(row.querySelector("input").value);
  }
  function currentConfigPatch() {
    const patch = {};
    document.querySelectorAll("#config-sliders .slider-row").forEach((row) => {
      const key = row.dataset.key;
      let v = parseFloat(row.querySelector("input").value);
      if (row.dataset.fmt === "int") v = Math.round(v);
      patch[key] = v;
    });
    return patch;
  }
  let configDebounce = null;
  document.querySelectorAll("#config-sliders .slider-row").forEach((row) => {
    const input = row.querySelector("input");
    const valEl = row.querySelector(".slider-val");
    const fmt = row.dataset.fmt;
    valEl.textContent = fmtSlider(fmt, input.value);
    input.addEventListener("input", () => { valEl.textContent = fmtSlider(fmt, input.value); });
    input.addEventListener("change", () => {
      clearTimeout(configDebounce);
      configDebounce = setTimeout(async () => {
        try {
          const patch = currentConfigPatch();
          const out = await postJSON("config", patch);
          persistSetting(patch);   // remember the slider values across reloads
          const snap = out && (out.state ? out.state.world : (out.world || out.snapshot));
          if (snap) drawWorld(snap);
          // reflect a possibly-changed ignition threshold on the workspace line
          if (out && out.config && out.config.ignition_threshold != null) {
            $("#threshold-val").textContent = f3(out.config.ignition_threshold);
          }
          // refresh the arousal baseline marker if it changed
          renderArousal(num($("#arousal-val").textContent), configValue("arousal_baseline"));
        } catch (e) { setStatus("error", "Config error"); }
      }, 120);
    });
  });

  // ============================================================
  //  FLAG TOGGLES -> POST /config  (Phase-2 deep + Phase-3 learning/personality)
  // ============================================================
  // checked by default (matches applyDeepDefaults); each flips one feature flag.
  // covers both the #deep-toggles (Phase 2) and #lp-toggles (Phase 3) groups.
  document.querySelectorAll(".panel-config input[data-flag]").forEach((box) => {
    box.addEventListener("change", async () => {
      const flag = box.dataset.flag;
      try {
        await postJSON("config", { [flag]: box.checked });
        persistSetting({ [flag]: box.checked });   // survive reload
        try { refreshCoverage(); } catch (e) { /* non-fatal */ }
      } catch (e) { setStatus("error", "Config error"); }
    });
  });

  $("#btn-horizon-profile")?.addEventListener("click", async (ev) => {
    const button = ev.currentTarget;
    const patch = {};
    HORIZON_FLAGS.forEach((flag) => { patch[flag] = true; });
    button.disabled = true;
    button.textContent = "Activating…";
    try {
      await postJSON("config", patch);
      persistSetting(patch);
      applyControlStates(patch);
      try { await refreshCoverage(); } catch (e) { /* non-fatal */ }
      await refreshAll();
    } catch (e) {
      setStatus("error", "Phase 7 config error");
    } finally {
      button.disabled = false;
      button.textContent = "Activate all Phase 7";
    }
  });

  $("#btn-export-analysis")?.addEventListener("click", () => {
    const opened = window.open(`${API}/export/analysis`, "_blank", "noopener");
    if (opened) opened.opener = null;
  });

  // ============================================================
  //  SOCIETY VIEW (multi-agent) — GET /society
  // ============================================================
  let SOC_SELECTED = 0;

  async function refreshSociety(generation) {
    let data;
    try {
      data = await api("society");
    } catch (e) { return; }
    if (generation != null && generation !== horizonGeneration) return;
    if (!data) return;
    drawSociety(data.world, SOC_SELECTED);
    renderRelations(data.relations, data.agents);
  }

  function drawSociety(world, selected) {
    const cv = document.getElementById("society-canvas");
    if (!cv || !world) return;
    const ctx = cv.getContext("2d");
    const g = num(world.grid_size) || 12, cell = cv.width / g;
    ctx.clearRect(0, 0, cv.width, cv.height);
    const KIND = {
      food: cssVar("--pos"),
      hazard: cssVar("--neg"),
      tool: cssVar("--cool"),
      curio: cssVar("--curio"),
    };
    (world.objects || []).forEach((o) => {
      ctx.fillStyle = KIND[o.kind] || cssVar("--ink-faint");
      ctx.fillRect(o.x * cell + cell * 0.3, o.y * cell + cell * 0.3, cell * 0.4, cell * 0.4);
    });
    (world.agents || []).forEach((a) => {
      ctx.beginPath();
      ctx.arc(a.x * cell + cell / 2, a.y * cell + cell / 2, cell * 0.32, 0, Math.PI * 2);
      ctx.fillStyle = a.id === selected ? cssVar("--accent") : cssVar("--ink");
      ctx.fill();
      ctx.fillStyle = cssVar("--bg-inset");
      ctx.font = `${Math.floor(cell * 0.4)}px sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(String(a.id), a.x * cell + cell / 2, a.y * cell + cell / 2);
    });
  }

  function renderRelations(rel, agents) {
    const box = document.getElementById("society-relations");
    if (!box || !rel) return;
    box.innerHTML = (rel.edges || [])
      .map((e) => `<div class="row"><span class="mono">${esc(e.from)}→${esc(e.to)}</span>` +
                  `<span class="micro">trust ${f2(e.trust)} · ${esc(e.affect)}</span></div>`)
      .join("") || '<div class="micro">No relations yet.</div>';
  }

  document.getElementById("btn-society-apply")?.addEventListener("click", async () => {
    const n = parseInt(document.getElementById("input-nagents").value, 10) || 1;
    try {
      const state = await postJSON("society/config", { n_agents: n });
      resetHorizonClientState();
      setRunningUI(!!(state && state.running));
      if (state && state.running) startPolling();
      else stopPolling();
      await refreshAll();
      await refreshMemoryGraph(true);
    } catch (e) { setStatus("error", "Society error"); }
  });

  document.getElementById("society-canvas")?.addEventListener("click", (ev) => {
    api("society").then((d) => {
      if (!d || !d.world) return;
      const cv = ev.currentTarget, g = num(d.world.grid_size) || 12, cell = cv.width / g;
      const rect = cv.getBoundingClientRect();
      // canvas is CSS-scaled to fit; map client px back to canvas px first
      const sx = cv.width / rect.width, sy = cv.height / rect.height;
      const gx = Math.floor((ev.clientX - rect.left) * sx / cell);
      const gy = Math.floor((ev.clientY - rect.top) * sy / cell);
      const hit = (d.world.agents || []).find((a) => a.x === gx && a.y === gy);
      if (hit) {
        SOC_SELECTED = hit.id;
        document.getElementById("soc-selected").textContent = `viewing agent ${hit.id}`;
      }
      refreshSociety();
    }).catch(() => {});
  });

  // ============================================================
  //  LABORATORY (Phase 4) — time series, scenarios, export, battery
  // ============================================================
  // Draw one polyline per agent for the selected metric, auto-scaling y to the
  // metric's min/max over the window. Reads GET /metrics/history (last 200 rows).
  async function refreshLabChart(generation) {
    const cv = $("#lab-chart");
    if (!cv) return;
    const ctx = cv.getContext("2d");
    const W = cv.width, H = cv.height;
    ctx.clearRect(0, 0, W, H);

    const metric = ($("#lab-metric") && $("#lab-metric").value) || "energy";
    const d = await api("metrics/history?limit=200");
    if (generation != null && generation !== horizonGeneration) return;
    const rows = (d && d.series && d.series.rows) || [];
    if (!rows.length) return;

    // group rows by agent_id, preserving order
    const byAgent = new Map();
    rows.forEach((r) => {
      const id = r.agent_id != null ? r.agent_id : 0;
      let arr = byAgent.get(id);
      if (!arr) { arr = []; byAgent.set(id, arr); }
      arr.push(num(r[metric]));
    });

    // auto-scale y to the min/max of the selected metric across all agents
    let lo = Infinity, hi = -Infinity;
    byAgent.forEach((vals) => vals.forEach((v) => {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }));
    if (!isFinite(lo) || !isFinite(hi)) return;
    if (hi - lo < 1e-9) { hi += 0.5; lo -= 0.5; }

    const pad = 10;
    const maxLen = Math.max(...Array.from(byAgent.values(), (a) => a.length));
    const sx = (i) => pad + (maxLen <= 1 ? 0 : (i / (maxLen - 1)) * (W - 2 * pad));
    const sy = (v) => H - pad - ((v - lo) / (hi - lo)) * (H - 2 * pad);

    const palette = [
      cssVar("--accent"), cssVar("--cool"), cssVar("--pos"),
      cssVar("--curio"), cssVar("--neg"),
    ];

    let ai = 0;
    byAgent.forEach((vals) => {
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = sx(i), y = sy(v);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.strokeStyle = palette[ai % palette.length] || cssVar("--ink-soft");
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ai++;
    });
  }

  $("#lab-metric")?.addEventListener("change", () => {
    refreshLabChart().catch(() => {});
  });

  $("#btn-export-csv")?.addEventListener(
    "click", () => window.open(`${API}/export.csv`, "_blank"));
  $("#btn-export-json")?.addEventListener(
    "click", () => window.open(`${API}/export.json`, "_blank"));

  $("#btn-scenario-run")?.addEventListener("click", async () => {
    const out = $("#lab-scenario-summary");
    let body;
    try {
      body = JSON.parse($("#lab-scenario").value);
    } catch (e) {
      if (out) out.textContent = "parse error: " + e.message;
      return;
    }
    try {
      const res = await postJSON("scenario/run", body);
      const rows = (res && res.series && res.series.rows) || [];
      const summary = res && res.summary != null
        ? (typeof res.summary === "string" ? res.summary : JSON.stringify(res.summary))
        : "";
      if (out) out.textContent = summary + " · " + rows.length + " rows";
    } catch (e) {
      if (out) out.textContent = "run error: " + e.message;
    }
  });

  function runBattery(name, body) {
    return async () => {
      try {
        const r = await postJSON("battery/" + name, body || { seed: 42, ticks: 12 });
        if ($("#lab-battery-result")) {
          $("#lab-battery-result").textContent =
            name + ": score=" + f3(r.score) + " — " + (r.interpretation || "");
        }
        // ALWAYS surface the server's exact honesty caveat
        if ($("#lab-disclaimer") && r.disclaimer != null) {
          $("#lab-disclaimer").textContent = r.disclaimer;
        }
      } catch (e) {
        if ($("#lab-battery-result")) $("#lab-battery-result").textContent = name + " error: " + e.message;
      }
    };
  }
  $("#btn-mirror")?.addEventListener("click", runBattery("mirror"));
  $("#btn-false-memory")?.addEventListener("click", runBattery("false_memory"));
  $("#btn-calibration")?.addEventListener("click", runBattery("calibration"));
  $("#btn-relational-self")?.addEventListener("click", runBattery("relational_self", { seed: 7, ticks: 40 }));
  // Phase 5 — psychophysics signatures of conscious ACCESS (functional only).
  $("#btn-masking")?.addEventListener("click", runBattery("masking", { seed: 42, ticks: 3 }));
  $("#btn-blink")?.addEventListener("click", runBattery("blink", { seed: 42, ticks: 3 }));
  $("#btn-priming")?.addEventListener("click", runBattery("priming", { seed: 42, ticks: 2 }));
  $("#btn-reality-monitor")?.addEventListener("click", runBattery("reality_monitor", { seed: 42, ticks: 40 }));
  $("#btn-language-genesis")?.addEventListener("click", runBattery("language_genesis", { seed: 42, ticks: 120 }));

  // ---------- theory coverage (the honest asymptote checklist) ----------
  // GET /agent/coverage lists every theory-proposed mechanism the project
  // implements and whether it is active in the current config. A level-2
  // coverage checklist — NOT a consciousness score. Refreshed on load and
  // whenever a Settings toggle changes the config.
  async function refreshCoverage() {
    const box = $("#coverage-list");
    if (!box) return;
    let d;
    try { d = await api("agent/coverage"); } catch (e) { return; }
    const items = (d && d.items) || [];
    if ($("#coverage-count")) {
      $("#coverage-count").textContent =
        "— " + num(d.active_count) + "/" + num(d.total) + " mechanisms active";
    }
    box.innerHTML = "";
    const frag = document.createDocumentFragment();
    items.forEach((it) => {
      const row = el("div", "row");
      const top = el("div", "row-top");
      top.appendChild(el("span", "row-title",
        (it.active ? "●" : "○") + " " + esc(it.theory)));
      top.appendChild(el("span", "row-tag", it.flag ? esc(it.flag) : "core"));
      row.appendChild(top);
      row.appendChild(el("div", "row-sub", esc(it.mechanism) + " — " + esc(it.module)));
      frag.appendChild(row);
    });
    if (!items.length) box.appendChild(el("div", "empty", "Coverage unavailable."));
    else box.appendChild(frag);
  }

  // ---------- fast training: headless config + back-to-back ticks ----------
  document.getElementById('btn-fast-train')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-fast-train');
    const out = document.getElementById('train-result');
    const ticks = parseInt(document.getElementById('train-ticks').value, 10) || 1000;
    btn.disabled = true; out.textContent = 'training…';
    try {
      await postJSON('config', { persist_memory: false, trace_logging: false });
      // Reflect the new backend state so the toggles aren't out of sync, and
      // persist it so a reload doesn't silently re-enable per-tick disk I/O.
      document.querySelectorAll('.panel-config input[data-flag="persist_memory"], .panel-config input[data-flag="trace_logging"]')
        .forEach((box) => { box.checked = false; });
      persistSetting({ persist_memory: false, trace_logging: false });
      const t0 = performance.now();
      const r = await postJSON('train', { ticks });
      const secs = (performance.now() - t0) / 1000;
      out.textContent = `ran ${r.ticks_run} ticks in ${secs.toFixed(1)}s (${Math.round(r.ticks_run / secs)} t/s)`;
    } catch (e) {
      out.textContent = 'training failed';
    } finally {
      btn.disabled = false;
      try { refreshAll(); } catch (_) {}
    }
  });

  // ---------- checkpoints: save / list / load / delete a full run ----------
  // On-demand only (never polled): refreshed once on init and after each
  // save/load/delete. A checkpoint captures the whole run (world, agents,
  // learned state, memory, RNG); Load restores the live run in place.
  function setCkptStatus(msg) {
    const s = document.getElementById("ckpt-status");
    if (s) s.textContent = msg || "";
  }

  async function refreshCheckpoints() {
    const box = document.getElementById("ckpt-list");
    if (!box) return;
    let data;
    try {
      data = await api("checkpoint/list");
    } catch (e) {
      setCkptStatus("list failed");
      return;
    }
    const list = (data && data.checkpoints) || [];
    box.innerHTML = "";
    if (!list.length) {
      box.appendChild(el("div", "empty", "No checkpoints saved."));
      return;
    }
    const frag = document.createDocumentFragment();
    list.forEach((c) => {
      const name = c.name != null ? String(c.name) : "";
      const row = el("div", "row");
      const top = el("div", "row-top");
      const title = el("span", "row-title");
      title.textContent = name;
      const tag = el("span", "row-tag");
      tag.textContent = "tick " + num(c.tick) + " · " + num(c.n_agents) + " agents";
      top.appendChild(title);
      top.appendChild(tag);

      const sub = el("div", "row-sub");
      sub.textContent = (c.saved_at != null ? String(c.saved_at) : "—") +
        (c.bytes != null ? " · " + num(c.bytes) + " B" : "");

      const actions = el("div", "ckpt-actions");
      const loadBtn = el("button", "btn btn-quiet micro");
      loadBtn.textContent = "Load";
      if (c.compatible === false) {
        loadBtn.disabled = true;
        loadBtn.title = "Legacy checkpoint: incompatible with this build";
        tag.textContent += " · legacy";
      }
      loadBtn.addEventListener("click", async () => {
        setCkptStatus("loading " + name + "…");
        try {
          const r = await postJSON("checkpoint/load", { name });
          setCkptStatus("loaded " + name + " @ tick " + num(r && r.tick));
          resetHorizonClientState();
          await refreshAll();
          await refreshMemoryGraph(true);
        } catch (e) {
          setCkptStatus("load failed");
        }
      });
      const delBtn = el("button", "btn btn-quiet micro");
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", async () => {
        setCkptStatus("deleting " + name + "…");
        try {
          await postJSON("checkpoint/delete", { name });
          setCkptStatus("deleted " + name);
          refreshCheckpoints();
        } catch (e) {
          setCkptStatus("delete failed");
        }
      });
      actions.appendChild(loadBtn);
      actions.appendChild(delBtn);

      row.appendChild(top);
      row.appendChild(sub);
      row.appendChild(actions);
      frag.appendChild(row);
    });
    box.appendChild(frag);
  }

  document.getElementById("btn-ckpt-save")?.addEventListener("click", async () => {
    const input = document.getElementById("ckpt-name");
    const name = (input && input.value.trim()) || "run";
    setCkptStatus("saving…");
    try {
      const r = await postJSON("checkpoint/save", { name });
      setCkptStatus("saved " + (r && r.name != null ? r.name : name) +
        " @ tick " + num(r && r.tick));
      refreshCheckpoints();
    } catch (e) {
      setCkptStatus("save failed");
    }
  });

  // ---------- optional LLM narrator: on-demand, grounded in real variables ----------
  // POST /agent/narrate renders agent 0's REAL internal variables into a fluent
  // narration via the configured LLM. It is generated TEXT, not evidence of
  // consciousness or lived experience. Fired only on click (each call costs an
  // API request); never polled. 503 = no key configured, 502 = provider error —
  // api() throws on both, so degrade to a small inline message.
  document.getElementById('btn-narrate')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-narrate');
    const status = document.getElementById('narrate-status');
    const out = document.getElementById('narrate-output');
    const modelEl = document.getElementById('narrate-model');
    btn.disabled = true; status.textContent = 'narrating…';
    try {
      const r = await postJSON('agent/narrate', {});
      out.textContent = r.narration || '(empty)';
      out.hidden = false;
      modelEl.textContent = 'Generated from internal variables by ' +
        (r.model || 'the LLM') + ' — text, not lived experience.';
      modelEl.hidden = false;
      status.textContent = '';
    } catch (e) {
      status.textContent = 'LLM narrator unavailable (set OPENROUTER_API_KEY in .env).';
      out.hidden = true; modelEl.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });

  // ---------- optional LLM functional probes: grounding audit + report card ----------
  // Both are on-demand only (never polled); each click costs one LLM request.
  // NEITHER assesses consciousness. The grounding audit uses the LLM as a
  // skeptical auditor scoring whether the agent's introspective answers are
  // GROUNDED in its real internal variables (reportability fidelity); a high
  // score means faithful, non-confabulated reporting — NOT experience. The
  // report card is a plain-language summary of the FUNCTIONAL test batteries.
  // 503 = no key configured, 502 = provider error — api() throws on both, so we
  // degrade to the same inline "unavailable" message the narrator uses. The
  // backend's own disclaimer/interpretation are rendered verbatim.
  const AUDIT_UNAVAIL = "LLM auditor unavailable (set OPENROUTER_API_KEY in .env).";

  document.getElementById('btn-audit')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-audit');
    const status = document.getElementById('llmprobe-status');
    const box = document.getElementById('audit-result');
    btn.disabled = true;
    if (status) status.textContent = 'auditing…';
    try {
      const r = await postJSON('agent/audit', {});
      box.innerHTML = "";
      // header: reportability fidelity score + the backend's interpretation
      const head = el("div", "row");
      const top = el("div", "row-top");
      top.appendChild(el("span", "row-title", "Reportability fidelity"));
      top.appendChild(el("span", "row-tag mono", f2(r.score)));
      head.appendChild(top);
      if (r.interpretation) head.appendChild(el("div", "row-sub", esc(r.interpretation)));
      box.appendChild(head);
      // one row per verdict: FAITHFUL / CONFAB tag + the question + note
      const verdicts = (r.detail && r.detail.verdicts) || [];
      verdicts.forEach((v) => {
        const row = el("div", "row");
        const vtop = el("div", "row-top");
        const faithful = !!v.faithful;
        const tag = el("span", "row-title " + (faithful ? "verdict-faithful" : "verdict-confab"));
        tag.textContent = faithful ? "FAITHFUL" : "CONFAB";
        vtop.appendChild(tag);
        if (v.question) vtop.appendChild(el("span", "row-tag", esc(v.question)));
        row.appendChild(vtop);
        if (v.note) row.appendChild(el("div", "row-sub", esc(v.note)));
        box.appendChild(row);
      });
      box.hidden = false;
      if (status) status.textContent = '';
    } catch (e) {
      if (status) status.textContent = AUDIT_UNAVAIL;
      box.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById('btn-report-card')?.addEventListener('click', async () => {
    const btn = document.getElementById('btn-report-card');
    const status = document.getElementById('llmprobe-status');
    const out = document.getElementById('report-card-out');
    btn.disabled = true;
    // runs the batteries + an LLM call server-side, so it can take ~5-15s
    if (status) status.textContent = 'compiling… (runs the batteries + LLM, ~10s)';
    try {
      const r = await postJSON('agent/report-card', {});
      out.textContent = r.report_card || '(empty)';
      out.hidden = false;
      if (status) status.textContent = '';
    } catch (e) {
      if (status) status.textContent = AUDIT_UNAVAIL;
      out.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });

  // ---------- the language organ: converse / biography / cross-examination /
  // inner voice. All on-demand LLM renderings of the REAL state — grounded
  // server-side, never a witness, never a judge of consciousness. ----------
  const conversationHistory = [];

  $("#converse-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = $("#converse-input");
    const log = $("#converse-log");
    const btn = $("#btn-converse");
    const question = (input.value || "").trim();
    if (!question || !log) return;
    // render the interviewer's turn immediately
    log.hidden = false;
    const qEl = el("div", "cv-turn cv-q");
    qEl.appendChild(el("span", "cv-who", "interviewer"));
    qEl.appendChild(el("div", "cv-text", esc(question)));
    log.appendChild(qEl);
    input.value = "";
    btn.disabled = true;
    const aEl = el("div", "cv-turn cv-a");
    aEl.appendChild(el("span", "cv-who", "agent (LLM rendering)"));
    const aText = el("div", "cv-text", "…");
    aEl.appendChild(aText);
    log.appendChild(aEl);
    log.scrollTop = log.scrollHeight;
    try {
      const r = await postJSON("agent/converse",
        { question, history: conversationHistory.slice(-6) });
      aText.innerHTML = esc(r.answer || "(empty)");
      conversationHistory.push({ role: "interviewer", content: question });
      conversationHistory.push({ role: "agent", content: r.answer || "" });
    } catch (e) {
      aText.innerHTML = esc("LLM unavailable (set OPENROUTER_API_KEY in .env).");
      aEl.classList.add("cv-error");
    } finally {
      btn.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  });

  $("#btn-biography")?.addEventListener("click", async () => {
    const btn = $("#btn-biography");
    const status = $("#organ-status");
    const out = $("#biography-out");
    btn.disabled = true;
    if (status) status.textContent = "writing the life story from the real records…";
    try {
      const r = await postJSON("agent/biography", {});
      out.textContent = r.biography || "(empty)";
      out.hidden = false;
      if (status) status.textContent = "";
    } catch (e) {
      if (status) status.textContent = "LLM unavailable (set OPENROUTER_API_KEY in .env).";
      out.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });

  $("#btn-cross-examine")?.addEventListener("click", async () => {
    const btn = $("#btn-cross-examine");
    const status = $("#organ-status");
    const box = $("#crossx-out");
    btn.disabled = true;
    // runs the functional batteries + one LLM call server-side
    if (status) status.textContent = "cross-examining… (runs the batteries + LLM, ~20-40s)";
    try {
      const r = await postJSON("agent/cross-examine", {});
      box.innerHTML = "";
      const section = (title, text, cls) => {
        if (!text) return;
        const row = el("div", "row" + (cls ? " " + cls : ""));
        const top = el("div", "row-top");
        top.appendChild(el("span", "row-title", title));
        row.appendChild(top);
        row.appendChild(el("div", "row-sub", esc(text)));
        box.appendChild(row);
      };
      section("The strongest honest case for", r.case_for);
      section("The strongest rebuttal", r.case_against);
      section("Verdict — undecidable in principle", r.verdict, "crossx-verdict");
      const g = r.grounding || {};
      section("Grounding", "coverage " + (g.coverage || "—") + " · probes: " +
        Object.entries(g.probes || {}).map(([k, v]) => k + "=" + f2(v)).join(" · "));
      box.hidden = false;
      if (status) status.textContent = "";
    } catch (e) {
      if (status) status.textContent = "LLM unavailable (set OPENROUTER_API_KEY in .env).";
      box.hidden = true;
    } finally {
      btn.disabled = false;
    }
  });

  $("#btn-inner-voice")?.addEventListener("click", async () => {
    const btn = $("#btn-inner-voice");
    const status = $("#inner-voice-status");
    btn.disabled = true;
    if (status) status.textContent = "generating…";
    try {
      const r = await postJSON("agent/inner-voice", {});
      if (status) {
        status.textContent = r.entered
          ? "“" + (r.utterance || "") + "” — queued for the next ignition competition"
          : (r.note || "not queued");
      }
    } catch (e) {
      if (status) status.textContent = "LLM unavailable (set OPENROUTER_API_KEY in .env).";
    } finally {
      btn.disabled = false;
    }
  });

  // ============================================================
  //  INIT
  // ============================================================
  ensureMetricCells();
  drawWorld(null);
  drawCircadianDial(1);
  drawMemoryGraph(memoryGraphCache);
  renderIgnitionDynamics(null, -1);
  // apply the saved settings (or first-run defaults), then take the first reading
  async function bootstrap() {
    try { await applyDeepDefaults(); } catch (e) { /* first reading still useful */ }
    await refreshAll();
    try { await refreshCoverage(); } catch (e) { /* non-fatal */ }
    try { await refreshMemoryGraph(true); } catch (e) { /* non-fatal */ }
    try { await refreshCheckpoints(); } catch (e) { /* non-fatal */ }
  }
  void bootstrap();
  // load the checkpoint list once (on-demand only — not in the polling loop)

  // compact the sticky masthead once the user scrolls into the instrument
  // (the framing epigraph folds away; the transport stays within reach)
  let mastheadCompact = false;
  window.addEventListener("scroll", () => {
    const scrolled = window.scrollY > 40;
    if (scrolled !== mastheadCompact) {
      mastheadCompact = scrolled;
      document.body.classList.toggle("is-scrolled", scrolled);
    }
  }, { passive: true });
})();
