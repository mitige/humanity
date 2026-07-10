"""Static contracts for the five live intervention controls in the UI.

The API behavior itself is covered by ``tests/test_interaction.py``.  These
tests make sure the Observatoire exposes every modality it documents and that
the world canvas is genuinely operable with a pointer and a keyboard.
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
        self.endpoints: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.by_id[values["id"]] = {"tag": tag, **values}
        endpoint = values.get("data-endpoint")
        if endpoint:
            self.endpoints.add(endpoint)


def _sources() -> tuple[str, str, str, _MarkupProbe]:
    html = (ROOT / "ui/index.html").read_text(encoding="utf-8")
    js = (ROOT / "ui/app.js").read_text(encoding="utf-8")
    css = (ROOT / "ui/styles.css").read_text(encoding="utf-8")
    probe = _MarkupProbe()
    probe.feed(html)
    return html, js, css, probe


def _without_js_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(^|\s)//[^\n]*", r"\1", source)


def test_observatory_exposes_all_five_intervention_modalities() -> None:
    html, js, css, probe = _sources()
    expected = {
        "/agent/ask",
        "/world/stimulus",
        "/agent/inject",
        "/agent/attend",
        "/agent/perturb",
    }

    assert "experimental-interventions" in probe.by_id
    assert expected <= probe.endpoints
    for control in (
        "intervention-tabs",
        "intervention-ask-question",
        "intervention-stimulus-kind",
        "intervention-inject-content",
        "intervention-attend-target",
        "intervention-perturb-type",
        "interaction-log",
    ):
        assert control in probe.by_id

    log = probe.by_id["interaction-log"]
    assert log.get("aria-live") in {"polite", "assertive"}
    assert "aria-label" in log

    active_js = _without_js_comments(js)
    for endpoint in expected:
        assert endpoint in active_js
    for function in (
        "activateIntervention",
        "submitIntervention",
        "appendInterventionLog",
    ):
        assert f"function {function}" in active_js
    assert ".panel-interventions" in css
    assert ".intervention-tabs" in css
    assert ".interaction-log" in css


def test_world_canvas_posts_pointer_and_keyboard_stimuli() -> None:
    _html, js, css, probe = _sources()
    canvas = probe.by_id["world-canvas"]
    assert canvas.get("tabindex") == "0"
    assert canvas.get("aria-describedby") == "world-interaction-help"
    for control in ("world-stimulus-kind", "world-stimulus-intensity", "world-interaction-status"):
        assert control in probe.by_id
    assert probe.by_id["world-interaction-status"].get("aria-live") in {"polite", "assertive"}

    active_js = _without_js_comments(js)
    for function in ("mapWorldPointToGrid", "postWorldStimulusAt", "drawWorldCursor"):
        assert f"function {function}" in active_js
    assert re.search(r'worldCanvas\.addEventListener\(\s*["\']click["\']', active_js)
    assert re.search(r'worldCanvas\.addEventListener\(\s*["\']keydown["\']', active_js)
    assert 'postJSON("world/stimulus"' in active_js
    assert "ArrowLeft" in active_js and "ArrowRight" in active_js
    assert 'ev.key === "Enter"' in active_js
    assert ".world-interaction-tools" in css
    assert "#world-canvas:focus-visible" in css


def test_interventions_are_serialized_correlated_and_cache_busted() -> None:
    html, js, css, _probe = _sources()
    active_js = _without_js_comments(js)

    assert html.count("?v=7.3") == 2
    assert "let interventionPending = false" in active_js
    assert "function setInterventionBusy" in active_js
    assert "if (interventionPending) return" in active_js
    assert "correlationId" in active_js
    assert 'response.effect.applied === false' in active_js
    assert "#world-interaction-status { color: var(--ink-soft); }" in css
    assert ".interaction-sequence { color: var(--ink-soft);" in css
    assert "body.is-scrolled .tps-field { display: none; }" in css
    assert "body.is-scrolled .transport-buttons" in css


def test_manual_step_is_strictly_serialized_and_generation_safe() -> None:
    _html, js, _css, _probe = _sources()
    active_js = _without_js_comments(js)
    listener_start = active_js.find('$("#btn-step").addEventListener')
    listener_end = active_js.find('$("#btn-start").addEventListener', listener_start)
    listener = active_js[listener_start:listener_end]

    assert "let stepInFlight = false" in active_js[:listener_start]
    assert "if (stepInFlight) return" in listener

    lock = listener.find("stepInFlight = true")
    disable = listener.find("stepButton.disabled = true")
    first_await = listener.find("await ")
    assert 0 <= lock < first_await
    assert 0 <= disable < first_await

    finally_start = listener.find("finally {")
    assert finally_start >= 0
    finally_body = listener[finally_start:]
    assert "stepInFlight = false" in finally_body
    assert "stepButton.disabled = false" in finally_body

    generation_capture = listener.find("const generation = horizonGeneration")
    stale_tick = listener.find("generation !== horizonGeneration", first_await)
    apply_trace = listener.find("applyTrace(trace)")
    canonical_refresh = listener.find("await refreshAll()", apply_trace)
    stale_refresh = listener.find(
        "generation !== horizonGeneration", canonical_refresh)
    graph_refresh = listener.find(
        "await refreshMemoryGraph(true)", stale_refresh)
    assert 0 <= generation_capture < first_await < stale_tick < apply_trace
    assert apply_trace < canonical_refresh < stale_refresh < graph_refresh < finally_start
