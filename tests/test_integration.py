"""Tests for the IIT-inspired integrated-information proxy (NOT true Phi).

These exercise ``core.integration.IntegrationMonitor.phi_proxy``: the proxy is
always bounded in [0, 1] for varied inputs; identical coalition vectors under a
strong broadcast integrate more than orthogonal vectors; and empty/degenerate
inputs do not crash.
"""
from __future__ import annotations

import pytest

from core.global_workspace import GlobalWorkspace
from core.integration import IntegrationMonitor
from schemas.models import Coalition, SimConfig


def _cfg() -> SimConfig:
    """Deterministic config for the integration tests."""
    return SimConfig(random_seed=42, world_noise=0.0)


def _coalition(source: str, activation: float, vector: list[float]) -> Coalition:
    """Build a Coalition directly (bypassing competition) for controlled inputs."""
    return Coalition(
        source=source,
        content=source,
        activation=activation,
        precision=1.0,
        vector=vector,
    )


def test_phi_proxy_bounded_for_varied_inputs() -> None:
    """phi_proxy (and its components) stay within [0, 1] across varied inputs."""
    mon = IntegrationMonitor()
    cases = [
        ([], 0.0),
        ([_coalition("perception", 1.0, [1.0])], 1.0),
        (
            [
                _coalition("perception", 0.6, [1.0, 0.0, -1.0]),
                _coalition("memory", 0.3, [-1.0, 1.0, 0.5]),
                _coalition("motivation", 0.1, [0.2, 0.2, 0.2]),
            ],
            0.8,
        ),
        (
            [
                _coalition("a", 0.25, [0.0, 0.0]),
                _coalition("b", 0.25, [0.0, 0.0]),
                _coalition("c", 0.25, [1.0, 1.0]),
                _coalition("d", 0.25, [1.0, 1.0]),
            ],
            5.0,  # deliberately out-of-range broadcast: must be clamped internally
        ),
    ]
    for coalitions, bcast in cases:
        state = mon.phi_proxy(coalitions, bcast)
        assert 0.0 <= state.phi_proxy <= 1.0
        assert 0.0 <= state.differentiation <= 1.0
        assert 0.0 <= state.integration <= 1.0
        assert state.n_elements == len(coalitions)


def test_identical_vectors_integrate_more_than_orthogonal() -> None:
    """Identical coalition vectors + strong broadcast => higher integration."""
    cfg = _cfg()
    mon = IntegrationMonitor()

    gw_ident = GlobalWorkspace(cfg)
    identical = [
        gw_ident.make_coalition("perception", "A", 0.9, 0.9, [1.0, 1.0, 1.0]),
        gw_ident.make_coalition("memory", "B", 0.5, 0.8, [1.0, 1.0, 1.0]),
        gw_ident.make_coalition("motivation", "C", 0.4, 0.7, [1.0, 1.0, 1.0]),
    ]
    ws_ident = gw_ident.compete(identical, cfg)
    int_ident = mon.phi_proxy(ws_ident.competition, ws_ident.broadcast_strength)

    gw_orth = GlobalWorkspace(cfg)
    orthogonal = [
        gw_orth.make_coalition("perception", "A", 0.9, 0.9, [1.0, 0.0, 0.0]),
        gw_orth.make_coalition("memory", "B", 0.5, 0.8, [0.0, 1.0, 0.0]),
        gw_orth.make_coalition("motivation", "C", 0.4, 0.7, [0.0, 0.0, 1.0]),
    ]
    ws_orth = gw_orth.compete(orthogonal, cfg)
    int_orth = mon.phi_proxy(ws_orth.competition, ws_orth.broadcast_strength)

    # The two fields share the same activation pattern (hence broadcast), so the
    # difference is driven purely by inter-part similarity (binding).
    assert int_ident.integration > int_orth.integration
    assert int_ident.phi_proxy > int_orth.phi_proxy


def test_empty_and_degenerate_inputs_do_not_crash() -> None:
    """Empty / single / zero-vector inputs return a valid, bounded state."""
    mon = IntegrationMonitor()

    empty = mon.phi_proxy([], 0.0)
    assert empty.phi_proxy == 0.0
    assert empty.n_elements == 0

    # A single element cannot be differentiated against alternatives.
    single = mon.phi_proxy([_coalition("perception", 0.5, [0.3, 0.4])], 0.4)
    assert single.n_elements == 1
    assert single.differentiation == 0.0
    assert 0.0 <= single.phi_proxy <= 1.0

    # Zero-vector coalitions: cosine similarity must not divide by zero.
    zeros = mon.phi_proxy(
        [_coalition("a", 0.5, [0.0, 0.0]), _coalition("b", 0.5, [0.0, 0.0])],
        0.5,
    )
    assert 0.0 <= zeros.phi_proxy <= 1.0

    # Coalitions without any feature vectors at all.
    novec = mon.phi_proxy(
        [_coalition("a", 0.5, []), _coalition("b", 0.5, [])],
        0.5,
    )
    assert 0.0 <= novec.phi_proxy <= 1.0


def test_partition_label_documents_proxy_nature() -> None:
    """The partition label flags this as a heuristic MIB proxy, not true Phi."""
    mon = IntegrationMonitor()
    state = mon.phi_proxy([_coalition("a", 1.0, [1.0])], 1.0)
    assert "MIB-proxy" in state.partition
