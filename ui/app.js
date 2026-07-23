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
  // Coalition sources are colored via the themed --src-* custom properties
  // (styles.css), so the timeline/legend/bars re-tint with the theme and stay
  // AA on both inset surfaces. Any source outside the known set maps to unknown.
  const SOURCE_KEYS = [
    "perception", "memory", "self", "emotion", "goal", "imagination",
    "dream", "social", "inner_speech", "wandering", "language",
    "motivation", "prediction_error", "interoception", "metacognition",
    "concept", "unknown",
  ];
  const sourceKey = (source) => {
    const key = String(source || "unknown").toLowerCase();
    return SOURCE_KEYS.includes(key) ? key : "unknown";
  };
  const sourceCssVar = (source) => "var(--src-" + sourceKey(source) + ")";
  const SOURCE_COLORS = new Proxy({}, {
    get: (_t, source) => cssVar("--src-" + sourceKey(source)),
  });
  const HORIZON_FLAGS = [
    "phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
    "vector_memory_enabled", "td_learning_enabled", "mind_wandering_enabled",
    "world_dynamics_enabled", "tasks_enabled",
  ];
  const GENDER_HOSTILE_EVENTS = new Set([
    "misgendering", "invalidation", "rejection", "discrimination",
    "threat", "care_barrier", "access_denied",
  ]);

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
    if (!res.ok) {
      const err = new Error(`${path} -> ${res.status}`);
      err.status = res.status;
      try { err.detail = await res.json(); } catch (e) { /* no JSON body */ }
      throw err;
    }
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
      const parsed = raw ? JSON.parse(raw) : null;
      // Phase 8 requires a complete, explicit scenario reset. A stale browser
      // preference must never activate the mechanism or invent a profile.
      if (parsed && typeof parsed === "object") delete parsed.gender_experience_enabled;
      return parsed;
    } catch (e) { return null; }
  }
  function saveSettings(obj) {
    try {
      const safe = { ...(obj || {}) };
      delete safe.gender_experience_enabled;
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(safe));
    } catch (e) { /* ignore */ }
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
  // shell / instrument client state (Le Méridien redesign)
  let clientConfig = {};            // last GET /config dump (perception radius, nominal threshold…)
  let lastWorkspaceState = null;    // last workspace payload fed to the aperture
  let lastFullWorkspace = null;     // last payload WITH competition[] (the /agent/consciousness echo is reduced)
  let lastSocietyData = null;       // last GET /society payload (society view + minis + inspector)
  let lastDaylight = 1;             // last circadian daylight (theme retint)
  let lastIsSleeping = false;       // aperture ASLEEP state
  let prevIgnitedForPulse = false;  // rising-edge detector for the one-shot aperture pulse
  let dynCursor = -1;               // keyboard cursor into ignitionHistory (-1 = follow latest)
  let pollFailures = 0;             // consecutive poll batch failures (connection banner)
  const pendingViewDraws = new Set(); // canvases skipped while their view was hidden
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)");

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
  // Phase 8 client boundary: ordinary and public reads refresh in the poll.
  // The private/debug payload only exists after the user explicitly reveals it.
  let genderCatalog = [];
  let genderManifestDraft = null;
  let genderPayload = null;
  let genderSocietyPayload = null;
  let genderDebugPayload = null;
  let genderProbeHistory = [];
  let genderActivePresetId = null;
  let genderSyncedProfileId = null;
  let genderControlsBound = false;

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
    genderPayload = null;
    genderSocietyPayload = null;
    genderDebugPayload = null;
    genderProbeHistory = [];
    genderSyncedProfileId = null;

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
    renderGenderExperience(null, null);
  }

  // ============================================================
  //  STATUS + THEME
  // ============================================================
  let lastErrorToast = { text: "", at: 0 };
  function setStatus(kind, text) {
    const pill = $("#status-pill");
    pill.className = "pill pill-" + kind;
    $("#status-label").textContent = text;
    // surface errors as a toast too (deduped) — the pill alone is easy to miss
    if (kind === "error") {
      const now = performance.now();
      if (text !== lastErrorToast.text || now - lastErrorToast.at > 6000) {
        lastErrorToast = { text, at: now };
        toast(text, "error");
      }
    }
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
      retintAllCanvases(); // every themed canvas + the aperture, not just three
    });
  })();

  // ============================================================
  //  CANVAS SCALING (HiDPI) + VIEW-VISIBILITY GATING
  // ============================================================
  // Every canvas keeps its LOGICAL design size for all drawing math; the
  // backing store is sized to CSS width × devicePixelRatio (capped at 2) and
  // the context transform maps logical→device. Hit-tests stay in logical
  // coordinates (client px are converted with the logical size, not .width).
  function ensureCanvasScale(canvas, logicalW, logicalH) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cssW = canvas.clientWidth || logicalW;
    const k = (cssW / logicalW) * dpr;
    const w = Math.max(1, Math.round(logicalW * k));
    const h = Math.max(1, Math.round(logicalH * k));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(k, 0, 0, k, 0, 0);
    return ctx;
  }
  // One ResizeObserver per canvas, created once (WeakSet guard) — the resize
  // callback only marks + redraws through the canvas's own draw entry point.
  const observedCanvases = new WeakSet();
  function observeCanvasResize(canvas, redraw) {
    if (!canvas || observedCanvases.has(canvas) || typeof ResizeObserver === "undefined") return;
    observedCanvases.add(canvas);
    let raf = 0;
    const ro = new ResizeObserver(() => {
      if (raf) return;
      raf = requestAnimationFrame(() => { raf = 0; redraw(); });
    });
    ro.observe(canvas);
  }
  // A canvas inside a hidden view has no layout box: skip the draw, remember it,
  // and flush when the view becomes active again (see the router).
  function canvasVisible(el) { return !!(el && el.offsetParent !== null); }

  // read CSS vars so the canvas matches the active theme — memoized per theme
  // (getComputedStyle is costly at 350ms poll cadence; the cache is invalidated
  // on every theme toggle).
  let cssVarCache = Object.create(null);
  function cssVar(name) {
    let v = cssVarCache[name];
    if (v == null) {
      v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      cssVarCache[name] = v;
    }
    return v;
  }
  function invalidateCssVars() { cssVarCache = Object.create(null); }

  // Redraw every themed surface after a palette change (all canvases + aperture).
  function retintAllCanvases() {
    invalidateCssVars();
    if (currentWorldSnap) drawWorld(currentWorldSnap);
    renderIgnitionDynamics(null, lastTick);
    drawMemoryGraph(memoryGraphCache);
    drawCircadianDial(lastDaylight);
    if (lastSocietyData) renderSocietyAll(lastSocietyData);
    refreshLabChart().catch(() => {});
    updateAperture(lastWorkspaceState);
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

  // kind → distinct SHAPE (never color alone): food=disc, hazard=triangle,
  // tool=square, curio=diamond. Shared by the world map, the society map and
  // the overview miniatures.
  function traceKindShape(ctx, kind, cx, cy, r) {
    ctx.beginPath();
    if (kind === "hazard") {
      ctx.moveTo(cx, cy - r);
      ctx.lineTo(cx + r * 0.92, cy + r * 0.78);
      ctx.lineTo(cx - r * 0.92, cy + r * 0.78);
      ctx.closePath();
    } else if (kind === "tool") {
      ctx.rect(cx - r * 0.82, cy - r * 0.82, r * 1.64, r * 1.64);
    } else if (kind === "curio") {
      ctx.moveTo(cx, cy - r);
      ctx.lineTo(cx + r, cy);
      ctx.lineTo(cx, cy + r);
      ctx.lineTo(cx - r, cy);
      ctx.closePath();
    } else {
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
    }
  }

  const WORLD_L = 560; // logical drawing size of the two big grid canvases

  function drawWorld(snapshot) {
    currentWorldSnap = snapshot;
    drawMiniWorld(snapshot); // the overview echo has its own visibility gate
    const canvas = $("#world-canvas");
    if (!canvasVisible(canvas)) { pendingViewDraws.add("world"); return; }
    const ctx = ensureCanvasScale(canvas, WORLD_L, WORLD_L);
    const W = WORLD_L, H = WORLD_L;
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

    // perception radius ring — the REAL configured radius (the legacy /state
    // snapshot has no radius field; the hardcoded 3 was a silent lie).
    const radius = num(clientConfig.perception_radius) ||
      num(snapshot && snapshot.radius) || 3;
    ctx.beginPath();
    ctx.arc(center(agent.x), center(agent.y), (radius + 0.5) * cell, 0, Math.PI * 2);
    ctx.strokeStyle = agentCol;
    ctx.globalAlpha = 0.45;
    ctx.setLineDash([4, 6]);
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // objects: SHAPE = kind, size hints novelty, opacity hints danger
    const objs = (snapshot && snapshot.objects) || [];
    objs.forEach((o) => {
      const color = kindColor[o.kind] || cssVar("--ink-faint");
      const novelty = clamp01(num(o.novelty));
      const danger = clamp01(num(o.danger));
      const r = cell * (0.18 + 0.2 * novelty);
      const alpha = 0.5 + 0.4 * Math.max(danger, o.kind === "hazard" ? 0.35 : 0.18);
      ctx.globalAlpha = Math.min(1, alpha);
      ctx.fillStyle = color;
      traceKindShape(ctx, o.kind, center(o.x), center(o.y), r);
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

    canvas.setAttribute("aria-label",
      `World grid ${grid}×${grid}, tick ${num(snapshot && snapshot.tick)}, ` +
      `${objs.length} object${objs.length === 1 ? "" : "s"}, agent at ${agent.x},${agent.y}. ` +
      "Interactive: click or use arrow keys then Enter to inject a stimulus.");
    renderWorldCellDetail(snapshot, agent, radius);
    renderWorldObjectsTable(snapshot, agent);
  }

  // Inspector for the selected cell — real fields of the objects standing there.
  function renderWorldCellDetail(snapshot, agent, radius) {
    const host = $("#world-cell-detail");
    if (!host) return;
    if (worldCursor.x == null || worldCursor.y == null) {
      host.innerHTML = '<span class="micro">Select a cell (pointer or arrows) to inspect it.</span>';
      return;
    }
    const cx = worldCursor.x, cy = worldCursor.y;
    const objs = ((snapshot && snapshot.objects) || [])
      .filter((o) => num(o.x) === cx && num(o.y) === cy);
    const ag = agent || (snapshot && snapshot.agent) || {};
    const dist = Math.abs(num(ag.x) - cx) + Math.abs(num(ag.y) - cy);
    const inRadius = dist <= (radius || 3);
    const parts = [];
    parts.push(`<span class="wcd-title mono">cell (${cx}, ${cy})</span>`);
    if (num(ag.x) === cx && num(ag.y) === cy) {
      parts.push(`<div>agent here · energy ${f2(ag.energy)}</div>`);
    }
    if (!objs.length) {
      parts.push('<div class="micro">empty cell</div>');
    } else {
      objs.forEach((o) => {
        parts.push(
          `<div><b class="kind-${esc(o.kind)}">${esc(o.kind)}</b> #${num(o.id)} · ` +
          `danger ${f2(o.danger)} · novelty ${f2(o.novelty)} · utility ${f2(o.utility)}</div>`);
      });
    }
    parts.push(`<div class="micro">distance to agent ${dist} · ` +
      `${inRadius ? "inside" : "outside"} perception radius (${radius || 3})</div>`);
    host.innerHTML = parts.join("");
  }

  // Non-graphical equivalent of the world canvas: every object, by distance.
  function renderWorldObjectsTable(snapshot, agent) {
    const tbody = document.querySelector("#world-objects-table tbody");
    if (!tbody) return;
    const ag = agent || (snapshot && snapshot.agent) || { x: 0, y: 0 };
    const objs = ((snapshot && snapshot.objects) || []).slice()
      .sort((a, b) =>
        (Math.abs(num(a.x) - ag.x) + Math.abs(num(a.y) - ag.y)) -
        (Math.abs(num(b.x) - ag.x) + Math.abs(num(b.y) - ag.y)));
    tbody.replaceChildren();
    if (!objs.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = '<td colspan="6" class="micro">No objects in the world.</td>';
      tbody.appendChild(tr);
      return;
    }
    const frag = document.createDocumentFragment();
    objs.forEach((o) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td class="kind-${esc(o.kind)}">${esc(o.kind)}</td>` +
        `<td class="num">${num(o.id)}</td>` +
        `<td class="num">${num(o.x)},${num(o.y)}</td>` +
        `<td class="num">${f2(o.danger)}</td>` +
        `<td class="num">${f2(o.novelty)}</td>` +
        `<td class="num">${f2(o.utility)}</td>`;
      frag.appendChild(tr);
    });
    tbody.appendChild(frag);
  }

  // Overview miniature — same real snapshot, reduced glyphs, click-through to #/world.
  function drawMiniWorld(snapshot) {
    const canvas = $("#overview-world-mini");
    if (!canvas) return;
    if (!canvasVisible(canvas)) { pendingViewDraws.add("overview"); return; }
    const L = 220;
    const ctx = ensureCanvasScale(canvas, L, L);
    ctx.clearRect(0, 0, L, L);
    const grid = num(snapshot && snapshot.grid_size) || lastGrid || 12;
    const cell = L / grid;
    const center = (c) => c * cell + cell / 2;
    const kindColor = {
      food: cssVar("--pos"), hazard: cssVar("--neg"),
      tool: cssVar("--cool"), curio: cssVar("--curio"),
    };
    ((snapshot && snapshot.objects) || []).forEach((o) => {
      ctx.fillStyle = kindColor[o.kind] || cssVar("--ink-faint");
      ctx.globalAlpha = 0.8;
      traceKindShape(ctx, o.kind, center(o.x), center(o.y), Math.max(2.4, cell * 0.2));
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    const agent = (snapshot && snapshot.agent) || { x: grid / 2, y: grid / 2 };
    ctx.beginPath();
    ctx.arc(center(agent.x), center(agent.y), Math.max(3, cell * 0.3), 0, Math.PI * 2);
    ctx.fillStyle = cssVar("--accent");
    ctx.fill();
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
  // Also feeds the Ignition Aperture (the Overview's signature dial).
  function renderIgnitionGate(ws) {
    if (!ws) return;
    lastWorkspaceState = ws;
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
    updateAperture(ws);
  }

  // ============================================================
  //  IGNITION APERTURE — the instrument's signature dial (#/overview)
  // ============================================================
  // A 240° dial (150°→390°, gap at the bottom). The score arc is the real
  // ignition_score; the faint engraved band is the ignition zone beyond the
  // EFFECTIVE threshold; the ghost tick marks the NOMINAL configured threshold
  // — the visible gap between the two ticks IS the arousal/homeostatic
  // modulation, drawn honestly. The inner arc is broadcast strength. It only
  // pulses on a REAL ignition rising edge (and never under reduced motion).
  const AP = { cx: 170, cy: 164, r: 126, rIn: 102, a0: 150, sweep: 240 };
  function apPoint(r, v) {
    const th = (AP.a0 + clamp01(v) * AP.sweep) * Math.PI / 180;
    return [AP.cx + r * Math.cos(th), AP.cy + r * Math.sin(th)];
  }
  function apArc(r, v0, v1) {
    const [x0, y0] = apPoint(r, v0);
    const [x1, y1] = apPoint(r, v1);
    const large = (clamp01(v1) - clamp01(v0)) * AP.sweep > 180 ? 1 : 0;
    return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
  }
  let apertureNodes = null;
  function buildAperture(svg) {
    svg.replaceChildren();
    for (let i = 0; i <= 40; i++) {
      const v = i / 40, major = i % 10 === 0;
      const [x0, y0] = apPoint(AP.r + 9, v);
      const [x1, y1] = apPoint(AP.r + (major ? 19 : 14), v);
      svg.appendChild(svgEl("line", {
        x1: x0.toFixed(1), y1: y0.toFixed(1), x2: x1.toFixed(1), y2: y1.toFixed(1),
        class: major ? "ap-tick-major" : "ap-tick",
      }));
      if (major) {
        const [lx, ly] = apPoint(AP.r + 30, v);
        const t = svgEl("text", {
          x: lx.toFixed(1), y: ly.toFixed(1), class: "ap-tick-label",
          "text-anchor": "middle", "dominant-baseline": "middle",
        });
        t.textContent = v === 0 ? ".00" : v === 1 ? "1.0" : v.toFixed(2).slice(1);
        svg.appendChild(t);
      }
    }
    const mk = (tag, attrs) => { const node = svgEl(tag, attrs); svg.appendChild(node); return node; };
    const text = (y, cls) => {
      const t = mk("text", { x: AP.cx, y, class: cls, "text-anchor": "middle" });
      return t;
    };
    apertureNodes = {
      track: mk("path", { d: apArc(AP.r, 0, 1), class: "ap-track" }),
      zone: mk("path", { class: "ap-zone", d: "" }),
      scoreArc: mk("path", { class: "ap-score-arc", d: "" }),
      broadcastArc: mk("path", { class: "ap-broadcast-arc", d: "" }),
      nominalTick: mk("line", { class: "ap-nominal" }),
      effTick: mk("line", { class: "ap-eff" }),
      state: text(AP.cy - 40, "ap-state"),
      score: text(AP.cy + 8, "ap-score"),
      thresholdLine: text(AP.cy + 30, "ap-threshold"),
      winner: text(AP.cy + 54, "ap-winner"),
      content: text(AP.cy + 72, "ap-content"),
    };
  }
  function apSetTick(node, v, len) {
    const [x0, y0] = apPoint(AP.r - len, v);
    const [x1, y1] = apPoint(AP.r + len, v);
    node.setAttribute("x1", x0.toFixed(1)); node.setAttribute("y1", y0.toFixed(1));
    node.setAttribute("x2", x1.toFixed(1)); node.setAttribute("y2", y1.toFixed(1));
    node.setAttribute("visibility", "visible");
  }
  function updateAperture(ws) {
    const svg = $("#aperture");
    if (!svg) return;
    if (!canvasVisible(svg)) { pendingViewDraws.add("overview"); return; }
    if (!apertureNodes || !svg.childElementCount) buildAperture(svg);
    const n = apertureNodes;
    const hasData = !!ws && lastTick >= 0;
    if (!hasData) {
      n.zone.setAttribute("d", ""); n.scoreArc.setAttribute("d", "");
      n.broadcastArc.setAttribute("d", "");
      n.nominalTick.setAttribute("visibility", "hidden");
      n.effTick.setAttribute("visibility", "hidden");
      n.state.textContent = "AWAITING";
      n.score.textContent = "—";
      n.thresholdLine.textContent = "no cycle yet";
      n.winner.textContent = ""; n.content.textContent = "";
      svg.classList.remove("is-ignited", "is-asleep");
      svg.setAttribute("aria-label", "Ignition aperture: no cycle yet");
      return;
    }
    const score = clamp01(num(ws.ignition_score));
    const eff = clamp01(num(ws.effective_threshold != null ? ws.effective_threshold : ws.threshold));
    const nominal = clamp01(num(
      clientConfig.ignition_threshold != null ? clientConfig.ignition_threshold : ws.threshold));
    const broadcast = clamp01(num(ws.broadcast_strength));
    const ignited = !!ws.ignited;
    const asleep = !!lastIsSleeping;
    n.zone.setAttribute("d", eff < 0.996 ? apArc(AP.r, eff, 1) : "");
    n.scoreArc.setAttribute("d", score > 0.004 ? apArc(AP.r, 0, score) : "");
    n.broadcastArc.setAttribute("d", broadcast > 0.004 ? apArc(AP.rIn, 0, broadcast) : "");
    apSetTick(n.effTick, eff, 12);
    apSetTick(n.nominalTick, nominal, 8);
    svg.classList.toggle("is-ignited", ignited);
    svg.classList.toggle("is-asleep", asleep);
    n.state.textContent = asleep ? "ASLEEP" : (ignited ? "GLOBAL ACCESS" : "SUBLIMINAL");
    n.score.textContent = f3(score);
    n.thresholdLine.textContent = "threshold " + f3(eff) +
      (Math.abs(eff - nominal) > 0.002 ? " · nominal " + f3(nominal) : "");
    n.winner.textContent = ws.winner_source || "";
    n.winner.style.fill = ws.winner_source ? sourceCssVar(ws.winner_source) : "";
    const content = ws.winner_content || "";
    n.content.textContent = content
      ? "“" + (content.length > 44 ? content.slice(0, 43) + "…" : content) + "”"
      : "";
    if (ignited && !prevIgnitedForPulse && !REDUCED_MOTION.matches) {
      svg.classList.remove("igniting");
      void svg.getBoundingClientRect();
      svg.classList.add("igniting");
      setTimeout(() => svg.classList.remove("igniting"), 320);
    }
    prevIgnitedForPulse = ignited;
    if ($("#ap-strength")) $("#ap-strength").textContent =
      ws.winner_strength != null ? f3(ws.winner_strength) : "—";
    if ($("#ap-dominance")) $("#ap-dominance").textContent =
      ws.dominance != null ? f3(ws.dominance) : "—";
    if ($("#ap-arousal")) $("#ap-arousal").textContent =
      ws.arousal != null ? f3(ws.arousal) : "—";
    svg.setAttribute("aria-label",
      `Ignition aperture: score ${f3(score)} against effective threshold ${f3(eff)} — ` +
      (asleep ? "asleep" : ignited ? "global access (ignited)" : "present but subliminal") +
      (ws.winner_source ? `. Winning source ${ws.winner_source}.` : "."));
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

  // HOT readouts: calibrated horizontal meters (comparable, unlike the old
  // repeated half-circle gauges) — the ids stayed, the geometry changed.
  function setGauge(fillSel, valSel, v) {
    const fill = $(fillSel);
    if (fill) fill.style.width = (clamp01(v) * 100).toFixed(1) + "%";
    const val = $(valSel);
    if (val) val.textContent = f2(v);
    const meter = fill && fill.parentElement;
    if (meter && meter.getAttribute("role") === "meter") {
      meter.setAttribute("aria-valuenow", clamp01(v).toFixed(3));
    }
  }

  function renderWorkspace(ws) {
    if (!ws) return;
    const box = $("#coalitions");
    // effective (arousal-modulated, homeostatic) cutoff — the live bar the
    // ignition_score must clear. Falls back to the nominal threshold.
    const threshold = clamp01(
      num(ws.effective_threshold != null ? ws.effective_threshold : ws.threshold) || 0.30
    );

    // The /agent/consciousness echo of the workspace is REDUCED (no
    // competition[]); keep the last full payload so the bars never blank out
    // mid-run when only the echo arrives.
    if (Array.isArray(ws.competition) && ws.competition.length) lastFullWorkspace = ws;
    const barSource = Array.isArray(ws.competition) && ws.competition.length
      ? ws : (lastFullWorkspace || ws);

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

    // Decision banner — the HONEST scale: ignition_score (winner strength ×
    // dominance, arousal-modulated) against the effective threshold. The bars
    // below are softmax SHARES of the broadcast field, an incommensurable
    // scale, so the threshold no longer cuts across them.
    const scoreEl = $("#ws-score");
    if (scoreEl) scoreEl.textContent = ws.ignition_score != null ? f3(ws.ignition_score) : "—";
    const verdictEl = $("#ws-verdict");
    if (verdictEl) {
      verdictEl.textContent = ws.ignited ? "ignited — global access" : "subliminal";
      verdictEl.classList.toggle("is-ignited", !!ws.ignited);
    }

    // mirror arousal + ignition gate from the same workspace payload
    renderArousal(ws.arousal, configValue("arousal_baseline"));
    renderIgnitionGate(ws);

    const coalitions = (barSource.competition || []).slice();
    // sort descending by share for a clean ranked readout
    coalitions.sort((a, b) => num(b.activation) - num(a.activation));

    const frag = document.createDocumentFragment();
    coalitions.forEach((c) => {
      // the dominant coalition is always marked; "winner" (full accent) only
      // when ignited, "dominant" (dimmed accent) when present-but-subliminal.
      const isDominant = c.source === ws.winner_source;
      const cls = isDominant ? (ws.ignited ? " winner" : " dominant") : "";
      const row = el("div", "coalition" + cls);
      row.style.setProperty("--src", sourceCssVar(c.source));
      const badge = isDominant
        ? `<span class="co-badge">${ws.ignited ? "access" : "dominant"}</span>` : "";
      const label = el("div", "co-label",
        `<span class="co-src">${esc(c.source)}${badge}</span>${esc(c.content || "")}`);
      label.title = `${c.source} — softmax share ${f3(c.activation)} · precision ${f2(c.precision)}`;
      const barWrap = el("div", "co-bar");
      const fill = el("div", "co-fill");
      // RAW share on the absolute 0..1 axis (shares sum to 1) — two instants
      // stay comparable; no re-normalization to the window maximum.
      fill.style.width = (clamp01(num(c.activation)) * 100).toFixed(1) + "%";
      barWrap.appendChild(fill);
      const val = el("div", "co-val", f3(c.activation));
      row.appendChild(label); row.appendChild(barWrap); row.appendChild(val);
      frag.appendChild(row);
    });
    if (!coalitions.length) {
      frag.appendChild(el("div", "empty",
        "No competition data yet — step the simulation to populate the workspace."));
    }
    box.appendChild(frag);

    // accessible equivalent: the same competition as a real table
    const tbody = document.querySelector("#coalition-table tbody");
    if (tbody) {
      tbody.replaceChildren();
      const tfrag = document.createDocumentFragment();
      coalitions.forEach((c) => {
        const tr = document.createElement("tr");
        tr.innerHTML =
          `<td>${esc(c.source)}${c.source === ws.winner_source ? (ws.ignited ? " (access)" : " (dominant)") : ""}</td>` +
          `<td>${esc(c.content || "")}</td>` +
          `<td class="num">${f3(c.activation)}</td>` +
          `<td class="num">${c.precision != null ? f2(c.precision) : "—"}</td>`;
        tfrag.appendChild(tr);
      });
      tbody.appendChild(tfrag);
    }
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
    // stay pinned to the latest moment ONLY if the user was already at the
    // right edge (don't fight a manual scroll through history)
    const stick = track.scrollLeft >= track.scrollWidth - track.clientWidth - 12;
    track.appendChild(frag);
    if (stick) track.scrollLeft = track.scrollWidth;
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
  // the six Overview KPI echoes (key, formatter) — fed by the same merged view
  const KPI_DEFS = [
    ["awareness_level", f3], ["phi_proxy", f3], ["arousal", f3],
    ["prediction_error", f3], ["free_energy", f3], ["energy", f2],
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
        `<path class="area" data-area></path><path data-line></path></svg>` +
        `<span class="mc-range micro" data-range></span>`;
      grid.appendChild(cell);
    });
  }

  function sparkPath(values) {
    // auto-scale to min/max of the window so any range (incl. negatives) reads;
    // the window bounds are returned so tiles can PRINT the scale (no silent axis)
    const n = values.length;
    if (n === 0) return { line: "", area: "", lo: null, hi: null };
    let lo = Math.min(...values), hi = Math.max(...values);
    const flat = hi - lo < 1e-9;
    if (flat) { hi += 0.5; lo -= 0.5; }
    const W = 100, H = 26, pad = 3;
    const sx = (i) => (n === 1 ? W / 2 : (i / (n - 1)) * W);
    const sy = (v) => H - pad - ((v - lo) / (hi - lo)) * (H - 2 * pad);
    let line = "";
    values.forEach((v, i) => { line += (i ? "L" : "M") + sx(i).toFixed(1) + " " + sy(v).toFixed(1) + " "; });
    const area = line + `L${W} ${H} L0 ${H} Z`;
    return { line: line.trim(), area, lo: flat ? values[0] : lo, hi: flat ? values[0] : hi };
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
      const range = cell.querySelector("[data-range]");
      if (range && sp.lo != null) {
        range.textContent = HISTORY[key].length > 1
          ? `window ${fmt(sp.lo)} – ${fmt(sp.hi)}` : "collecting…";
      }
    });

    // Overview KPI echoes (the canonical sparkline grid lives in Laboratory)
    merged.awareness_level = m.awareness_level != null
      ? m.awareness_level : cm.awareness_level;
    if (merged.awareness_level != null) pushHist("awareness_level", merged.awareness_level);
    KPI_DEFS.forEach(([key, fmt]) => {
      const tile = document.querySelector(`#overview-kpis [data-kpi="${key}"]`);
      if (!tile) return;
      const v = merged[key];
      if (v == null) return;
      tile.querySelector("[data-val]").textContent = fmt(v);
      const sp = sparkPath(HISTORY[key] || []);
      tile.querySelector("[data-line]").setAttribute("d", sp.line);
      tile.querySelector("[data-area]").setAttribute("d", sp.area);
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
        clientConfig = liveCfg;   // nominal threshold / radius for the dials
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
    if (!canvasVisible(cv)) { pendingViewDraws.add("mind"); return; }
    const W = 120, H = 120;
    const ctx = ensureCanvasScale(cv, W, H);
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

    lastDaylight = s.daylight != null ? s.daylight : 1;
    lastIsSleeping = !!s.is_sleeping;
    drawCircadianDial(lastDaylight);

    const asleep = lastIsSleeping;
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
    if (!canvasVisible(canvas)) { pendingViewDraws.add("workspace"); return; }
    const W = 720, H = 260;
    const ctx = ensureCanvasScale(canvas, W, H);
    if (!ctx) return;
    const left = 44, right = 16, top = 14, bottom = 32;
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
    // (the legend lives in the DOM next to the chart — nothing decorative in-canvas)

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

    // ignition zone — the region ABOVE the (moving) effective threshold,
    // engraved faintly so a crossing reads as entering the zone
    ctx.save();
    ctx.beginPath();
    ignitionHistory.forEach((sample, i) => {
      const x = xAt(i), y = yAt(sample.effective_threshold);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.lineTo(xAt(n - 1), yAt(1));
    ctx.lineTo(xAt(0), yAt(1));
    ctx.closePath();
    ctx.fillStyle = cssVar("--accent");
    ctx.globalAlpha = 0.07;
    ctx.fill();
    ctx.restore();

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

    // keyboard inspection cursor (←/→ on the focused chart)
    if (dynCursor >= 0 && dynCursor < n) {
      const cx = xAt(dynCursor) + 0.5;
      ctx.save();
      ctx.strokeStyle = cssVar("--ink");
      ctx.globalAlpha = 0.55;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(cx, top); ctx.lineTo(cx, top + plotH); ctx.stroke();
      ctx.restore();
    }

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
    const readout = $("#dynamics-readout");
    if (readout) {
      const s = dynCursor >= 0 && dynCursor < n ? ignitionHistory[dynCursor] : latest;
      readout.textContent = `${dynCursor >= 0 ? "inspecting" : "latest"} t${f0(s.tick)} · ` +
        `score ${f3(s.score)} / eff ${f3(s.effective_threshold)} · ` +
        (s.ignited ? "ignited" : "subliminal") +
        (dynCursor >= 0 ? "  (Esc to follow live)" : "");
    }
    canvas.setAttribute("aria-label", "Ignition score and effective-threshold history. " + summaryText);
  }

  // keyboard scrutiny of the access-dynamics samples (chart is focusable)
  $("#ignition-chart")?.addEventListener("keydown", (ev) => {
    const n = ignitionHistory.length;
    if (!n) return;
    if (ev.key === "ArrowLeft") dynCursor = dynCursor < 0 ? n - 2 : Math.max(0, dynCursor - 1);
    else if (ev.key === "ArrowRight") dynCursor = dynCursor < 0 ? n - 1 : Math.min(n - 1, dynCursor + 1);
    else if (ev.key === "Home") dynCursor = 0;
    else if (ev.key === "End") dynCursor = n - 1;
    else if (ev.key === "Escape") dynCursor = -1;
    else return;
    ev.preventDefault();
    renderIgnitionDynamics(null, lastTick);
  });

  // one renderer, two windows: the canonical timeline in #/workspace and its
  // compact echo on #/overview — plus a DOM source legend (color never alone).
  function renderStreamHost(host, data, compact) {
    if (!host) return { sources: new Set(), ignitedCount: 0 };
    host.innerHTML = "";
    const fragment = document.createDocumentFragment();
    const sources = new Set();
    let ignitedCount = 0;
    data.forEach((moment) => {
      const source = String(moment && moment.dominant_source || "unknown").toLowerCase();
      const awareness = clamp01(num(moment && moment.awareness_level));
      const ignited = !!(moment && moment.ignited);
      const tickLabel = "t" + f0(moment && moment.tick);
      const content = String(moment && moment.contents || "no content label");
      const description = `${tickLabel} · ${source} · awareness ${f3(awareness)} · ` +
        `${ignited ? "ignited" : "subliminal"} · ${content}`;
      const bar = el("span", "moment" + (ignited ? " ignited" : ""));
      bar.style.height = Math.max(4, awareness * (compact ? 36 : 50)).toFixed(1) + "px";
      bar.style.background = sourceCssVar(source);   // themed CSS variable
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
    return { sources, ignitedCount };
  }

  function renderSourceLegend(sources) {
    const host = $("#source-legend");
    if (!host) return;
    host.replaceChildren();
    const frag = document.createDocumentFragment();
    [...sources].sort().forEach((source) => {
      const item = el("span", "lg");
      const dot = el("i", "dot");
      dot.style.background = sourceCssVar(source);
      item.appendChild(dot);
      item.appendChild(document.createTextNode(source));
      frag.appendChild(item);
    });
    host.appendChild(frag);
  }

  function renderHorizonStream(moments) {
    const data = (Array.isArray(moments) ? moments : streamData).slice(-STREAM_MAX);
    const main = renderStreamHost($("#horizon-stream"), data, false);
    renderStreamHost($("#overview-stream"), data, true);
    renderSourceLegend(main.sources);
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

  const MEMG_W = 720, MEMG_H = 440; // logical drawing space of the memory graph

  function drawMemoryGraph(graph) {
    const canvas = $("#memory-graph");
    const summary = $("#memory-graph-summary");
    if (!canvas || !canvas.getContext) return;
    if (!canvasVisible(canvas)) { pendingViewDraws.add("memory"); return; }
    const ctx = ensureCanvasScale(canvas, MEMG_W, MEMG_H);
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
    const W = MEMG_W, H = MEMG_H;
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
  //  SITUATED GENDERED SELF (Phase 8)
  // ============================================================
  // Three boundaries are deliberately kept separate:
  //   1. complete private scenario input (explicit debug reveal only),
  //   2. the simulated agent's readable self-understanding,
  //   3. public projection and observer-local recognition.
  // The browser never infers identity from affect, body, expression or society.
  const genderHuman = (value) => String(value == null ? "" : value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const genderSigned = (value) => {
    const n = num(value);
    return (n >= 0 ? "+" : "") + n.toFixed(3);
  };
  const genderAxisText = (axes) => {
    const a = axes || {};
    return `f ${f2(a.feminine)} · m ${f2(a.masculine)} · a ${f2(a.androgynous)}`;
  };

  function setGenderStatus(text, kind) {
    const node = $("#gender-scenario-status");
    if (!node) return;
    node.textContent = text || "";
    node.classList.toggle("is-error", kind === "error");
    node.classList.toggle("is-ok", kind === "ok");
  }

  function genderLabelsMarkup(values, emptyText, extraClass) {
    const labels = Array.isArray(values) ? values : [];
    if (!labels.length) {
      return `<span class="gender-label ${extraClass || ""}">${esc(emptyText || "none disclosed")}</span>`;
    }
    return labels.map((label) =>
      `<span class="gender-label ${extraClass || ""}">${esc(label)}</span>`
    ).join("");
  }

  function renderGenderMetricGroup(selector, items) {
    const host = $(selector);
    if (!host) return;
    host.replaceChildren();
    (items || []).forEach((item) => {
      const value = clamp01(num(item.value));
      const metric = el("div", "gender-metric");
      metric.dataset.tone = item.tone || "neutral";
      const head = el("div", "gender-metric-head");
      head.appendChild(el("span", "", esc(item.label)));
      const output = document.createElement("output");
      output.textContent = f3(value);
      head.appendChild(output);
      const meter = el("div", "meter");
      meter.setAttribute("role", "meter");
      meter.setAttribute("aria-label", item.label);
      meter.setAttribute("aria-valuemin", "0");
      meter.setAttribute("aria-valuemax", "1");
      meter.setAttribute("aria-valuenow", value.toFixed(3));
      const fill = el("div", "meter-fill");
      fill.style.width = pctTxt(value);
      meter.appendChild(fill);
      metric.append(head, meter);
      host.appendChild(metric);
    });
  }

  function renderGenderTimeline(plan, state) {
    const track = $("#gender-life-track");
    const list = $("#gender-life-list");
    if (!track || !list) return;
    track.replaceChildren();
    list.replaceChildren();

    let stages = plan && Array.isArray(plan.stages) ? plan.stages : [];
    if (!stages.length && state && state.life_stage) {
      stages = [{ stage: state.life_stage, duration_ticks: null }];
    }
    stages.forEach((stage) => {
      const current = !!(state && stage.stage === state.life_stage);
      const visual = el("span", "gender-track-stage" + (current ? " is-current" : ""));
      const duration = stage.duration_ticks == null ? 12 : num(stage.duration_ticks);
      visual.style.setProperty("--stage-weight", String(clamp(duration / 12, 1, 8)));
      track.appendChild(visual);

      const item = el("li", current ? "is-current" : "");
      const text = el("div");
      const title = document.createElement("strong");
      title.textContent = genderHuman(stage.stage);
      const meta = document.createElement("span");
      const durationText = stage.duration_ticks == null
        ? "current stage"
        : `${Math.round(num(stage.duration_ticks))} configured ticks`;
      const currentText = current && state
        ? ` · tick ${Math.round(num(state.tick_in_stage))} in stage`
        : "";
      meta.textContent = durationText + currentText;
      text.append(title, meta);
      item.appendChild(text);
      list.appendChild(item);
    });

    const note = $("#gender-course-note");
    if (note) {
      const historyCount = plan && Array.isArray(plan.initial_history_summary)
        ? plan.initial_history_summary.length : 0;
      note.textContent = plan
        ? `${stages.length} configured stage${stages.length === 1 ? "" : "s"} · ${historyCount} prior-history note${historyCount === 1 ? "" : "s"}`
        : "Current stage shown; reveal experiment input for the full plan.";
    }
  }

  function renderGenderSelf(state) {
    const host = $("#gender-self-content");
    if (!host) return;
    const self = (state && state.self_understanding) || {};
    const labels = Array.isArray(self.labels) ? self.labels : [];
    const scopes = self.disclosure_scopes || {};
    const currentIntent = state && state.current_intent;
    host.innerHTML =
      `<div class="gender-labels">${genderLabelsMarkup(
        labels,
        self.questioning ? "questioning / unlabeled" : "no active label",
        self.questioning ? "is-questioning" : ""
      )}</div>` +
      `<dl class="gender-layer-kv">` +
        `<dt>certainty</dt><dd class="mono">${f3(self.certainty)}</dd>` +
        `<dt>questioning</dt><dd>${self.questioning ? "yes" : "no"}</dd>` +
        `<dt>last revision</dt><dd class="mono">t${Math.round(num(self.last_revision_tick))}</dd>` +
        `<dt>private scope</dt><dd>${esc((scopes.private || []).join(", ") || "none")}</dd>` +
        `<dt>trusted scope</dt><dd>${esc((scopes.trusted || []).join(", ") || "none")}</dd>` +
        `<dt>public scope</dt><dd>${esc((scopes.public || []).join(", ") || "none")}</dd>` +
        `<dt>current intent</dt><dd>${currentIntent
          ? `${esc(genderHuman(currentIntent.type))} · <span class="mono">${esc(currentIntent.provenance)}</span>`
          : "none"}</dd>` +
      `</dl>`;

    const fits = Object.entries(self.fit_by_label || {});
    if (fits.length) {
      const heading = el("span", "eyebrow", "Fit evidence ledger");
      const fitList = el("div", "gender-fit-list");
      fits.sort((a, b) => num(b[1]) - num(a[1])).forEach(([label, raw]) => {
        const value = clamp01(num(raw));
        const row = el("div", "gender-fit-row");
        row.appendChild(el("span", "", esc(label)));
        const meter = el("div", "meter");
        meter.setAttribute("role", "meter");
        meter.setAttribute("aria-label", `Fit evidence for ${label}`);
        meter.setAttribute("aria-valuemin", "0");
        meter.setAttribute("aria-valuemax", "1");
        meter.setAttribute("aria-valuenow", value.toFixed(3));
        const fill = el("div", "meter-fill");
        fill.style.width = pctTxt(value);
        meter.appendChild(fill);
        row.appendChild(meter);
        row.appendChild(el("span", "mono", f2(value)));
        fitList.appendChild(row);
      });
      host.append(heading, fitList);
    }
    if (state && state.report) {
      host.appendChild(el("p", "report-voice", esc(state.report)));
    }
  }

  function renderGenderPublic(society, state) {
    const host = $("#gender-public-content");
    if (!host) return;
    const projections = (society && society.projections) || {};
    const projection = projections["0"] || projections[0] || null;
    if (!projection) {
      host.innerHTML = '<div class="empty">No public projection is available.</div>';
      return;
    }
    const recognitions = ((society && society.recognition) || [])
      .filter((item) => num(item.target_id) === num(state && state.agent_id));
    host.innerHTML =
      `<div class="gender-labels">${genderLabelsMarkup(projection.labels, "no label disclosed")}</div>` +
      `<dl class="gender-layer-kv">` +
        `<dt>name</dt><dd>${esc(projection.name || "not disclosed")}</dd>` +
        `<dt>pronouns</dt><dd>${esc((projection.pronouns || []).join(", ") || "not disclosed")}</dd>` +
        `<dt>scope</dt><dd>${esc(projection.disclosure_scope || "public")}</dd>` +
        `<dt>observer records</dt><dd class="mono">${recognitions.length}</dd>` +
        `<dt>updated</dt><dd class="mono">t${Math.round(num(projection.updated_tick))}</dd>` +
      `</dl>`;
    const expression = Object.entries(projection.expression || {});
    if (expression.length) {
      const wrap = el("div", "gender-fit-list");
      expression.forEach(([channel, axes]) => {
        const row = el("div", "gender-fit-row");
        row.appendChild(el("span", "", esc(genderHuman(channel))));
        row.appendChild(el("span", "mono", esc(genderAxisText(axes))));
        row.appendChild(el("span", "mono", "public"));
        wrap.appendChild(row);
      });
      host.appendChild(wrap);
    }
  }

  function renderGenderPrivate(debug) {
    const host = $("#gender-private-content");
    if (!host || !debug) return;
    const profile = debug.profile || {};
    const initial = profile.initial_self_understanding || {};
    const affinities = Object.entries(profile.felt_affinities || {})
      .sort((a, b) => num(b[1]) - num(a[1]));
    const priorities = Object.entries(profile.transition_priorities || {});
    const history = (debug.life_course && debug.life_course.initial_history_summary) || [];
    host.innerHTML =
      `<dl class="gender-layer-kv">` +
        `<dt>profile input</dt><dd class="mono">${esc(profile.profile_id || "—")}</dd>` +
        `<dt>assigned category</dt><dd>${esc(profile.assigned_category || "unspecified")}</dd>` +
        `<dt>felt affinities</dt><dd>${esc(affinities.map(([k, v]) => `${k} ${f2(v)}`).join(" · ") || "none")}</dd>` +
        `<dt>fluidity</dt><dd class="mono">${f3(profile.fluidity)}</dd>` +
        `<dt>gender salience</dt><dd class="mono">${f3(profile.gender_salience)}</dd>` +
        `<dt>initial labels</dt><dd>${esc((initial.labels || []).join(", ") || "unlabeled")}</dd>` +
        `<dt>expression inputs</dt><dd>${esc(Object.keys(profile.preferred_expression || {}).map(genderHuman).join(", ") || "none")}</dd>` +
        `<dt>body inputs</dt><dd>${esc(Object.keys(profile.body_preferences || {}).map(genderHuman).join(", ") || "none")}</dd>` +
        `<dt>transition priorities</dt><dd>${esc(priorities.map(([k, v]) => `${genderHuman(k)} ${f2(v)}`).join(" · ") || "none")}</dd>` +
        `<dt>prior history</dt><dd>${esc(history.join(" ") || "none configured")}</dd>` +
        `<dt>pending events</dt><dd class="mono">${(debug.pending_events || []).length}</dd>` +
        `<dt>event ledger</dt><dd class="mono">${Math.round(num(debug.event_ledger_size))}</dd>` +
        `<dt>profile checksum</dt><dd class="mono">${esc(String(debug.profile_checksum || "").slice(0, 14))}…</dd>` +
      `</dl>` +
      `<p class="micro">${esc(debug.framing || "Experiment inputs are unavailable to simulated observers.")}</p>`;
    host.hidden = false;
    renderGenderTimeline(debug.life_course, debug.state);
  }

  function renderGenderExpression(state) {
    const host = $("#gender-expression");
    if (!host) return;
    host.replaceChildren();
    Object.entries((state && state.expression) || {}).forEach(([channel, item]) => {
      const card = el("article", "gender-data-card");
      card.innerHTML =
        `<header><h5>${esc(genderHuman(channel))}</h5><output>accent ${f3(item.accentuation)}</output></header>` +
        `<div class="gender-data-points">` +
          `<span>visibility<b>${f2(item.visibility)}</b></span>` +
          `<span>safety cost<b>${f2(item.safety_cost)}</b></span>` +
          `<span>accentuation<b>${f2(item.accentuation)}</b></span>` +
        `</div>` +
        `<p class="micro">desired ${esc(genderAxisText(item.desired))}<br>public ${esc(genderAxisText(item.public))}</p>` +
        `<div class="gender-driver-list">${(item.drivers || []).length
          ? item.drivers.map((driver) => `<span class="gender-driver">${esc(genderHuman(driver))}</span>`).join("")
          : '<span class="gender-driver">no accentuation driver</span>'}</div>`;
      host.appendChild(card);
    });
    if (!host.childElementCount) host.innerHTML = '<div class="empty">No expression channels configured.</div>';
  }

  function renderGenderBody(state) {
    const host = $("#gender-body");
    if (!host) return;
    host.replaceChildren();
    Object.entries((state && state.body) || {}).forEach(([domain, item]) => {
      const change = num(item.change_rate);
      const card = el("article", "gender-data-card");
      card.innerHTML =
        `<header><h5>${esc(genderHuman(domain))}</h5><output>align ${f3(item.alignment)}</output></header>` +
        `<div class="gender-data-points">` +
          `<span>alignment<b>${f2(item.alignment)}</b></span>` +
          `<span>salience<b>${f2(item.salience)}</b></span>` +
          `<span>public vis.<b>${f2(item.public_visibility)}</b></span>` +
        `</div>` +
        `<p class="micro">current ${esc(genderAxisText(item.current))}<br>preferred ${esc(genderAxisText(item.preferred))}</p>` +
        `<span class="gender-transition-meta">abstract change rate ${change >= 0 ? "+" : ""}${change.toFixed(3)}</span>`;
      host.appendChild(card);
    });
    if (!host.childElementCount) host.innerHTML = '<div class="empty">No body domains configured.</div>';
  }

  function genderTransitionBar(label, value, kind) {
    const v = clamp01(num(value));
    return `<div class="gender-transition-bar" data-kind="${esc(kind)}">` +
      `<span>${esc(label)}</span>` +
      `<div class="meter" role="meter" aria-label="${esc(label)}" aria-valuemin="0" aria-valuemax="1" aria-valuenow="${v.toFixed(3)}">` +
        `<div class="meter-fill" style="width:${pctTxt(v)}"></div>` +
      `</div><span class="mono">${f2(v)}</span></div>`;
  }

  function renderGenderTransitions(state) {
    const host = $("#gender-transitions");
    if (!host) return;
    host.replaceChildren();
    Object.entries((state && state.transitions) || {}).forEach(([dimension, item]) => {
      const card = el("article", "gender-transition");
      card.innerHTML =
        `<header><h5>${esc(genderHuman(dimension))}</h5><span class="gender-transition-status">${esc(genderHuman(item.status))}</span></header>` +
        `<div class="gender-transition-bars">` +
          genderTransitionBar("desire", item.desire, "desire") +
          genderTransitionBar("access", item.access, "access") +
          genderTransitionBar("progress", item.progress, "progress") +
        `</div>` +
        `<div class="gender-transition-meta">satisfaction ${num(item.satisfaction).toFixed(3)} · ${esc(genderHuman(item.reversibility))}</div>` +
        `<div class="gender-transition-meta">${esc(item.last_reason || "no status change yet")} · t${Math.round(num(item.last_change_tick))}</div>`;
      host.appendChild(card);
    });
    if (!host.childElementCount) host.innerHTML = '<div class="empty">No transition dimensions configured.</div>';
  }

  function renderGenderProbeLog(state) {
    const host = $("#gender-probe-log");
    if (!host) return;
    host.replaceChildren();
    const rows = genderProbeHistory.slice(0, 6);
    const currentIntent = state && state.current_intent;
    if (currentIntent && !rows.some((row) => row.id === `intent-${currentIntent.intent_id}`)) {
      rows.unshift({
        id: `intent-${currentIntent.intent_id}`,
        label: `intent · ${genderHuman(currentIntent.type)}`,
        tick: currentIntent.tick,
        provenance: currentIntent.provenance,
      });
    }
    const knownIds = new Set(rows.map((row) => String(row.eventId || "")));
    ((state && state.recent_event_ids) || []).slice().reverse().forEach((eventId) => {
      if (!knownIds.has(String(eventId)) && rows.length < 6) {
        rows.push({
          id: `event-${eventId}`,
          label: `processed event #${eventId}`,
          tick: state.tick,
          provenance: "ledger",
        });
      }
    });
    rows.forEach((row) => {
      const item = el("div", "gender-probe-entry");
      item.appendChild(el("span", "", esc(row.label)));
      item.appendChild(el("span", "", `t${Math.round(num(row.tick))} · ${esc(row.provenance || "unknown")}`));
      host.appendChild(item);
    });
    if (!host.childElementCount) {
      host.innerHTML = '<div class="empty">No recent event or intention provenance.</div>';
    }
  }

  function renderGenderExperience(payload, society) {
    if (payload !== undefined) genderPayload = payload;
    if (society !== undefined) genderSocietyPayload = society;
    const live = genderPayload;
    const state = live && live.state;
    const active = !!(live && live.enabled && live.configured && state);
    const badge = $("#gender-phase-badge");
    if (badge) {
      badge.dataset.state = active ? "active" : "dormant";
      badge.innerHTML = `<span aria-hidden="true"></span> ${active ? "active" : "dormant"}`;
    }
    const gate = document.querySelector('[data-flag="gender_experience_enabled"]');
    if (gate) gate.checked = !!(live && live.enabled);
    const disclaimer = $("#gender-disclaimer");
    if (disclaimer && live && live.disclaimer) disclaimer.textContent = live.disclaimer;
    const empty = $("#gender-empty");
    const observatory = $("#gender-observatory");
    if (empty) empty.hidden = active;
    if (observatory) observatory.hidden = !active;
    if (!active) {
      const privateContent = $("#gender-private-content");
      if (privateContent) privateContent.hidden = true;
      const debugButton = $("#btn-gender-debug");
      if (debugButton) {
        debugButton.setAttribute("aria-expanded", "false");
        debugButton.textContent = "Reveal private input";
      }
      return;
    }

    // On a fresh browser load, align the blueprint chooser with the active
    // profile once. Subsequent user selection is left untouched so they can
    // prepare a different scenario without the poll loop fighting the form.
    if (genderSyncedProfileId !== state.profile_id) {
      const matchingPreset = genderCatalog.find((item) => {
        const agent = item.manifest && item.manifest.agents &&
          (item.manifest.agents["0"] || item.manifest.agents[0]);
        return agent && agent.profile && agent.profile.profile_id === state.profile_id;
      });
      if (matchingPreset && $("#gender-scenario-select")) {
        $("#gender-scenario-select").value = matchingPreset.preset_id;
        genderActivePresetId = matchingPreset.preset_id;
        renderGenderScenarioEditor();
      }
      genderSyncedProfileId = state.profile_id;
    }

    $("#gender-life-position").textContent =
      `${genderHuman(state.life_stage)} · ${Math.round(num(state.tick_in_stage))} ticks in stage`;
    $("#gender-profile-id").textContent = state.profile_id || "—";
    $("#gender-state-tick").textContent = "t" + Math.round(num(state.tick));
    renderGenderTimeline(genderDebugPayload && genderDebugPayload.life_course, state);
    renderGenderSelf(state);
    renderGenderPublic(genderSocietyPayload, state);

    const congruence = state.congruence || {};
    renderGenderMetricGroup("#gender-congruence", [
      { label: "body", value: congruence.body, tone: "private" },
      { label: "expression", value: congruence.expression, tone: "constructive" },
      { label: "social", value: congruence.social, tone: "public" },
      { label: "administrative", value: congruence.administrative, tone: "public" },
      { label: "total", value: congruence.total, tone: "constructive" },
    ]);
    const affect = state.affect || {};
    renderGenderMetricGroup("#gender-affect", [
      { label: "dysphoria", value: affect.dysphoria, tone: "stress" },
      { label: "euphoria", value: affect.euphoria, tone: "constructive" },
      { label: "fulfillment", value: affect.fulfillment, tone: "constructive" },
    ]);
    const stress = state.minority_stress || {};
    renderGenderMetricGroup("#gender-stress", [
      { label: "external now", value: stress.external_current, tone: "stress" },
      { label: "external chronic", value: stress.external_chronic, tone: "stress" },
      { label: "rejection expectation", value: stress.rejection_expectation, tone: "stress" },
      { label: "concealment pressure", value: stress.concealment_pressure, tone: "stress" },
      { label: "vigilance", value: stress.vigilance, tone: "stress" },
      { label: "internalized transphobia", value: stress.internalized_transphobia, tone: "private" },
      { label: "cumulative exposure", value: stress.cumulative_exposure, tone: "stress" },
    ]);
    const resilience = state.resilience || {};
    renderGenderMetricGroup("#gender-resilience", [
      { label: "support", value: resilience.support, tone: "constructive" },
      { label: "community", value: resilience.community, tone: "constructive" },
      { label: "positive representation", value: resilience.positive_representation, tone: "constructive" },
      { label: "pride", value: resilience.pride, tone: "constructive" },
      { label: "self-acceptance", value: resilience.self_acceptance, tone: "constructive" },
      { label: "combined index", value: resilience.index, tone: "constructive" },
    ]);
    renderGenderExpression(state);
    renderGenderBody(state);
    renderGenderTransitions(state);
    renderGenderProbeLog(state);
  }

  function renderGenderScenarioEditor() {
    const select = $("#gender-scenario-select");
    const item = genderCatalog.find((candidate) => candidate.preset_id === (select && select.value));
    if (!item) {
      genderManifestDraft = null;
      const apply = $("#btn-gender-apply");
      if (apply) apply.disabled = true;
      return;
    }
    genderManifestDraft = JSON.parse(JSON.stringify(item.manifest));
    genderActivePresetId = genderActivePresetId || item.preset_id;
    const title = $("#gender-scenario-title");
    if (title) title.textContent = genderHuman(item.preset_id);
    const description = $("#gender-scenario-description");
    if (description) description.textContent = item.description;
    renderGenderLifeEditor(genderManifestDraft);
    const confirm = $("#gender-reset-confirm");
    const apply = $("#btn-gender-apply");
    if (confirm) confirm.checked = false;
    if (apply) apply.disabled = true;
    setGenderStatus("Blueprint loaded. Inspect or configure it before applying.", "");
  }

  function renderGenderLifeEditor(manifest) {
    const stagesHost = $("#gender-life-stages");
    const contextHost = $("#gender-context-fields");
    if (!stagesHost || !contextHost || !manifest) return;
    stagesHost.replaceChildren();
    contextHost.replaceChildren();
    const agentInput = manifest.agents && (manifest.agents["0"] || manifest.agents[0]);
    const stages = (agentInput && agentInput.life_course && agentInput.life_course.stages) || [];
    stages.forEach((stage, index) => {
      const card = el("section", "gender-stage-editor");
      card.dataset.stageIndex = String(index);
      card.innerHTML =
        `<label><input type="checkbox" data-stage-enabled checked><span>${esc(genderHuman(stage.stage))}</span></label>` +
        `<label><span>duration ticks</span><input type="number" data-stage-field="duration_ticks" min="1" max="1000000" value="${Math.round(num(stage.duration_ticks))}"></label>` +
        `<label><span>body change <output>${f2(stage.body_change_rate)}</output></span><input type="range" data-stage-field="body_change_rate" min="0" max="1" step="0.01" value="${num(stage.body_change_rate)}"></label>` +
        `<label><span>autonomy <output>${f2(stage.autonomy)}</output></span><input type="range" data-stage-field="autonomy" min="0" max="1" step="0.01" value="${num(stage.autonomy)}"></label>` +
        `<label><span>resource access <output>${f2(stage.resource_access)}</output></span><input type="range" data-stage-field="resource_access" min="0" max="1" step="0.01" value="${num(stage.resource_access)}"></label>` +
        `<label><span>norm exposure <output>${f2(stage.norm_exposure)}</output></span><input type="range" data-stage-field="norm_exposure" min="0" max="1" step="0.01" value="${num(stage.norm_exposure)}"></label>`;
      const enabled = card.querySelector("[data-stage-enabled]");
      enabled.addEventListener("change", () => card.classList.toggle("is-omitted", !enabled.checked));
      card.querySelectorAll('input[type="range"]').forEach((input) => {
        input.addEventListener("input", () => {
          const output = input.closest("label").querySelector("output");
          if (output) output.textContent = f2(input.valueAsNumber);
        });
      });
      stagesHost.appendChild(card);
    });

    const context = manifest.social_context || {};
    const contextFields = [
      ["norm_rigidity", "norm rigidity"],
      ["institutional_hostility", "institutional hostility"],
      ["baseline_safety", "baseline safety"],
      ["care_access", "abstract care access"],
      ["community_visibility", "community visibility"],
      ["positive_representation", "positive representation"],
    ];
    contextFields.forEach(([key, label]) => {
      const value = clamp01(num(context[key]));
      const field = el("label", "gender-context-field");
      field.innerHTML =
        `<span>${esc(label)} <output>${f2(value)}</output></span>` +
        `<input type="range" data-context-field="${esc(key)}" min="0" max="1" step="0.01" value="${value}">`;
      const input = field.querySelector("input");
      input.addEventListener("input", () => {
        field.querySelector("output").textContent = f2(input.valueAsNumber);
      });
      contextHost.appendChild(field);
    });
    const hostility = el("label", "gender-context-hostility");
    hostility.innerHTML =
      `<input type="checkbox" data-context-hostility ${context.hostility_enabled ? "checked" : ""}>` +
      `<span>allow configured hostile social events</span>`;
    contextHost.appendChild(hostility);
  }

  function buildGenderManifestFromEditor() {
    if (!genderManifestDraft) throw new Error("Choose a scenario blueprint first.");
    const manifest = JSON.parse(JSON.stringify(genderManifestDraft));
    const agentInput = manifest.agents && (manifest.agents["0"] || manifest.agents[0]);
    if (!agentInput || !agentInput.life_course) throw new Error("Scenario has no agent 0 life course.");
    const original = agentInput.life_course.stages || [];
    const selectedStages = [];
    document.querySelectorAll("#gender-life-stages .gender-stage-editor").forEach((card) => {
      if (!card.querySelector("[data-stage-enabled]").checked) return;
      const index = Math.max(0, Math.trunc(Number(card.dataset.stageIndex) || 0));
      const stage = JSON.parse(JSON.stringify(original[index]));
      card.querySelectorAll("[data-stage-field]").forEach((input) => {
        const key = input.dataset.stageField;
        stage[key] = key === "duration_ticks"
          ? Math.max(1, Math.min(1000000, Math.round(input.valueAsNumber || 1)))
          : clamp01(input.valueAsNumber);
      });
      selectedStages.push(stage);
    });
    if (!selectedStages.length) throw new Error("Keep at least one life stage.");
    agentInput.life_course.stages = selectedStages;
    document.querySelectorAll("#gender-context-fields [data-context-field]").forEach((input) => {
      manifest.social_context[input.dataset.contextField] = clamp01(input.valueAsNumber);
    });
    const hostility = document.querySelector("#gender-context-fields [data-context-hostility]");
    if (hostility) manifest.social_context.hostility_enabled = !!hostility.checked;
    const seedInput = $("#gender-scenario-seed");
    const seed = Math.max(0, Math.min(4294967295, Math.trunc(Number(seedInput && seedInput.value) || 0)));
    if (seedInput) seedInput.value = String(seed);
    manifest.seed = seed;
    const root = manifest.preset_id || "custom";
    manifest.scenario_id = `${root}-${seed}-configured`.slice(0, 96);
    return manifest;
  }

  async function loadGenderScenarios() {
    const select = $("#gender-scenario-select");
    const seedInput = $("#gender-scenario-seed");
    if (!select || !seedInput) return;
    const previous = select.value || "nonbinary";
    const seed = Math.max(0, Math.min(4294967295, Math.trunc(Number(seedInput.value) || 42)));
    seedInput.value = String(seed);
    select.disabled = true;
    setGenderStatus("Loading inspectable manifests…", "");
    try {
      const result = await api(`gender/scenarios?seed=${encodeURIComponent(seed)}`);
      genderCatalog = Array.isArray(result && result.scenarios) ? result.scenarios : [];
      select.replaceChildren();
      genderCatalog.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.preset_id;
        option.textContent = genderHuman(item.preset_id);
        select.appendChild(option);
      });
      const wanted = genderCatalog.some((item) => item.preset_id === previous)
        ? previous
        : (genderCatalog.some((item) => item.preset_id === "nonbinary") ? "nonbinary" : (genderCatalog[0] && genderCatalog[0].preset_id));
      if (wanted) select.value = wanted;
      renderGenderScenarioEditor();
    } catch (error) {
      genderCatalog = [];
      genderManifestDraft = null;
      select.innerHTML = '<option value="">Scenario API unavailable</option>';
      setGenderStatus("Could not load gender-life scenarios.", "error");
    } finally {
      select.disabled = false;
    }
  }

  async function applyGenderScenario(event) {
    event.preventDefault();
    const confirm = $("#gender-reset-confirm");
    const button = $("#btn-gender-apply");
    if (!confirm || !confirm.checked) {
      setGenderStatus("Confirm the full reset before applying.", "error");
      return;
    }
    let manifest;
    try {
      manifest = buildGenderManifestFromEditor();
    } catch (error) {
      setGenderStatus(error.message, "error");
      return;
    }
    button.disabled = true;
    button.textContent = "Resetting…";
    setGenderStatus("Installing the complete manifest transactionally…", "");
    try {
      const response = await postJSON("gender/scenario", { scenario: manifest });
      resetHorizonClientState();
      genderActivePresetId = manifest.preset_id || $("#gender-scenario-select").value;
      genderPayload = response.agents && (response.agents["0"] || response.agents[0]);
      genderSocietyPayload = response.public_society || null;
      genderDebugPayload = null;
      renderGenderExperience(genderPayload, genderSocietyPayload);
      applyControlStates({ gender_experience_enabled: true });
      clientConfig.gender_experience_enabled = true;
      buildConfigFull();
      confirm.checked = false;
      setGenderStatus(
        `${genderHuman(manifest.preset_id || "custom scenario")} installed · full reset · initialized t${Math.round(num(response.initialized_tick))}.`,
        "ok"
      );
      toast("Gender-life scenario applied through a full reset.", "ok");
      await refreshAll();
    } catch (error) {
      const detail = error && error.detail && error.detail.detail;
      const validationMessage = Array.isArray(detail) && detail[0] && detail[0].msg;
      setGenderStatus(
        typeof detail === "string"
          ? detail
          : (validationMessage || "Scenario rejected; the live run was not partially changed."),
        "error"
      );
      setStatus("error", "Gender scenario error");
    } finally {
      button.textContent = "Apply & reset";
      button.disabled = true;
    }
  }

  function hideGenderDebug() {
    genderDebugPayload = null;
    const content = $("#gender-private-content");
    const button = $("#btn-gender-debug");
    if (content) {
      content.replaceChildren();
      content.hidden = true;
    }
    if (button) {
      button.setAttribute("aria-expanded", "false");
      button.textContent = "Reveal private input";
    }
    const state = genderPayload && genderPayload.state;
    if (state) renderGenderTimeline(null, state);
  }

  async function revealGenderDebug(options) {
    const quiet = options && options.quiet;
    const button = $("#btn-gender-debug");
    if (button) {
      button.disabled = true;
      button.textContent = "Loading private input…";
    }
    try {
      const debug = await api("agent/gender/debug");
      genderDebugPayload = debug;
      renderGenderPrivate(debug);
      if (button) {
        button.setAttribute("aria-expanded", "true");
        button.textContent = "Hide private input";
      }
      if (!quiet) toast("Private experiment input revealed locally.", "ok");
    } catch (error) {
      if (!quiet) toast("Private input is unavailable until a scenario is configured.", "error");
      hideGenderDebug();
    } finally {
      if (button) button.disabled = false;
    }
  }

  async function toggleGenderDebug() {
    const content = $("#gender-private-content");
    if (content && !content.hidden) hideGenderDebug();
    else await revealGenderDebug();
  }

  async function queueGenderEvent(event) {
    event.preventDefault();
    if (!(genderPayload && genderPayload.configured)) {
      toast("Choose a gender-life scenario first.", "error");
      return;
    }
    const type = $("#gender-event-type").value;
    const domain = $("#gender-event-domain").value;
    const intensity = clamp01($("#gender-event-intensity").valueAsNumber);
    const hostile = GENDER_HOSTILE_EVENTS.has(type);
    try {
      const response = await postJSON("agent/gender/event", {
        type,
        domain,
        intensity,
        visibility: hostile ? "public" : "trusted",
        deliberate: hostile,
        context_code: `ui_${type}`.slice(0, 64),
      });
      genderProbeHistory.unshift({
        id: `event-${response.event.event_id}`,
        eventId: response.event.event_id,
        label: `event · ${genderHuman(type)} · ${genderHuman(domain)}`,
        tick: response.scheduled_tick,
        provenance: response.event.provenance,
      });
      renderGenderProbeLog(genderPayload.state);
      toast(`Event queued for t${response.scheduled_tick}.`, "ok");
      if (genderDebugPayload) await revealGenderDebug({ quiet: true });
    } catch (error) {
      toast("Event rejected without changing the queue.", "error");
    }
  }

  async function queueGenderIntent(event) {
    event.preventDefault();
    if (!(genderPayload && genderPayload.configured)) {
      toast("Choose a gender-life scenario first.", "error");
      return;
    }
    const type = $("#gender-intent-type").value;
    const dimension = $("#gender-intent-dimension").value;
    const body = {
      type,
      domain: dimension || "general",
      urgency: clamp01($("#gender-intent-urgency").valueAsNumber),
    };
    if (dimension) body.transition_dimension = dimension;
    if (type === "disclose") body.disclosure_scope = "public";
    if (type === "conceal") body.disclosure_scope = "private";
    try {
      const response = await postJSON("agent/gender/intent", body);
      genderProbeHistory.unshift({
        id: `intent-${response.intent.intent_id}`,
        label: `intent · ${genderHuman(type)}${dimension ? ` · ${genderHuman(dimension)}` : ""}`,
        tick: response.scheduled_tick,
        provenance: response.intent.provenance,
      });
      renderGenderProbeLog(genderPayload.state);
      toast(`Intention queued for t${response.scheduled_tick}.`, "ok");
      if (genderDebugPayload) await revealGenderDebug({ quiet: true });
    } catch (error) {
      toast("Intention rejected without changing the queue.", "error");
    }
  }

  function renderGenderBattery(result) {
    const host = $("#gender-battery-result");
    if (!host) return;
    host.replaceChildren();
    Object.entries((result && result.comparisons) || {}).forEach(([name, values]) => {
      const row = el("div", "gender-comparison");
      const same = values && values.same_private_profile;
      row.appendChild(el(
        "strong",
        "",
        `${esc(genderHuman(name))}${same === true ? ' <span class="gender-driver">same private profile</span>' : ""}`
      ));
      Object.entries(values || {})
        .filter(([key, value]) => key !== "same_private_profile" && typeof value === "number")
        .forEach(([key, value]) => {
          row.appendChild(el("span", "", `${esc(genderHuman(key))} ${genderSigned(value)}`));
        });
      host.appendChild(row);
    });
    host.appendChild(el("p", "gender-battery-note", esc(
      (result && result.interpretation) || "Counterfactual interpretation unavailable."
    )));
  }

  async function runGenderBattery(event) {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button[type='submit']");
    const ticks = Math.max(4, Math.min(500, Math.round($("#gender-battery-ticks").valueAsNumber || 24)));
    const seed = Math.max(0, Math.min(4294967295, Math.trunc(Number($("#gender-scenario-seed").value) || 42)));
    const presetId = genderActivePresetId || $("#gender-scenario-select").value || "nonbinary";
    button.disabled = true;
    button.textContent = "Running 8 arms…";
    $("#gender-battery-result").innerHTML = '<div class="empty">Computing deterministic matched arms…</div>';
    try {
      const result = await postJSON("battery/gender-experience", {
        preset_id: presetId,
        seed,
        ticks,
      });
      renderGenderBattery(result);
    } catch (error) {
      $("#gender-battery-result").innerHTML = '<div class="empty">Battery request failed.</div>';
    } finally {
      button.disabled = false;
      button.textContent = "Run 8 matched arms";
    }
  }

  function bindGenderControls() {
    if (genderControlsBound) return;
    genderControlsBound = true;
    $("#gender-scenario-select")?.addEventListener("change", renderGenderScenarioEditor);
    $("#gender-scenario-seed")?.addEventListener("change", () => { void loadGenderScenarios(); });
    $("#gender-reset-confirm")?.addEventListener("change", (event) => {
      const button = $("#btn-gender-apply");
      if (button) button.disabled = !event.currentTarget.checked || !genderManifestDraft;
    });
    $("#gender-scenario-form")?.addEventListener("submit", applyGenderScenario);
    $("#btn-gender-debug")?.addEventListener("click", () => { void toggleGenderDebug(); });
    $("#gender-event-form")?.addEventListener("submit", queueGenderEvent);
    $("#gender-intent-form")?.addEventListener("submit", queueGenderIntent);
    $("#gender-battery-form")?.addEventListener("submit", runGenderBattery);

    [
      ["#gender-event-intensity", "#gender-event-intensity-value"],
      ["#gender-intent-urgency", "#gender-intent-urgency-value"],
    ].forEach(([inputSelector, outputSelector]) => {
      const input = $(inputSelector);
      const output = $(outputSelector);
      if (input && output) input.addEventListener("input", () => {
        output.textContent = f2(input.valueAsNumber);
      });
    });
  }

  async function initGenderExperience() {
    bindGenderControls();
    renderGenderExperience(null, null);
    await loadGenderScenarios();
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
      const [
        state, metrics, consciousness, ws, stream, self, mem, intro,
        gender, genderSociety,
      ] = await Promise.all([
        api("state").catch(() => null),
        api("metrics").catch(() => null),
        api("agent/consciousness").catch(() => null),
        api("agent/workspace").catch(() => null),
        api("agent/stream?limit=" + STREAM_MAX).catch(() => null),
        api("agent/self-model").catch(() => null),
        api("agent/memory?limit=20").catch(() => []),
        api("agent/introspection").catch(() => null),
        api("agent/gender").catch(() => null),
        api("society/gender").catch(() => null),
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
        const tickChip = $("#topbar-tick");
        if (tickChip) tickChip.textContent = "t " + tick;
        const cta = $("#overview-cta");
        if (cta && tick > 0 && !cta.hidden) cta.hidden = true;
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
        if (state.disclaimer) {
          const strip = $("#footer-disclaimer");
          strip.textContent = state.disclaimer;   // server text, verbatim
          strip.title = state.disclaimer;         // full text on the ellipsed strip
          const charterDisc = $("#charter-disclaimer");
          if (charterDisc) charterDisc.textContent = state.disclaimer;
        }
        if (state.framing) {
          $("#framing-text").textContent = state.framing;
          const charterFraming = $("#charter-framing");
          if (charterFraming) charterFraming.textContent = state.framing;
        }
      }

      renderMetrics(metrics, consciousness);
      if (consciousness) renderConsciousness(consciousness);
      if (ws) renderWorkspace(ws);
      else if (consciousness && consciousness.workspace) renderWorkspace(consciousness.workspace);
      if (stream) renderStream(stream);
      if (self) renderSelfModel(self);
      renderMemories(mem || []);
      if (intro) renderIntrospection(intro);
      if (gender) renderGenderExperience(gender, genderSociety);
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
      if (pollFailures) { pollFailures = 0; updateConnBanner(); }
    } catch (err) {
      console.error("refresh failed", err);
      pollFailures += 1;
      updateConnBanner();
      setStatus("error", "API error");
    }
  }

  // A quiet fixed banner after ≥3 consecutive failed poll batches; hidden on
  // the first success (the poll itself is the retry loop — nothing else to do).
  function updateConnBanner() {
    const banner = document.getElementById("conn-warning");
    if (!banner) return;
    if (pollFailures >= 3) {
      banner.hidden = false;
      banner.textContent = `Backend unreachable — retrying (${pollFailures} failed polls)`;
    } else if (!banner.hidden) {
      banner.hidden = true;
      banner.textContent = "";
      toast("Backend reachable again.", "ok");
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
    if (trace.gender_experience) {
      renderGenderExperience({
        enabled: true,
        configured: true,
        state: trace.gender_experience,
        disclaimer: trace.gender_experience.disclaimer,
      }, genderSocietyPayload);
    }
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
    lastProbeTab = name; // the probe dock reopens on the last tab used
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

  $("#btn-reset").addEventListener("click", () => {
    confirmAction(
      "Reset the simulation?",
      "The world, the agents, their memory and every learned state restart from scratch (the current slider values are applied). Saved checkpoints are kept.",
      async () => {
        try {
          stopPolling();
          await postJSON("reset", currentConfigPatch());
          resetHorizonClientState();
          setRunningUI(false);
          await refreshAll();
          await refreshMemoryGraph(true);
          await refreshClientConfig();
        } catch (e) { setStatus("error", "Reset error"); }
      });
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
      ? canvasRect.left - shellRect.left + point.x / MEMG_W * canvasRect.width
      : clientX - shellRect.left;
    const anchorY = clientY == null
      ? canvasRect.top - shellRect.top + point.y / MEMG_H * canvasRect.height
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
    // client px → LOGICAL graph coordinates (the backing store is DPR-scaled)
    const rect = canvas.getBoundingClientRect();
    const x = (ev.clientX - rect.left) * MEMG_W / Math.max(1, rect.width);
    const y = (ev.clientY - rect.top) * MEMG_H / Math.max(1, rect.height);
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
    // range inputs hand us STRINGS — coerce before the num()-based formatters
    const x = typeof v === "number" ? v : parseFloat(v);
    if (fmt === "int" || fmt === "f0") return f0(x);
    if (fmt === "f2") return f2(x);
    return f3(x);
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
          if (out && out.config) {
            clientConfig = out.config;   // nominal threshold / radius for the dials
            buildConfigFull();
          }
          // refresh the arousal baseline marker if it changed
          renderArousal(num($("#arousal-val").textContent), configValue("arousal_baseline"));
        } catch (e) { configErrorFeedback(e); }
      }, 120);
    });
  });

  // ============================================================
  //  FLAG TOGGLES -> POST /config  (Phase-2 deep + Phase-3 learning/personality)
  // ============================================================
  // checked by default (matches applyDeepDefaults); each flips one feature flag.
  // covers both the #deep-toggles (Phase 2) and #lp-toggles (Phase 3) groups.
  document.querySelectorAll(".panel-config input[data-flag]").forEach((box) => {
    if (box.hasAttribute("data-explicit-scenario-only")) return;
    box.addEventListener("change", async () => {
      const flag = box.dataset.flag;
      try {
        const out = await postJSON("config", { [flag]: box.checked });
        persistSetting({ [flag]: box.checked });   // survive reload
        if (out && out.config) { clientConfig = out.config; buildConfigFull(); }
        try { refreshCoverage(); } catch (e) { /* non-fatal */ }
      } catch (e) { configErrorFeedback(e); }
    });
  });

  // 409 = structural field: explain instead of a generic "Config error"
  function configErrorFeedback(e) {
    const fields = e && e.detail && e.detail.detail && e.detail.detail.fields;
    if (e && e.status === 409 && Array.isArray(fields)) {
      toast("Structural field (" + fields.join(", ") + ") — apply it through Reset.", "error");
      setStatus("error", "Requires reset");
    } else {
      setStatus("error", "Config error");
    }
  }

  // Client copy of the live SimConfig (nominal threshold, perception radius,
  // read-only Settings disclosure). Refreshed at boot and after every mutation.
  async function refreshClientConfig() {
    try {
      const live = await api("config");
      if (live && live.config) {
        clientConfig = live.config;
        applyControlStates(live.config);
        buildConfigFull();
      }
    } catch (e) { /* non-fatal — dials fall back to payload values */ }
  }

  $("#btn-horizon-profile")?.addEventListener("click", async (ev) => {
    const button = ev.currentTarget;
    const patch = {};
    HORIZON_FLAGS.forEach((flag) => { patch[flag] = true; });
    button.disabled = true;
    button.textContent = "Activating…";
    try {
      const out = await postJSON("config", patch);
      if (out && out.config) { clientConfig = out.config; buildConfigFull(); }
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
  let socInspectorFetchedFor = -1;

  async function refreshSociety(generation) {
    let data;
    try {
      data = await api("society");
    } catch (e) { return; }
    if (generation != null && generation !== horizonGeneration) return;
    if (!data) return;
    lastSocietyData = data;
    renderSocietyAll(data);
  }

  // One entry point re-renders every society window from the SAME payload —
  // the selection is the single source of truth, no re-fetch needed.
  function renderSocietyAll(data) {
    if (!data || !data.world) return;
    const ids = (data.world.agents || []).map((a) => num(a.id));
    if (ids.length && !ids.includes(SOC_SELECTED)) SOC_SELECTED = ids[0];
    const n = ids.length;
    // topbar + overview echoes
    const agentChip = $("#topbar-agent");
    if (agentChip) {
      agentChip.hidden = n <= 1;
      agentChip.textContent = "agent " + SOC_SELECTED;
    }
    const nEl = $("#overview-nagents");
    if (nEl) nEl.textContent = n > 1 ? "· " + n + " agents" : "";
    const langNote = $("#language-society-note");
    if (langNote) langNote.hidden = n > 1;
    drawSociety(data.world, SOC_SELECTED, data.relations);
    drawMiniSociety(data.world, SOC_SELECTED);
    renderSocietyAgents(data);
    renderRelations(data.relations, data.agents);
    renderSocietyMessages(data);
    void refreshSocietyInspector(false);
  }

  function drawSociety(world, selected, relations) {
    const cv = document.getElementById("society-canvas");
    if (!cv || !world) return;
    if (!canvasVisible(cv)) { pendingViewDraws.add("world"); return; }
    const ctx = ensureCanvasScale(cv, WORLD_L, WORLD_L);
    const g = num(world.grid_size) || 12, cell = WORLD_L / g;
    ctx.clearRect(0, 0, WORLD_L, WORLD_L);
    const KIND = {
      food: cssVar("--pos"),
      hazard: cssVar("--neg"),
      tool: cssVar("--cool"),
      curio: cssVar("--curio"),
    };
    const center = (c) => c * cell + cell / 2;
    (world.objects || []).forEach((o) => {
      ctx.fillStyle = KIND[o.kind] || cssVar("--ink-faint");
      ctx.globalAlpha = 0.7;
      traceKindShape(ctx, o.kind, center(o.x), center(o.y), cell * 0.2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    const agents = world.agents || [];
    const byId = new Map(agents.map((a) => [num(a.id), a]));
    // trust links drawn on the map: width = trust, colour = affect valence
    ((relations && relations.edges) || []).forEach((e) => {
      const a = byId.get(num(e.from)), b = byId.get(num(e.to));
      if (!a || !b) return;
      const trust = clamp01(num(e.trust));
      ctx.beginPath();
      ctx.moveTo(center(a.x), center(a.y));
      ctx.lineTo(center(b.x), center(b.y));
      ctx.strokeStyle = String(e.affect || "").includes("neg") || num(e.trust) < 0.25
        ? cssVar("--neg") : cssVar("--pos");
      ctx.globalAlpha = 0.18 + trust * 0.4;
      ctx.lineWidth = 0.8 + trust * 2.4;
      ctx.stroke();
      ctx.globalAlpha = 1;
    });
    // earshot circles of the live messages (real x/y/radius/ttl fields only)
    ((world.messages) || []).forEach((msg) => {
      const r = num(msg.radius);
      if (!(r > 0)) return;
      ctx.beginPath();
      ctx.arc(center(num(msg.x)), center(num(msg.y)), r * cell, 0, Math.PI * 2);
      ctx.strokeStyle = cssVar("--curio");
      ctx.globalAlpha = 0.12 + 0.18 * clamp01(num(msg.ttl) / 4);
      ctx.setLineDash([3, 4]);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    });
    agents.forEach((a) => {
      const ax = center(a.x), ay = center(a.y);
      const isSel = num(a.id) === selected;
      ctx.beginPath();
      ctx.arc(ax, ay, cell * 0.32, 0, Math.PI * 2);
      ctx.fillStyle = isSel ? cssVar("--accent") : cssVar("--ink");
      ctx.fill();
      if (isSel) { // double ring: selection is a SHAPE, not only a tint
        ctx.beginPath();
        ctx.arc(ax, ay, cell * 0.44, 0, Math.PI * 2);
        ctx.strokeStyle = cssVar("--accent");
        ctx.lineWidth = 1.6;
        ctx.stroke();
      }
      ctx.fillStyle = cssVar("--bg-inset");
      ctx.font = `600 ${Math.floor(cell * 0.4)}px ${cssVar("--sans") || "sans-serif"}`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(String(a.id), ax, ay);
    });
    cv.setAttribute("aria-label",
      `Society map: ${agents.length} agent${agents.length === 1 ? "" : "s"}, ` +
      `agent ${selected} selected. Arrow keys cycle the selection.`);
  }

  function drawMiniSociety(world, selected) {
    const canvas = $("#overview-society-mini");
    if (!canvas || !world) return;
    if (!canvasVisible(canvas)) { pendingViewDraws.add("overview"); return; }
    const L = 220;
    const ctx = ensureCanvasScale(canvas, L, L);
    ctx.clearRect(0, 0, L, L);
    const g = num(world.grid_size) || 12, cell = L / g;
    const center = (c) => c * cell + cell / 2;
    (world.objects || []).forEach((o) => {
      ctx.fillStyle = cssVar("--ink-faint");
      ctx.globalAlpha = 0.5;
      ctx.fillRect(center(o.x) - 1.4, center(o.y) - 1.4, 2.8, 2.8);
    });
    ctx.globalAlpha = 1;
    (world.agents || []).forEach((a) => {
      ctx.beginPath();
      ctx.arc(center(a.x), center(a.y), Math.max(3.4, cell * 0.3), 0, Math.PI * 2);
      ctx.fillStyle = num(a.id) === selected ? cssVar("--accent") : cssVar("--ink");
      ctx.fill();
    });
  }

  // Comparable agent cards — same columns for everyone (from /society.agents,
  // data already polled and previously discarded).
  function renderSocietyAgents(data) {
    const host = $("#society-agents");
    if (!host) return;
    const worldAgents = (data.world && data.world.agents) || [];
    if (worldAgents.length <= 1) { host.replaceChildren(); return; }
    host.replaceChildren();
    const frag = document.createDocumentFragment();
    worldAgents.forEach((wa) => {
      const id = num(wa.id);
      const detail = (data.agents && data.agents[String(id)]) || {};
      const met = detail.metrics || {};
      const card = el("button", "agent-card" + (id === SOC_SELECTED ? " selected" : ""));
      card.type = "button";
      card.setAttribute("aria-pressed", id === SOC_SELECTED ? "true" : "false");
      card.innerHTML =
        `<span class="ac-head"><span>agent ${id}</span><span class="mono">E ${f0(wa.energy)}</span></span>` +
        `<span>Φ ${f3(met.phi_proxy)} · aware ${f3(met.awareness_level)}</span>` +
        `<span class="micro">${esc(wa.last_action || "—")} · affect ${esc(wa.affect || "—")} ${f2(wa.valence)}</span>`;
      card.addEventListener("click", () => selectSocietyAgent(id, true));
      frag.appendChild(card);
    });
    host.appendChild(frag);
  }

  function renderRelations(rel, agents) {
    const box = document.getElementById("society-relations");
    if (!box || !rel) return;
    const edges = (rel.edges || []).slice()
      .sort((a, b) =>
        (num(b.from) === SOC_SELECTED || num(b.to) === SOC_SELECTED ? 1 : 0) -
        (num(a.from) === SOC_SELECTED || num(a.to) === SOC_SELECTED ? 1 : 0));
    box.innerHTML = edges
      .map((e) => `<div class="row"><div class="row-top">` +
        `<span class="row-title mono">${esc(e.from)} → ${esc(e.to)}</span>` +
        `<span class="row-tag">trust ${f2(e.trust)}` +
        (e.familiarity != null ? ` · fam ${f2(e.familiarity)}` : "") +
        `</span></div><div class="row-sub">${esc(e.affect)}</div></div>`)
      .join("") ||
      ((rel.nodes || []).length > 1
        ? '<div class="empty">No relations yet.</div>'
        : '<div class="empty">Single agent — no relations to model.</div>');
  }

  // Live messages of the shared world (real Message fields only: no invented
  // listeners — delivery happens next tick and is not in the payload).
  function renderSocietyMessages(data) {
    const host = $("#society-messages");
    if (!host) return;
    const messages = ((data.world && data.world.messages) || []).slice(-48);
    const filtered = (data.world && data.world.agents || []).length > 1 && SOC_SELECTED != null
      ? messages : messages;
    if (!filtered.length) {
      host.innerHTML = '<div class="empty">No live messages.</div>';
      return;
    }
    host.innerHTML = filtered.map((m) =>
      `<div class="row"><div class="row-top">` +
      `<span class="row-title">agent ${num(m.sender_id)}${m.word ? " · <span class=\"mono\">“" + esc(m.word) + "”</span>" : ""}</span>` +
      `<span class="row-tag">t${num(m.tick_emitted)} · ttl ${num(m.ttl)}</span></div>` +
      `<div class="row-sub">${esc(m.content || "")} · reach ${num(m.radius)} cells</div></div>`
    ).join("");
  }

  // Per-agent inspector (D4): a snapshot from the per-agent endpoints when the
  // selection changes — the main instrument keeps observing agent 0.
  async function refreshSocietyInspector(force) {
    const host = $("#society-inspector");
    if (!host) return;
    const n = lastSocietyData && lastSocietyData.world && lastSocietyData.world.agents
      ? lastSocietyData.world.agents.length : 1;
    if (n <= 1) {
      host.innerHTML = '<p class="micro">Single agent — every panel of the instrument already observes agent 0.</p>';
      socInspectorFetchedFor = -1;
      return;
    }
    if (!force && socInspectorFetchedFor === SOC_SELECTED) return;
    socInspectorFetchedFor = SOC_SELECTED;
    const id = SOC_SELECTED;
    host.innerHTML = `<div class="inset-box"><span class="micro">inspecting agent ${id}…</span></div>`;
    try {
      const [consc, self] = await Promise.all([
        api(`society/agent/${id}/consciousness`).catch(() => null),
        api(`society/agent/${id}/self-model`).catch(() => null),
      ]);
      if (id !== SOC_SELECTED) return;
      const cm = (consc && consc.conscious_moment) || {};
      const ws = (consc && consc.workspace) || {};
      const ast = (consc && consc.attention_schema) || {};
      host.innerHTML =
        `<div class="inset-box">` +
        `<span class="wcd-title">Agent ${id} — snapshot <span class="micro">(GET /society/agent/${id}/consciousness + self-model; the main instrument stays on agent 0)</span></span>` +
        `<div>${ws.ignited ? "ignited — global access" : "subliminal"} · score <span class="mono">${f3(ws.ignition_score)}</span> / eff <span class="mono">${f3(ws.effective_threshold != null ? ws.effective_threshold : ws.threshold)}</span></div>` +
        `<div>aware of: ${esc(ast.aware_of || cm.contents || "—")}</div>` +
        (self ? `<div>identity <span class="mono">${esc(self.identity)}</span> · energy <span class="mono">${f2(self.energy)}</span> · mood <span class="mono">${f3(self.mood)}</span> · coherence <span class="mono">${f3(self.coherence)}</span></div>` : "") +
        `</div>`;
    } catch (e) {
      if (id === SOC_SELECTED) {
        host.innerHTML = `<div class="inset-box"><span class="micro">Inspector unavailable for agent ${id}.</span></div>`;
      }
    }
  }

  function selectSocietyAgent(id, announce) {
    SOC_SELECTED = num(id);
    const sel = document.getElementById("soc-selected");
    if (sel) sel.textContent = `viewing agent ${SOC_SELECTED}`;
    const live = $("#society-selection");
    if (live && announce) {
      live.textContent = `Agent ${SOC_SELECTED} selected.`;
    }
    if (lastSocietyData) renderSocietyAll(lastSocietyData);
    void refreshSocietyInspector(true);
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
      SOC_SELECTED = 0;
      socInspectorFetchedFor = -1;
      await refreshClientConfig();
    } catch (e) { setStatus("error", "Society error"); }
  });

  document.getElementById("society-canvas")?.addEventListener("click", (ev) => {
    const cv = ev.currentTarget;
    const world = lastSocietyData && lastSocietyData.world;
    if (!world) { refreshSociety(); return; }
    const g = num(world.grid_size) || 12, cell = WORLD_L / g;
    const rect = cv.getBoundingClientRect();
    // client px → LOGICAL canvas px (backing store is DPR-scaled)
    const sx = WORLD_L / Math.max(1, rect.width), sy = WORLD_L / Math.max(1, rect.height);
    const gx = Math.floor((ev.clientX - rect.left) * sx / cell);
    const gy = Math.floor((ev.clientY - rect.top) * sy / cell);
    const hit = (world.agents || []).find((a) => num(a.x) === gx && num(a.y) === gy);
    if (hit) selectSocietyAgent(hit.id, true);
  });
  // keyboard selection: ←/→ cycle through the agents on the focused map
  document.getElementById("society-canvas")?.addEventListener("keydown", (ev) => {
    const world = lastSocietyData && lastSocietyData.world;
    const ids = ((world && world.agents) || []).map((a) => num(a.id)).sort((a, b) => a - b);
    if (!ids.length) return;
    const idx = Math.max(0, ids.indexOf(SOC_SELECTED));
    if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
      ev.preventDefault(); selectSocietyAgent(ids[(idx + 1) % ids.length], true);
    } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
      ev.preventDefault(); selectSocietyAgent(ids[(idx - 1 + ids.length) % ids.length], true);
    } else if (ev.key === "Home") {
      ev.preventDefault(); selectSocietyAgent(ids[0], true);
    } else if (ev.key === "End") {
      ev.preventDefault(); selectSocietyAgent(ids[ids.length - 1], true);
    }
  });

  // ============================================================
  //  LABORATORY (Phase 4) — time series, scenarios, export, battery
  // ============================================================
  // Draw one polyline per agent for the selected metric, auto-scaling y to the
  // metric's min/max over the window. Reads GET /metrics/history (last 200 rows).
  async function refreshLabChart(generation) {
    const cv = $("#lab-chart");
    if (!cv) return;
    // hidden view → skip the fetch entirely (200 rows per poll saved); the
    // router flushes a redraw when the Laboratory becomes visible again.
    if (!canvasVisible(cv)) { pendingViewDraws.add("laboratory"); return; }
    const W = 560, H = 220;
    const ctx = ensureCanvasScale(cv, W, H);
    ctx.clearRect(0, 0, W, H);

    const metric = ($("#lab-metric") && $("#lab-metric").value) || "energy";
    const d = await api("metrics/history?limit=200");
    if (generation != null && generation !== horizonGeneration) return;
    const rows = (d && d.series && d.series.rows) || [];
    const emptyEl = $("#lab-chart-empty");
    const legendEl = $("#lab-chart-legend");
    if (!rows.length) {
      if (emptyEl) {
        emptyEl.hidden = false;
        emptyEl.textContent = "No recorded series yet — run or train first.";
      }
      if (legendEl) legendEl.replaceChildren();
      return;
    }
    if (emptyEl) emptyEl.hidden = true;

    // group rows by agent_id, preserving order (+ keep ticks for the x axis)
    const byAgent = new Map();
    let tickLo = Infinity, tickHi = -Infinity;
    rows.forEach((r) => {
      const id = r.agent_id != null ? r.agent_id : 0;
      let arr = byAgent.get(id);
      if (!arr) { arr = []; byAgent.set(id, arr); }
      arr.push(num(r[metric]));
      const t = num(r.tick);
      if (t < tickLo) tickLo = t;
      if (t > tickHi) tickHi = t;
    });

    // auto-scale y to the min/max of the selected metric across all agents
    let lo = Infinity, hi = -Infinity;
    byAgent.forEach((vals) => vals.forEach((v) => {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }));
    if (!isFinite(lo) || !isFinite(hi)) return;
    if (hi - lo < 1e-9) { hi += 0.5; lo -= 0.5; }

    const left = 42, right = 10, top = 10, bottom = 24;
    const plotW = W - left - right, plotH = H - top - bottom;
    const maxLen = Math.max(...Array.from(byAgent.values(), (a) => a.length));
    const sx = (i) => left + (maxLen <= 1 ? 0 : (i / (maxLen - 1)) * plotW);
    const sy = (v) => top + plotH - ((v - lo) / (hi - lo)) * plotH;

    // y axis: printed min/max + midline (no silent auto-scale)
    ctx.font = "10px monospace";
    ctx.textBaseline = "middle";
    ctx.fillStyle = cssVar("--ink-faint");
    ctx.strokeStyle = cssVar("--line");
    ctx.lineWidth = 1;
    [[hi, top + 0.5], [(hi + lo) / 2, top + plotH / 2 + 0.5], [lo, top + plotH + 0.5]]
      .forEach(([v, y]) => {
        ctx.globalAlpha = 0.45;
        ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(W - right, y); ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.textAlign = "right";
        ctx.fillText(f2(v), left - 6, y);
      });
    // x axis: real tick range
    ctx.textAlign = "left";
    ctx.fillText("t" + f0(tickLo), left, H - 9);
    ctx.textAlign = "right";
    ctx.fillText("t" + f0(tickHi), W - right, H - 9);

    const palette = [
      cssVar("--accent"), cssVar("--cool"), cssVar("--pos"),
      cssVar("--curio"), cssVar("--neg"),
    ];

    let ai = 0;
    const agentIds = [];
    byAgent.forEach((vals, id) => {
      agentIds.push(id);
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

    if (legendEl) {
      legendEl.replaceChildren();
      const frag = document.createDocumentFragment();
      agentIds.forEach((id, i) => {
        const item = el("span", "lg");
        const sw = el("i", "swatch");
        sw.style.background = palette[i % palette.length];
        item.appendChild(sw);
        const last = byAgent.get(id);
        item.appendChild(document.createTextNode(
          `agent ${id} · last ${f2(last[last.length - 1])}`));
        frag.appendChild(item);
      });
      legendEl.appendChild(frag);
    }
    cv.setAttribute("aria-label",
      `Time series of ${metric} for ${byAgent.size} agent${byAgent.size === 1 ? "" : "s"}, ` +
      `ticks ${f0(tickLo)} to ${f0(tickHi)}, range ${f2(lo)} to ${f2(hi)}.`);
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
      loadBtn.addEventListener("click", () => {
        confirmAction(
          `Load checkpoint “${name}”?`,
          "The live run is replaced by the saved one (world, agents, learned state, memory, RNG).",
          async () => {
            setCkptStatus("loading " + name + "…");
            try {
              const r = await postJSON("checkpoint/load", { name });
              setCkptStatus("loaded " + name + " @ tick " + num(r && r.tick));
              resetHorizonClientState();
              await refreshAll();
              await refreshMemoryGraph(true);
              await refreshClientConfig();
            } catch (e) {
              setCkptStatus("load failed");
            }
          });
      });
      const delBtn = el("button", "btn btn-quiet micro");
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", () => {
        confirmAction(
          `Delete checkpoint “${name}”?`,
          "The saved run is removed from disk. This cannot be undone.",
          async () => {
            setCkptStatus("deleting " + name + "…");
            try {
              await postJSON("checkpoint/delete", { name });
              setCkptStatus("deleted " + name);
              refreshCheckpoints();
            } catch (e) {
              setCkptStatus("delete failed");
            }
          });
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
  //  SHELL — toasts, dialogs, router, probe dock, palette, shortcuts
  //  (Le Méridien: 8 hash views over one persistent DOM — no re-mounting,
  //   no listener churn; the router only toggles [hidden] and flushes the
  //   canvas draws that were skipped while a view was off-screen.)
  // ============================================================
  function toast(message, kind) {
    const region = $("#toast-region");
    if (!region) return;
    const node = el("div", "toast" + (kind ? " is-" + kind : ""));
    node.textContent = message;
    region.appendChild(node);
    while (region.children.length > 4) region.firstElementChild.remove();
    setTimeout(() => { node.remove(); }, 5200);
  }

  let confirmHandler = null;
  function confirmAction(title, body, onConfirm) {
    const dlg = $("#confirm-dialog");
    if (!dlg || typeof dlg.showModal !== "function") { void onConfirm(); return; }
    $("#confirm-title").textContent = title;
    $("#confirm-body").textContent = body;
    confirmHandler = onConfirm;
    dlg.showModal();
    $("#btn-confirm-ok").focus();
  }
  $("#btn-confirm-ok")?.addEventListener("click", () => {
    const dlg = $("#confirm-dialog");
    const run = confirmHandler;
    confirmHandler = null;
    if (dlg) dlg.close();
    if (run) void run();
  });
  document.querySelectorAll("dialog").forEach((dlg) => {
    dlg.addEventListener("click", (ev) => {
      const closer = ev.target.closest("[data-close-dialog]");
      if (closer) { ev.preventDefault(); dlg.close(); }
      // a navigation link inside a dialog (More sheet) also closes it
      if (ev.target.closest("a[href^='#/']")) dlg.close();
    });
    dlg.addEventListener("close", () => {
      if (dlg.id === "confirm-dialog") confirmHandler = null;
    });
  });

  function openCharter() {
    const dlg = $("#charter");
    if (dlg && typeof dlg.showModal === "function" && !dlg.open) dlg.showModal();
  }
  document.addEventListener("click", (ev) => {
    const opener = ev.target.closest("[data-open-charter]");
    if (opener) {
      ev.preventDefault();
      const host = opener.closest("dialog");
      if (host && host.open) host.close();
      openCharter();
    }
  });
  $("#btn-charter-ack")?.addEventListener("click", () => {
    try { localStorage.setItem("humanity.ui.charter.dismissed", "1"); } catch (e) { /* ignore */ }
  });

  // ---------- hash router ----------
  const VIEW_DEFS = [
    { name: "overview", title: "Overview" },
    { name: "workspace", title: "Workspace" },
    { name: "world", title: "World & society" },
    { name: "mind", title: "Mind" },
    { name: "learning-language", title: "Learning & language" },
    { name: "laboratory", title: "Laboratory" },
    { name: "memory", title: "Memory" },
    { name: "settings", title: "Settings" },
  ];
  let activeView = "overview";

  function parseRoute() {
    const m = /^#\/([\w-]+)(?:\/([\w-]+))?/.exec(location.hash || "");
    const name = m && VIEW_DEFS.some((v) => v.name === m[1]) ? m[1] : null;
    return { view: name, section: m ? m[2] : null };
  }

  // Re-run the draws that were skipped while this view was hidden — always
  // from cached data (the poll keeps accumulating regardless of the view).
  function flushViewDraws(view) {
    if (!pendingViewDraws.has(view)) return;
    pendingViewDraws.delete(view);
    if (view === "world") {
      if (currentWorldSnap) drawWorld(currentWorldSnap);
      if (lastSocietyData) renderSocietyAll(lastSocietyData);
    } else if (view === "workspace") {
      renderIgnitionDynamics(null, lastTick);
    } else if (view === "memory") {
      drawMemoryGraph(memoryGraphCache);
    } else if (view === "laboratory") {
      refreshLabChart().catch(() => {});
    } else if (view === "mind") {
      drawCircadianDial(lastDaylight);
    } else if (view === "overview") {
      updateAperture(lastWorkspaceState);
      if (currentWorldSnap) drawMiniWorld(currentWorldSnap);
      if (lastSocietyData) drawMiniSociety(lastSocietyData.world, SOC_SELECTED);
    }
  }

  function activateView(name, section) {
    activeView = name;
    document.querySelectorAll(".view").forEach((sec) => {
      sec.hidden = sec.dataset.view !== name;
    });
    document.querySelectorAll("#app-nav .nav-item").forEach((a) => {
      if (a.dataset.nav === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    document.querySelectorAll(".tabbar a[data-tab]").forEach((a) => {
      if (a.dataset.tab === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    const def = VIEW_DEFS.find((v) => v.name === name);
    const crumb = $("#topbar-view");
    if (crumb) crumb.textContent = def ? def.title : name;
    document.title = "Humanity — " + (def ? def.title : "Instrument");
    try { localStorage.setItem("humanity.ui.lastRoute", "#/" + name); } catch (e) { /* ignore */ }
    document.body.classList.remove("nav-open");
    flushViewDraws(name);
    if (section) {
      const target = document.getElementById(section) ||
        document.querySelector(`#view-${name} .panel-${section}`);
      if (target) target.scrollIntoView({ block: "start" });
    } else {
      window.scrollTo(0, 0);
    }
  }

  function onHashChange() {
    const route = parseRoute();
    if (!route.view) { location.replace("#/overview"); return; }
    activateView(route.view, route.section);
  }
  window.addEventListener("hashchange", onHashChange);

  // ---------- sidebar / mobile nav ----------
  function setNavCollapsed(collapsed) {
    document.body.classList.toggle("nav-collapsed", collapsed);
    try { localStorage.setItem("humanity.ui.nav", collapsed ? "collapsed" : "open"); } catch (e) { /* ignore */ }
  }
  $("#btn-nav-collapse")?.addEventListener("click", () => {
    setNavCollapsed(!document.body.classList.contains("nav-collapsed"));
  });
  $("#btn-nav-toggle")?.addEventListener("click", () => {
    const open = document.body.classList.toggle("nav-open");
    $("#btn-nav-toggle").setAttribute("aria-expanded", String(open));
  });
  $("#btn-more")?.addEventListener("click", () => {
    const dlg = $("#more-sheet");
    if (dlg && typeof dlg.showModal === "function") dlg.showModal();
  });

  // ---------- probe dock (one instrument, two windows) ----------
  // The interventions panel is a SINGLE DOM node whose canonical home is the
  // Laboratory; opening the dock ADOPTS the node into the drawer (listeners,
  // tab state and the correlated ledger move with it) and closing returns it.
  const DOCK_DEFAULT_TAB = { workspace: "inject", world: "stimulus", mind: "perturb", memory: "ask" };
  let lastProbeTab = "ask";
  let interventionsHome = null;
  let dockHideTimer = null;
  function dockIsOpen() { return document.body.classList.contains("dock-open"); }
  function setDockOpen(open, forcedTab) {
    const dock = $("#probe-dock");
    const panel = $("#experimental-interventions");
    if (!dock || !panel) return;
    if (open) {
      if (!interventionsHome) {
        interventionsHome = { parent: panel.parentElement, next: panel.nextElementSibling };
      }
      clearTimeout(dockHideTimer);
      dock.hidden = false;
      $("#probe-dock-body").appendChild(panel);
      requestAnimationFrame(() => document.body.classList.add("dock-open"));
      const tab = forcedTab || DOCK_DEFAULT_TAB[activeView] || lastProbeTab;
      activateIntervention(tab, false);
      lastProbeTab = tab;
      const tabBtn = document.querySelector(`#intervention-tabs [data-intervention="${tab}"]`);
      if (tabBtn) tabBtn.focus();
    } else if (dockIsOpen()) {
      document.body.classList.remove("dock-open");
      if (interventionsHome && interventionsHome.parent) {
        interventionsHome.parent.insertBefore(panel, interventionsHome.next);
      }
      dockHideTimer = setTimeout(() => {
        if (!dockIsOpen()) dock.hidden = true;
      }, 260);
      $("#btn-probe")?.focus();
    }
  }
  $("#btn-probe")?.addEventListener("click", () => setDockOpen(!dockIsOpen()));
  $("#btn-probe-close")?.addEventListener("click", () => setDockOpen(false));

  // ---------- command palette (Ctrl/Cmd+K) ----------
  const paletteState = { items: [], sel: 0 };
  function goView(name, section) {
    location.hash = "#/" + name + (section ? "/" + section : "");
  }
  function clickLater(sel) {
    const node = document.querySelector(sel);
    if (node) setTimeout(() => node.click(), 60);
  }
  function buildPaletteCommands() {
    const cmds = [];
    VIEW_DEFS.forEach((v, i) => cmds.push({
      kind: "cmd", label: "Go to " + v.title, hint: "#/" + v.name + " · " + (i + 1),
      run: () => goView(v.name),
    }));
    cmds.push(
      { kind: "cmd", label: "Run / pause simulation", hint: "POST /run · r", run: () => (running ? $("#btn-pause") : $("#btn-start"))?.click() },
      { kind: "cmd", label: "Step one tick", hint: "POST /tick · s", run: () => $("#btn-step")?.click() },
      { kind: "cmd", label: "Reset simulation…", hint: "POST /reset · Shift+R", run: () => $("#btn-reset")?.click() },
      { kind: "cmd", label: "Toggle theme", hint: "t", run: () => $("#btn-theme")?.click() },
      { kind: "cmd", label: "Toggle probe dock", hint: "p", run: () => setDockOpen(!dockIsOpen()) },
      { kind: "cmd", label: "Open epistemic charter", hint: "!", run: openCharter },
      { kind: "cmd", label: "Show keyboard shortcuts", hint: "?", run: showShortcutsHelp },
      { kind: "cmd", label: "Save checkpoint", hint: "POST /checkpoint/save", run: () => { goView("laboratory", "ckpt-title"); clickLater("#btn-ckpt-save"); } },
      { kind: "cmd", label: "Export metrics CSV", hint: "GET /export.csv", run: () => $("#btn-export-csv")?.click() },
      { kind: "cmd", label: "Export metrics JSON", hint: "GET /export.json", run: () => $("#btn-export-json")?.click() },
      { kind: "cmd", label: "Export trace analysis", hint: "GET /export/analysis", run: () => $("#btn-export-analysis")?.click() },
      { kind: "cmd", label: "Activate all Phase 7", hint: "POST /config", run: () => $("#btn-horizon-profile")?.click() },
    );
    [["mirror", "Mirror"], ["false-memory", "False memory"], ["calibration", "Calibration"],
     ["relational-self", "Relational self"], ["masking", "Masking"], ["blink", "Attentional blink"],
     ["priming", "Subliminal priming"], ["reality-monitor", "Reality monitoring"],
     ["language-genesis", "Language genesis"]].forEach(([id, label]) => {
      cmds.push({
        kind: "cmd", label: "Run battery: " + label,
        hint: "POST /battery/" + id.replace(/-/g, "_"),
        run: () => { goView("laboratory", "batteries-title"); clickLater("#btn-" + id); },
      });
    });
    document.querySelectorAll("#lab-metric option").forEach((opt) => {
      cmds.push({
        kind: "metric", label: "Metric: " + opt.textContent.trim(), hint: "@ time series",
        run: () => {
          goView("laboratory", "series-title");
          const select = $("#lab-metric");
          select.value = opt.value;
          select.dispatchEvent(new Event("change"));
        },
      });
    });
    document.querySelectorAll(".panel-config input[data-flag]").forEach((box) => {
      const label = box.closest(".deep-toggle");
      const name = label ? label.querySelector("span").textContent.trim() : box.dataset.flag;
      cmds.push({
        kind: "setting", label: "Setting: " + name, hint: "# " + box.dataset.flag,
        run: () => focusSetting(label, name),
      });
    });
    document.querySelectorAll("#config-sliders .slider-row").forEach((row) => {
      const name = row.querySelector(".slider-label").firstChild.textContent.trim();
      cmds.push({
        kind: "setting", label: "Setting: " + name, hint: "# " + row.dataset.key,
        run: () => focusSetting(row, name),
      });
    });
    return cmds;
  }
  function focusSetting(node, term) {
    goView("settings");
    const filter = $("#settings-filter");
    if (filter) {
      filter.value = term;
      filter.dispatchEvent(new Event("input"));
    }
    if (node) {
      setTimeout(() => {
        node.scrollIntoView({ block: "center" });
        node.classList.add("settings-hit");
        const input = node.querySelector("input");
        if (input) input.focus({ preventScroll: true });
        setTimeout(() => node.classList.remove("settings-hit"), 2400);
      }, 80);
    }
  }
  function paletteFilter(term) {
    let pool = paletteState.items;
    let text = term.trim().toLowerCase();
    if (text.startsWith(">")) { pool = pool.filter((c) => c.kind === "cmd"); text = text.slice(1).trim(); }
    else if (text.startsWith("@")) { pool = pool.filter((c) => c.kind === "metric"); text = text.slice(1).trim(); }
    else if (text.startsWith("#")) { pool = pool.filter((c) => c.kind === "setting"); text = text.slice(1).trim(); }
    if (!text) return pool.slice(0, 14);
    return pool
      .map((c) => ({ c, at: c.label.toLowerCase().indexOf(text) }))
      .filter((x) => x.at >= 0 || (x.c.hint || "").toLowerCase().includes(text))
      .sort((a, b) => (a.at < 0 ? 99 : a.at) - (b.at < 0 ? 99 : b.at))
      .slice(0, 14)
      .map((x) => x.c);
  }
  function renderPalette(list) {
    const host = $("#palette-results");
    host.replaceChildren();
    if (!list.length) {
      const liEmpty = el("li", "p-empty", "No matching command.");
      liEmpty.setAttribute("role", "option");
      host.appendChild(liEmpty);
      return;
    }
    list.forEach((c, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === paletteState.sel));
      li.innerHTML = `<span class="p-label">${esc(c.label)}</span><span class="p-hint">${esc(c.hint || "")}</span>`;
      li.addEventListener("click", () => runPaletteItem(c));
      host.appendChild(li);
    });
  }
  let paletteList = [];
  function refreshPaletteResults() {
    paletteList = paletteFilter($("#palette-input").value || "");
    if (paletteState.sel >= paletteList.length) paletteState.sel = Math.max(0, paletteList.length - 1);
    renderPalette(paletteList);
  }
  function runPaletteItem(item) {
    $("#command-palette").close();
    if (item) void item.run();
  }
  function openPalette() {
    const dlg = $("#command-palette");
    if (!dlg || typeof dlg.showModal !== "function" || dlg.open) return;
    paletteState.items = buildPaletteCommands();
    paletteState.sel = 0;
    const input = $("#palette-input");
    input.value = "";
    dlg.showModal();
    refreshPaletteResults();
    input.focus();
  }
  $("#btn-palette")?.addEventListener("click", openPalette);
  $("#palette-input")?.addEventListener("input", () => { paletteState.sel = 0; refreshPaletteResults(); });
  $("#palette-input")?.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { ev.preventDefault(); paletteState.sel = Math.min(paletteList.length - 1, paletteState.sel + 1); renderPalette(paletteList); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); paletteState.sel = Math.max(0, paletteState.sel - 1); renderPalette(paletteList); }
    else if (ev.key === "Enter") { ev.preventDefault(); runPaletteItem(paletteList[paletteState.sel]); }
  });

  function showShortcutsHelp() {
    confirmAction("Keyboard shortcuts",
      "1–8 views · r run/pause · s step · Shift+R reset · p probe dock · t theme · " +
      "[ sidebar · ! charter · / search memory (on Memory) · Ctrl/Cmd+K commands · arrows drive the world grid, " +
      "the society map, the memory graph and the access chart.",
      () => {});
  }

  // ---------- global shortcuts ----------
  document.addEventListener("keydown", (ev) => {
    if (ev.defaultPrevented) return;
    const meta = ev.ctrlKey || ev.metaKey;
    if (meta && (ev.key === "k" || ev.key === "K")) { ev.preventDefault(); openPalette(); return; }
    if (meta || ev.altKey) return;
    const dlgOpen = document.querySelector("dialog[open]");
    if (ev.key === "Escape" && dockIsOpen() && !dlgOpen) { setDockOpen(false); return; }
    if (dlgOpen || ev.target.closest("input, textarea, select, [contenteditable='true']")) return;
    const k = ev.key;
    if (k >= "1" && k <= "8") { goView(VIEW_DEFS[+k - 1].name); return; }
    if (k === "r") { (running ? $("#btn-pause") : $("#btn-start"))?.click(); return; }
    if (k === "s") { $("#btn-step")?.click(); return; }
    if (k === "R") { $("#btn-reset")?.click(); return; }
    if (k === "p") { setDockOpen(!dockIsOpen()); return; }
    if (k === "t") { $("#btn-theme")?.click(); return; }
    if (k === "[") { setNavCollapsed(!document.body.classList.contains("nav-collapsed")); return; }
    if (k === "!") { openCharter(); return; }
    if (k === "?") { showShortcutsHelp(); return; }
    if (k === "/" && activeView === "memory") { ev.preventDefault(); $("#memory-search-input")?.focus(); }
  });

  // ---------- settings: filter + full read-only configuration ----------
  (function initSettingsFilter() {
    const input = $("#settings-filter");
    if (!input) return;
    input.addEventListener("input", () => {
      const term = input.value.trim().toLowerCase();
      let hits = 0;
      document.querySelectorAll("#view-settings .settings-group").forEach((group) => {
        let groupHits = 0;
        group.querySelectorAll(".deep-toggle, .slider-row").forEach((row) => {
          const flag = row.querySelector("input[data-flag]");
          const haystack = (row.textContent + " " + (row.dataset.key || "") + " " +
            (flag ? flag.dataset.flag : "") + " " + (row.title || "") + " " +
            (group.dataset.group || "")).toLowerCase();
          const hit = !term || haystack.includes(term);
          row.classList.toggle("filtered-out", !hit);
          if (hit) groupHits++;
        });
        group.classList.toggle("filtered-out", !!term && groupHits === 0);
        hits += groupHits;
      });
      const count = $("#settings-filter-count");
      if (count) count.textContent = term ? hits + " match" + (hits === 1 ? "" : "es") : "";
    });
  })();

  // Defaults of every SimConfig field (schemas/models.py) so the read-only
  // disclosure can print live value vs default without inventing anything.
  const CONFIG_STRUCTURAL = ["grid_size", "n_objects", "random_seed", "n_agents",
    "stream_length", "metrics_history_max", "phi_ar_window", "phi_causal_window", "n_concepts"];
  const CONFIG_CATALOG = [
    ["World & agent", { grid_size: 12, n_objects: 10, world_noise: 0.1, perception_radius: 3, random_seed: 42, initial_energy: 100 }],
    ["Attention & memory", { attention_capacity: 4, working_memory_capacity: 5, working_memory_decay: 4, memory_importance_threshold: 0.25, memory_retrieval_k: 3 }],
    ["Drives & learning", { curiosity: 1, caution: 1, energy_drive: 1, coherence_drive: 1, learning_rate: 0.2 }],
    ["Consciousness architecture", { ignition_threshold: 0.3, workspace_temp: 0.5, precision_weight: 1, epistemic_weight: 1, pragmatic_weight: 1, stream_length: 20 }],
    ["Ignition dynamics", { arousal_baseline: 0.45, arousal_gain: 1, competition_sharpness: 3, ignition_maintenance: 0.12 }],
    ["Society", { n_agents: 1, comm_radius: 4, message_ttl: 2, contagion_rate: 0.15, affiliation_drive: 1 }],
    ["Phase 2 — deep consciousness", { circadian_enabled: false, circadian_period: 50, night_threshold: 0.3, sleep_enabled: false, dream_enabled: false, sleep_fatigue_threshold: 0.8, wake_fatigue_threshold: 0.35, max_sleep_ticks: 30, replay_boost: 1.3, consolidation_prune_threshold: 0, imagination_enabled: false, imagination_horizon: 3, curiosity_enabled: false, curiosity_window: 8, agency_enabled: false }],
    ["Phase 3 — learning & personality", { learning_enabled: false, value_learning_rate: 0.2, value_learning_weight: 0.5, concepts_enabled: false, n_concepts: 6, concept_lr: 0.2, meta_learning_enabled: false, meta_lr_min: 0.05, meta_lr_max: 0.6, personality_enabled: false, personality_drift: 0.05 }],
    ["Phase 4 — instrument", { metrics_history_max: 1000 }],
    ["Performance & persistence", { persist_memory: true, trace_logging: true }],
    ["Behaviour balance", { satiation_enabled: false, satiation_weight: 3, explore_reward_weight: 0.5 }],
    ["Relational & reflexive self", { social_mirror_enabled: false, social_mirror_weight: 0.3, self_opacity_enabled: false, individuation_enabled: false, individuation_drive: 1 }],
    ["Phase 5 — the asymptote", { recurrence_enabled: false, recurrence_passes: 3, recurrence_gain: 0.5, reality_monitor_enabled: false, intero_inference_enabled: false, intero_lr: 0.25, temporality_enabled: false, retention_horizon: 5, protention_window: 6, inner_speech_enabled: false, inner_speech_gain: 0.6, phi_ar_enabled: false, phi_ar_window: 32, phi_ar_every: 8, priming_enabled: false, priming_decay: 0.5, priming_gain: 0.35 }],
    ["Phase 6 — the invention of language", { language_drive_enabled: false, language_drive: 1 }],
    ["Phase 7 — the horizon", { phi_causal_enabled: false, phi_causal_nodes: 5, phi_causal_window: 96, phi_causal_every: 16, hierarchy_enabled: false, hierarchy_lr: 0.15, hierarchy_gain: 0.3, planning_enabled: false, planning_horizon: 3, planning_discount: 0.7, vector_memory_enabled: false, semantic_weight: 0.6, td_learning_enabled: false, td_lambda: 0.8, td_discount: 0.9, mind_wandering_enabled: false, wandering_gain: 0.6, world_dynamics_enabled: false, season_period: 200, regrow_rate: 0.02, tasks_enabled: false }],
    ["Phase 8 — situated gendered self", { gender_experience_enabled: false, gender_affect_weight: 0.2, gender_motivation_weight: 1, gender_internalization_rate: 0.05, gender_recovery_rate: 0.03, gender_event_memory_max: 256 }],
  ];
  const cfgFmt = (v) => typeof v === "boolean" ? (v ? "on" : "off") : String(v);
  function buildConfigFull() {
    const host = $("#config-full");
    if (!host) return;
    if (!clientConfig || !Object.keys(clientConfig).length) {
      host.innerHTML = '<div class="empty">Configuration not loaded yet.</div>';
      return;
    }
    host.replaceChildren();
    const frag = document.createDocumentFragment();
    CONFIG_CATALOG.forEach(([group, fields]) => {
      frag.appendChild(el("div", "cf-group", esc(group)));
      Object.entries(fields).forEach(([key, def]) => {
        const live = clientConfig[key];
        const row = el("div", "cf-row");
        row.innerHTML =
          `<span class="cf-key">${esc(key)}${CONFIG_STRUCTURAL.includes(key) ? '<span class="cf-structural">reset</span>' : ""}</span>` +
          `<span class="cf-val">${esc(cfgFmt(live != null ? live : def))}</span>` +
          `<span class="cf-def">default ${esc(cfgFmt(def))}</span>`;
        frag.appendChild(row);
      });
    });
    host.appendChild(frag);
  }

  // ============================================================
  //  INIT
  // ============================================================
  // shell first: the router decides which view is visible before first paint
  (function initShellRoute() {
    try {
      if (localStorage.getItem("humanity.ui.nav") === "collapsed") setNavCollapsed(true);
    } catch (e) { /* ignore */ }
    let saved = null;
    try { saved = localStorage.getItem("humanity.ui.lastRoute"); } catch (e) { /* ignore */ }
    if (!parseRoute().view) location.replace(saved && /^#\/[\w-]+$/.test(saved) ? saved : "#/overview");
    onHashChange();
  })();
  ensureMetricCells();
  updateAperture(null);
  drawWorld(null);
  drawCircadianDial(1);
  drawMemoryGraph(memoryGraphCache);
  renderIgnitionDynamics(null, -1);
  // HiDPI: re-render a canvas when its CSS box resizes (one observer each)
  observeCanvasResize($("#world-canvas"), () => { if (currentWorldSnap) drawWorld(currentWorldSnap); });
  observeCanvasResize($("#society-canvas"), () => { if (lastSocietyData) drawSociety(lastSocietyData.world, SOC_SELECTED, lastSocietyData.relations); });
  observeCanvasResize($("#ignition-chart"), () => renderIgnitionDynamics(null, lastTick));
  observeCanvasResize($("#memory-graph"), () => drawMemoryGraph(memoryGraphCache));
  observeCanvasResize($("#lab-chart"), () => { refreshLabChart().catch(() => {}); });
  // apply the saved settings (or first-run defaults), then take the first reading
  async function bootstrap() {
    try { await initGenderExperience(); } catch (e) { /* Phase 8 remains explicitly dormant */ }
    try { await applyDeepDefaults(); } catch (e) { /* first reading still useful */ }
    await refreshAll();
    try { await refreshCoverage(); } catch (e) { /* non-fatal */ }
    try { await refreshMemoryGraph(true); } catch (e) { /* non-fatal */ }
    try { await refreshCheckpoints(); } catch (e) { /* non-fatal */ }
    try { await refreshClientConfig(); } catch (e) { /* non-fatal */ }
    // first launch: the epistemic charter presents the boundary once
    try {
      if (!localStorage.getItem("humanity.ui.charter.dismissed")) openCharter();
    } catch (e) { /* ignore */ }
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
