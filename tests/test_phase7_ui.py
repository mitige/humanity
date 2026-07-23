import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_IDS = {
    "horizon-readouts",
    "ignition-chart",
    "ignition-chart-summary",
    "horizon-stream",
    "memory-graph",
    "memory-graph-nodes",
    "memory-graph-edges",
    "memory-graph-summary",
    "memory-search-input",
    "horizon-task",
}
EXPECTED_FLAGS = {
    "phi_causal_enabled",
    "hierarchy_enabled",
    "planning_enabled",
    "vector_memory_enabled",
    "td_learning_enabled",
    "mind_wandering_enabled",
    "world_dynamics_enabled",
    "tasks_enabled",
}
EXPECTED_FUNCTIONS = (
    "renderHorizon",
    "renderIgnitionDynamics",
    "renderHorizonStream",
    "refreshMemoryGraph",
    "drawMemoryGraph",
)
EXPECTED_CSS_SELECTORS = (
    ".panel-horizon",
    ".horizon-readouts",
    ".memory-graph-shell",
    ".sr-only",
)

_JS_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\r\n]*", re.DOTALL)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


class _HTMLAttributeCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.data_flags = set()
        self.elements = {}
        self.hrefs = set()
        self.srcs = set()

    def handle_starttag(self, _tag, attrs):
        self._collect(attrs)

    def handle_startendtag(self, _tag, attrs):
        self._collect(attrs)

    def _collect(self, attrs):
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.elements[element_id] = attributes
        for name, value in attrs:
            if name == "id" and value:
                self.ids.add(value)
            elif name == "data-flag" and value:
                self.data_flags.add(value)
            elif name == "href" and value:
                self.hrefs.add(value)
            elif name == "src" and value:
                self.srcs.add(value)


def _strip_js_comments(source):
    return _JS_COMMENT_RE.sub("", source)


def _format_violations(violations):
    return "Phase 7 contract violations:\n- " + "\n- ".join(violations)


