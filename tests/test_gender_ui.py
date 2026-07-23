"""Static product contracts for the Phase-8 gender-experience observatory.

The engine/API behavior lives in the other ``test_gender_*`` modules.  These
checks keep the reader-facing boundary honest: no silent activation, no
identity inference in JavaScript, and no private profile in the polling path.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


class _MarkupProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.by_id: dict[str, dict[str, str]] = {}
        self.tags_by_id: dict[str, str] = {}
        self.flags: dict[str, dict[str, str]] = {}
        self.hrefs: set[str] = set()
        self.srcs: set[str] = set()

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key: value if value is not None else "" for key, value in attrs}
        element_id = values.get("id")
        if element_id:
            self.by_id[element_id] = values
            self.tags_by_id[element_id] = tag
        flag = values.get("data-flag")
        if flag:
            self.flags[flag] = values
        if values.get("href"):
            self.hrefs.add(values["href"])
        if values.get("src"):
            self.srcs.add(values["src"])


def _sources() -> tuple[str, str, str, _MarkupProbe]:
    html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
    js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
    css = (ROOT / "ui/styles.css").read_text(encoding="utf-8")
    probe = _MarkupProbe()
    probe.feed(html)
    return html, js, css, probe


def _function_body(js: str, name: str, next_name: str) -> str:
    start = js.find(f"function {name}(")
    end = js.find(f"function {next_name}(", start + 1)
    assert start >= 0 and end > start
    return js[start:end]


def test_gender_observatory_has_three_explicit_information_boundaries() -> None:
    html, _js, css, probe = _sources()
    normalized_html = " ".join(html.split())
    required = {
        "gender-experience",
        "gender-empty",
        "gender-observatory",
        "gender-private-content",
        "gender-self-content",
        "gender-public-content",
        "gender-life-track",
        "gender-life-list",
        "gender-congruence",
        "gender-affect",
        "gender-stress",
        "gender-resilience",
        "gender-expression",
        "gender-body",
        "gender-transitions",
    }
    assert required <= probe.by_id.keys()
    assert probe.tags_by_id["gender-life-list"] == "ol"
    assert probe.by_id["gender-life-track"].get("aria-hidden") == "true"
    assert "Semantic gender life-course timeline" == probe.by_id[
        "gender-life-list"
    ].get("aria-label")

    private = html.find('class="gender-layer gender-layer-private"')
    self_layer = html.find('class="gender-layer gender-layer-self"')
    public = html.find('class="gender-layer gender-layer-public"')
    assert 0 <= private < self_layer < public
    for phrase in (
        "Never available to simulated observers",
        "Identity is never inferred",
        "Private affinities, body preferences and undisclosed intents never appear",
        "not clinical scales",
        "no treatment protocol or medical advice",
    ):
        assert phrase in normalized_html

    assert ".mind-grid > .panel-gender { grid-column: span 12; }" in css
    assert "--gender-private" in css
    assert "--gender-self" in css
    assert "--gender-public" in css
    phase8_css = css[css.index("SITUATED GENDERED SELF"):css.index(
        ".panel-horizon",
        css.index("SITUATED GENDERED SELF"),
    )].lower()
    assert "pink" not in phase8_css
    assert "blue" not in phase8_css


def test_gender_scenario_controls_are_configurable_and_reset_gated() -> None:
    html, js, _css, probe = _sources()
    normalized_html = " ".join(html.split())
    for element_id in (
        "gender-scenario-form",
        "gender-scenario-select",
        "gender-scenario-seed",
        "gender-reset-confirm",
        "btn-gender-apply",
        "gender-life-editor",
        "gender-life-stages",
        "gender-context-fields",
    ):
        assert element_id in probe.by_id
    assert "disabled" in probe.by_id["btn-gender-apply"]
    assert "fully resets the current run" in normalized_html
    assert "Stages may be omitted, adult-start paths are valid" in normalized_html

    for function in (
        "loadGenderScenarios",
        "renderGenderLifeEditor",
        "buildGenderManifestFromEditor",
        "applyGenderScenario",
    ):
        assert f"function {function}" in js
    apply_body = _function_body(js, "applyGenderScenario", "hideGenderDebug")
    assert 'postJSON("gender/scenario", { scenario: manifest })' in apply_body
    assert "confirm.checked" in apply_body
    assert "resetHorizonClientState()" in apply_body
    assert 'api(`gender/scenarios?seed=${encodeURIComponent(seed)}`)' in js
    assert "Number(card.dataset.stageIndex)" in js
    assert "genderSyncedProfileId !== state.profile_id" in js


def test_phase8_cannot_be_silently_enabled_from_local_storage() -> None:
    _html, js, _css, probe = _sources()
    gate = probe.flags["gender_experience_enabled"]
    assert "checked" not in gate
    assert "disabled" in gate
    assert "data-explicit-scenario-only" in gate

    assert js.count("delete safe.gender_experience_enabled") == 1
    assert js.count("delete parsed.gender_experience_enabled") == 1
    assert 'box.hasAttribute("data-explicit-scenario-only")' in js
    defaults = re.search(
        r"const SETTINGS_DEFAULTS\s*=\s*\{(?P<body>.*?)\n\s*\};",
        js,
        flags=re.S,
    )
    assert defaults is not None
    assert "gender_experience_enabled" not in defaults.group("body")


def test_private_debug_is_explicit_and_background_refresh_is_safe() -> None:
    _html, js, _css, probe = _sources()
    assert probe.by_id["btn-gender-debug"].get("aria-expanded") == "false"
    assert 'api("agent/gender/debug")' in js
    reveal = _function_body(js, "revealGenderDebug", "toggleGenderDebug")
    assert 'api("agent/gender/debug")' in reveal

    perform = js[
        js.index("async function performRefreshAll("):
        js.index("function applyTrace(")
    ]
    assert 'api("agent/gender")' in perform
    assert 'api("society/gender")' in perform
    assert "agent/gender/debug" not in perform
    assert "renderGenderExperience(gender, genderSociety)" in perform


def test_gender_probes_use_enum_templates_and_show_provenance() -> None:
    html, js, _css, probe = _sources()
    for element_id in (
        "gender-event-form",
        "gender-event-type",
        "gender-event-domain",
        "gender-intent-form",
        "gender-intent-type",
        "gender-intent-dimension",
        "gender-probe-log",
        "gender-battery-form",
        "gender-battery-result",
    ):
        assert element_id in probe.by_id
    assert "Hostility (fixed enum, no dialogue)" in html
    assert "Provenance is recorded as" in html

    event_body = _function_body(js, "queueGenderEvent", "queueGenderIntent")
    assert 'postJSON("agent/gender/event"' in event_body
    assert "note:" not in event_body
    assert 'provenance: response.event.provenance' in event_body
    intent_body = _function_body(js, "queueGenderIntent", "renderGenderBattery")
    assert 'postJSON("agent/gender/intent"' in intent_body
    assert 'provenance: response.intent.provenance' in intent_body
    assert 'postJSON("battery/gender-experience"' in js


def test_gender_ui_is_responsive_accessible_and_cache_busted() -> None:
    html, _js, css, probe = _sources()
    assert "styles.css?v=8.1" in probe.hrefs
    assert "app.js?v=8.1" in probe.srcs
    assert html.count("?v=8.1") == 2
    assert probe.by_id["gender-scenario-status"].get("aria-live") == "polite"
    assert probe.by_id["gender-probe-log"].get("aria-live") == "polite"
    assert probe.by_id["gender-battery-result"].get("aria-live") == "polite"
    mobile = css[css.index("@media (max-width: 560px)"):]
    for contract in (
        ".gender-scenario-form { grid-template-columns: 1fr; }",
        ".gender-signal-groups { grid-template-columns: 1fr; }",
        ".gender-transition-grid { grid-template-columns: 1fr; }",
        ".gender-probe-form fieldset { grid-template-columns: 1fr; }",
        ".panel-gender input[type=\"range\"] { min-height: 44px; }",
    ):
        assert contract in mobile
    assert ".gender-layer-grid { grid-template-columns: 1fr; }" in css


def test_readme_documents_phase8_without_a_mandatory_identity_pipeline() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    for phrase in (
        "## Phase 8 — The situated gendered self",
        "not as the mandatory pipeline",
        "Identity is never inferred from dysphoria, expression, body coordinates",
        "External and internalized transphobia",
        "Accentuated expression, including hyperfeminine/hypermasculine paths",
        "A configurable life course",
        "Independent transition paths",
        "not evidence that the reported effect sizes or causal relations hold for real people",
        "not diagnostic, predictive, clinical, phenomenological, culturally exhaustive",
    ):
        assert phrase in normalized

    for preset_id in (
        "transfeminine_early",
        "transfeminine_late",
        "transmasculine_early",
        "transmasculine_late",
        "nonbinary",
        "genderfluid",
        "agender",
        "euphoria_led",
        "social_transition_only",
        "partial_medical_transition",
        "cis_control",
    ):
        assert f"`{preset_id}`" in readme

    for endpoint in (
        "/gender/scenarios",
        "/gender/scenario",
        "/agent/gender/debug",
        "/society/gender",
        "/export/gender-scenario",
        "/battery/gender-experience",
    ):
        assert endpoint in readme

    for image_name in (
        "gender-experience.png",
        "gender-dynamics.png",
        "gender-instrument.png",
    ):
        assert f"(docs/images/{image_name})" in readme
        image_path = ROOT / "docs" / "images" / image_name
        assert image_path.is_file()
        assert image_path.stat().st_size > 75_000

    assert "tests-692%20passing" in readme
    assert "# 692 deterministic tests" in readme
