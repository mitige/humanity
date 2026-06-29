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

  // ---------- state ----------
  let running = false;
  let pollTimer = null;
  let lastGrid = 12;
  let lastTick = -1;

  // client-side metric history for sparklines
  const HISTORY = {};
  const pushHist = (key, v) => {
    const a = HISTORY[key] || (HISTORY[key] = []);
    a.push(num(v));
    if (a.length > HIST) a.shift();
  };
  // client-side stream of ConsciousMoment {ignited, awareness_level}
  let streamData = [];

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
    const merged = {
      phi_proxy: m.phi_proxy != null ? m.phi_proxy : integ.phi_proxy,
      arousal: m.arousal != null ? m.arousal : cm.arousal,
      free_energy: m.free_energy != null ? m.free_energy : cm.free_energy,
      prediction_error: m.prediction_error,
      self_coherence: m.self_coherence,
      meta_confidence: m.meta_confidence != null ? m.meta_confidence : meta.meta_confidence,
      energy: m.energy,
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
  //  REFRESH (poll /state + agent endpoints)
  // ============================================================
  async function refreshAll() {
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

      if (state) {
        const snap = state.world || state.snapshot || state;
        drawWorld(snap);
        const tick = num(snap.tick != null ? snap.tick : (metrics && metrics.tick));
        $("#world-meta").textContent = "tick " + tick + " · GET /state";
        lastTick = tick;
        // canonical arousal source: GET /state.arousal
        if (state.arousal != null) renderArousal(state.arousal, configValue("arousal_baseline"));
        if (typeof state.running === "boolean") setRunningUI(state.running);
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
    } catch (err) {
      console.error("refresh failed", err);
      setStatus("error", "API error");
    }
  }

  // After a manual tick we have a full CycleTrace — apply it for the richest update.
  function applyTrace(trace) {
    if (!trace) return;
    if (trace.observation) {
      drawWorld({
        grid_size: lastGrid,
        tick: trace.observation.tick,
        radius: trace.observation.radius,
        agent: {
          x: trace.observation.agent_x, y: trace.observation.agent_y,
          energy: trace.observation.agent_energy,
        },
        objects: trace.observation.visible || [],
      });
      $("#world-meta").textContent = "tick " + num(trace.tick) + " · POST /tick";
    }
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
  }

  // ============================================================
  //  POLLING
  // ============================================================
  function startPolling() { stopPolling(); pollTimer = setInterval(refreshAll, POLL_MS); }
  function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } }

  // ============================================================
  //  CONTROLS
  // ============================================================
  $("#btn-step").addEventListener("click", async () => {
    try {
      const trace = await postJSON("tick");
      applyTrace(trace);
      const mem = await api("agent/memory?limit=20").catch(() => []);
      renderMemories(mem || []);
    } catch (e) { setStatus("error", "Tick error"); }
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
      // wipe client-side history so sparklines/stream restart clean
      for (const k in HISTORY) delete HISTORY[k];
      streamData = [];
      renderStream(null);
      await postJSON("reset", currentConfigPatch());
      setRunningUI(false);
      refreshAll();
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
          const out = await postJSON("config", currentConfigPatch());
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
  //  INIT
  // ============================================================
  ensureMetricCells();
  drawWorld(null);
  refreshAll();
})();