def test_horizon_observatory_is_wired_end_to_end():
    html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
    js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
    css = (ROOT / "ui/styles.css").read_text(encoding="utf-8")
    violations = []

    attributes = _HTMLAttributeCollector()
    attributes.feed(html)
    attributes.close()

    missing_ids = EXPECTED_IDS - attributes.ids
    if missing_ids:
        violations.append(f"missing HTML ids: {sorted(missing_ids)}")

    missing_data_flags = EXPECTED_FLAGS - attributes.data_flags
    if missing_data_flags:
        violations.append(
            f"missing HTML data-flag values: {sorted(missing_data_flags)}"
        )

    if "styles.css?v=8.1" not in attributes.hrefs:
        violations.append("styles.css cache-buster must be exactly ?v=8.1")
    if "app.js?v=8.1" not in attributes.srcs:
        violations.append("app.js cache-buster must be exactly ?v=8.1")
    if not any(href.startswith("data:image/svg+xml") for href in attributes.hrefs):
        violations.append("UI must provide an inline favicon without a 404 request")

    for canvas_id, summary_id in (
        ("ignition-chart", "ignition-chart-summary"),
        ("memory-graph", "memory-graph-summary"),
    ):
        canvas_attrs = attributes.elements.get(canvas_id, {})
        summary_attrs = attributes.elements.get(summary_id, {})
        described_by = set(canvas_attrs.get("aria-describedby", "").split())
        if summary_id not in described_by:
            violations.append(
                f"{canvas_id} must reference accessible summary {summary_id}"
            )
        if not summary_attrs:
            violations.append(f"missing accessible summary: {summary_id}")

    memory_graph_attrs = attributes.elements.get("memory-graph", {})
    if memory_graph_attrs.get("tabindex") != "0":
        violations.append("memory-graph canvas must be keyboard-focusable")
    if "memory-graph-nodes" not in set(
        memory_graph_attrs.get("aria-describedby", "").split()
    ):
        violations.append("memory-graph must describe every node via memory-graph-nodes")
    if "memory-graph-edges" not in set(
        memory_graph_attrs.get("aria-describedby", "").split()
    ):
        violations.append("memory-graph must describe every edge via memory-graph-edges")
    memory_nodes_attrs = attributes.elements.get("memory-graph-nodes", {})
    if memory_nodes_attrs.get("aria-label") != "Indexed autobiographical memory nodes":
        violations.append("memory-graph-nodes needs its explicit accessible label")
    memory_edges_attrs = attributes.elements.get("memory-graph-edges", {})
    if memory_edges_attrs.get("aria-label") != "Autobiographical memory similarity edges":
        violations.append("memory-graph-edges needs its explicit accessible label")

    for quiet_id in ("horizon-task", "ignition-chart-summary"):
        if "aria-live" in attributes.elements.get(quiet_id, {}):
            violations.append(f"{quiet_id} must not announce on every poll")

    executable_js = _strip_js_comments(js)
    settings_match = re.search(
        r"\b(?:const|let|var)\s+SETTINGS_DEFAULTS\s*=\s*\{(?P<body>.*?)\}\s*;",
        executable_js,
        re.DOTALL,
    )
    if settings_match is None:
        violations.append("SETTINGS_DEFAULTS object definition is missing")
    else:
        settings_body = settings_match.group("body")
        missing_defaults = {
            flag
            for flag in EXPECTED_FLAGS
            if re.search(
                rf"\b{re.escape(flag)}\s*:\s*true\b",
                settings_body,
            )
            is None
        }
        if missing_defaults:
            violations.append(
                "SETTINGS_DEFAULTS must enable: "
                f"{sorted(missing_defaults)}"
            )

    for function_name in EXPECTED_FUNCTIONS:
        definition_pattern = rf"\bfunction\s+{re.escape(function_name)}\s*\("
        definitions = list(re.finditer(definition_pattern, executable_js))
        if not definitions:
            violations.append(f"missing exact JS definition: {function_name}")
            continue

        js_without_definitions = re.sub(definition_pattern, "", executable_js)
        call_pattern = rf"\b{re.escape(function_name)}\s*\("
        if re.search(call_pattern, js_without_definitions) is None:
            violations.append(
                f"{function_name} is defined but never called"
            )

    for endpoint in (
        "agent/memory/search?q=${encodeURIComponent(query)}&limit=8",
        "agent/memory/graph?limit=60&edges=3",
    ):
        if endpoint not in executable_js:
            violations.append(f"missing exact Phase 7 endpoint: {endpoint}")

    if "Math.random" in executable_js:
        violations.append("Phase 7 UI must remain deterministic: Math.random is forbidden")

    for marker in (
        "refreshInFlight",
        "refreshQueued",
        "horizonGeneration",
        "resetHorizonClientState",
    ):
        if marker not in executable_js:
            violations.append(f"missing Phase 7 race-safety marker: {marker}")

    if re.search(
        r"requestedTick\s*-\s*lastMemoryGraphTick\s*<\s*20",
        executable_js,
    ) is None:
        violations.append(
            "memory graph throttle must use requestedTick - lastMemoryGraphTick < 20"
        )
    if re.search(r"%\s*20", executable_js):
        violations.append(
            "memory graph refresh must not depend on observing exact modulo-20 ticks"
        )

    refresh_start = executable_js.find("async function refreshAll(")
    apply_start = executable_js.find("function applyTrace(")
    polling_start = executable_js.find("function startPolling(")
    refresh_body = executable_js[refresh_start:apply_start]
    apply_body = executable_js[apply_start:polling_start]
    if refresh_start < 0 or "refreshMemoryGraph(false)" not in refresh_body:
        violations.append("refreshAll must delegate graph throttling to refreshMemoryGraph")
    if apply_start < 0 or "refreshMemoryGraph(" in apply_body:
        violations.append("applyTrace must not race the canonical Step graph refresh")

    bootstrap_start = executable_js.find("async function bootstrap(")
    bootstrap_end = executable_js.find("void bootstrap()", bootstrap_start)
    bootstrap_body = executable_js[bootstrap_start:bootstrap_end]
    defaults = bootstrap_body.find("await applyDeepDefaults()")
    initial_refresh = bootstrap_body.find("await refreshAll()", defaults)
    initial_graph = bootstrap_body.find("await refreshMemoryGraph(true)", initial_refresh)
    if not (0 <= defaults < initial_refresh < initial_graph):
        violations.append(
            "bootstrap must settle config, canonical state, then exclusive graph in order"
        )

    perform_start = executable_js.find("async function performRefreshAll(")
    perform_end = executable_js.find("function applyTrace(", perform_start)
    perform_body = executable_js[perform_start:perform_end]
    generation_capture = perform_body.find("const generation = horizonGeneration")
    generation_guard = perform_body.find("if (generation !== horizonGeneration) return")
    first_repaint = perform_body.find("drawWorld(")
    if not (
        0 <= generation_capture < generation_guard < first_repaint
    ):
        violations.append(
            "performRefreshAll must reject a pre-reset snapshot before any repaint"
        )
    incoming_tick = perform_body.find("const incomingTick")
    stale_tick_guard = perform_body.find("if (incomingTick < lastTick) return")
    if not (0 <= incoming_tick < stale_tick_guard < first_repaint):
        violations.append(
            "performRefreshAll must reject older ticks before repainting"
        )

    graph_start = executable_js.find("async function refreshMemoryGraph(")
    graph_end = executable_js.find("function drawGraphEdge(")
    graph_body = executable_js[graph_start:graph_end]
    generation_checks = graph_body.count("generation !== horizonGeneration")
    cache_write = graph_body.find("memoryGraphCache =")
    first_generation_check = graph_body.find("generation !== horizonGeneration")
    if generation_checks < 2 or not (
        0 <= first_generation_check < cache_write
    ):
        violations.append(
            "memory graph must reject stale generations before cache writes and repaints"
        )
    if "memoryGraphRequest === request" not in graph_body:
        violations.append("memory graph finally must only clear its own request")

    reset_start = executable_js.find('$("#btn-reset").addEventListener')
    reset_end = executable_js.find("$(\"#goal-form\")", reset_start)
    reset_body = executable_js[reset_start:reset_end]
    if "resetHorizonClientState()" not in reset_body:
        violations.append("reset must invalidate all Horizon client state")

    checkpoint_start = executable_js.find('loadBtn.addEventListener("click"')
    checkpoint_end = executable_js.find("const delBtn", checkpoint_start)
    checkpoint_body = executable_js[checkpoint_start:checkpoint_end]
    if "resetHorizonClientState()" not in checkpoint_body:
        violations.append("checkpoint load must invalidate all Horizon client state")
    if "refreshMemoryGraph(true)" not in checkpoint_body:
        violations.append("checkpoint load must force repaint its restored memory graph")

    step_start = executable_js.find('$("#btn-step").addEventListener')
    step_end = executable_js.find('$("#btn-start").addEventListener', step_start)
    step_body = executable_js[step_start:step_end]
    generation_capture = step_body.find("const generation = horizonGeneration")
    step_try = step_body.find("try {")
    if not (0 <= generation_capture < step_try):
        violations.append("Step must capture the Horizon generation before awaiting /tick")
    if re.search(
        r'const\s+trace\s*=\s*await\s+postJSON\("tick"\);\s*'
        r'if\s*\(generation\s*!==\s*horizonGeneration\)\s*return;\s*'
        r'applyTrace\(trace\);',
        step_body,
    ) is None:
        violations.append("Step must reject a stale /tick response before applyTrace")
    refresh_after_trace = step_body.find("await refreshAll()", step_body.find("applyTrace(trace)"))
    force_graph = step_body.find("await refreshMemoryGraph(true)", refresh_after_trace)
    if not (0 <= refresh_after_trace < force_graph):
        violations.append(
            "Step must await canonical post-action state then force its memory graph"
        )

    society_start = executable_js.find(
        'document.getElementById("btn-society-apply")?.addEventListener')
    society_end = executable_js.find(
        'document.getElementById("society-canvas")?.addEventListener', society_start)
    society_body = executable_js[society_start:society_end]
    society_post = society_body.find('await postJSON("society/config"')
    society_reset = society_body.find("resetHorizonClientState()")
    society_refresh = society_body.find("await refreshAll()")
    society_graph = society_body.find("await refreshMemoryGraph(true)")
    if not (
        0 <= society_post < society_reset < society_refresh < society_graph
    ):
        violations.append(
            "society reset must invalidate only after success and repaint canonical state"
        )

    for export_path in ("export.csv", "export.json"):
        if f"`${{API}}/{export_path}`" not in executable_js:
            violations.append(
                f"laboratory export must target root API path: {export_path}"
            )

    for keyboard_marker in (
        'addEventListener("keydown"',
        '"ArrowRight"',
        '"ArrowLeft"',
        '"Home"',
        '"End"',
    ):
        if keyboard_marker not in executable_js:
            violations.append(f"missing memory-graph keyboard control: {keyboard_marker}")
    for tooltip_dimension in ("tooltip.offsetHeight", "tooltip.offsetWidth"):
        if tooltip_dimension not in executable_js:
            violations.append(f"tooltip must measure rendered size: {tooltip_dimension}")

    css_without_comments = _BLOCK_COMMENT_RE.sub("", css)
    for selector in EXPECTED_CSS_SELECTORS:
        selector_pattern = rf"^[ \t]*{re.escape(selector)}[ \t]*\{{"
        if re.search(selector_pattern, css_without_comments, re.MULTILINE) is None:
            violations.append(f"missing exact CSS rule selector: {selector}")

    assert not violations, _format_violations(violations)


def test_phase7_is_documented_and_final_roadmap_is_completed():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    violations = []

    if re.search(r"^## Phase 7\b", readme, re.MULTILINE) is None:
        violations.append("missing level-2 README heading: Phase 7")
    if re.search(r"^## Future extensions$", readme, re.MULTILINE):
        violations.append("obsolete future-extensions heading remains")

    roadmap_match = re.search(
        r"(?P<section>^## Roadmap completed$(?:(?!^## ).)*)\Z",
        readme,
        re.MULTILINE | re.DOTALL,
    )
    if roadmap_match is None:
        violations.append("missing completed roadmap as final level-2 section")
        roadmap_section = ""
    else:
        roadmap_section = roadmap_match.group("section")

    for marker in (
        "### Foundations delivered — Phases 1–6",
        "### Phase 7 — The Horizon delivered",
        "### Phase 8 — The situated gendered self delivered",
        "### Delivery quality completed",
        "Coarse causal Φ",
        "Predictive hierarchy and VFE",
        "Multi-step EFE planning",
        "Semantic vector memory",
        "Contextual TD(λ)",
        "Mind-wandering / default mode",
        "Living world dynamics",
        "Structured tasks",
        "Horizon Observatoire and interventions",
        "Atomic persistence and checkpoints",
        "692/692 tests",
    ):
        if marker not in roadmap_section:
            violations.append(f"missing completed-roadmap evidence: {marker}")

    assert not violations, _format_violations(violations)
