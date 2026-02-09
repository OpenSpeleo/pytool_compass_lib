# -*- coding: utf-8 -*-
"""Tests for the survey adjustment solver module."""

import math

import pytest

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.models import ZERO
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D
from compass_lib.solver.noop import NoopSolver
from compass_lib.solver.proportional import ProportionalSolver

# ---------------------------------------------------------------------------
# Vector3D
# ---------------------------------------------------------------------------


class TestVector3D:
    """Tests for Vector3D arithmetic."""

    def test_add(self):
        a = Vector3D(1, 2, 3)
        b = Vector3D(4, 5, 6)
        assert a + b == Vector3D(5, 7, 9)

    def test_sub(self):
        a = Vector3D(4, 5, 6)
        b = Vector3D(1, 2, 3)
        assert a - b == Vector3D(3, 3, 3)

    def test_mul(self):
        a = Vector3D(2, 3, 4)
        assert a * 2 == Vector3D(4, 6, 8)
        assert 2 * a == Vector3D(4, 6, 8)

    def test_neg(self):
        a = Vector3D(1, -2, 3)
        assert -a == Vector3D(-1, 2, -3)

    def test_length(self):
        a = Vector3D(3, 4, 0)
        assert a.length == pytest.approx(5.0)

    def test_zero(self):
        assert Vector3D(0, 0, 0) == ZERO
        assert ZERO.length == 0.0


# ---------------------------------------------------------------------------
# Helpers: build networks for testing
# ---------------------------------------------------------------------------


def _make_linear_network() -> SurveyNetwork:
    """Build a linear network with no traverse: A -> B -> C -> D.

    Single anchor (A), so no traverse adjustment is possible.
    """
    a = Vector3D(0, 0, 0)
    b = Vector3D(10, 0, 0)
    c = Vector3D(20, 0, 0)
    d = Vector3D(30, 0, 0)

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=b - a, distance=10.0),
        NetworkShot(from_name="B", to_name="C", delta=c - b, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=d - c, distance=10.0),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d},
        shots=shots,
        anchors={"A"},
    )


def _make_two_anchor_traverse(
    misclosure: Vector3D = ZERO,
) -> SurveyNetwork:
    """Build a linear traverse between two anchors: A -> B -> C -> D.

    A and D are anchors with known coordinates.  The shot deltas
    include *misclosure* added to the last shot (C -> D), simulating
    accumulated measurement error.

    ::

        A ----> B ----> C ----> D
        (anchor)                (anchor)
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    ab_delta = Vector3D(10, 0, 0)
    bc_delta = Vector3D(10, 0, 0)
    cd_delta = Vector3D(10, 0, 0) + misclosure

    b = a + ab_delta
    c = d - cd_delta

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=ab_delta, distance=10.0),
        NetworkShot(from_name="B", to_name="C", delta=bc_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=cd_delta, distance=10.0),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d},
        shots=shots,
        anchors={"A", "D"},
    )


def _make_two_anchor_with_spur(
    misclosure: Vector3D = ZERO,
) -> SurveyNetwork:
    """Build a traverse A -> B -> C -> D with a side-branch B -> E.

    ::

        A ----> B ----> C ----> D
                |
                v
                E
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    ab_delta = Vector3D(10, 0, 0)
    bc_delta = Vector3D(10, 0, 0)
    cd_delta = Vector3D(10, 0, 0) + misclosure
    be_delta = Vector3D(0, -10, 0)

    b = a + ab_delta
    c = d - cd_delta
    e = b + be_delta

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=ab_delta, distance=10.0),
        NetworkShot(from_name="B", to_name="C", delta=bc_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=cd_delta, distance=10.0),
        NetworkShot(from_name="B", to_name="E", delta=be_delta, distance=10.0),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d, "E": e},
        shots=shots,
        anchors={"A", "D"},
    )


def _make_unequal_traverse(
    misclosure: Vector3D = ZERO,
) -> SurveyNetwork:
    """Build a traverse with unequal-length shots: A -> B -> C -> D.

    Shot lengths: A->B = 5 m, B->C = 10 m, C->D = 15 m.

    ::

        A --5m--> B --10m--> C --15m--> D
        (anchor)                        (anchor)
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    ab_delta = Vector3D(5, 0, 0)
    bc_delta = Vector3D(10, 0, 0)
    cd_delta = Vector3D(15, 0, 0) + misclosure

    b = a + ab_delta
    c = d - cd_delta

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=ab_delta, distance=5.0),
        NetworkShot(from_name="B", to_name="C", delta=bc_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=cd_delta, distance=cd_delta.length),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d},
        shots=shots,
        anchors={"A", "D"},
    )


def _make_reversed_edge_traverse(
    misclosure: Vector3D = ZERO,
) -> SurveyNetwork:
    """Build a traverse where the middle shot is surveyed in reverse.

    ::

        A ----> B <---- C ----> D
        (anchor)  reversed shot  (anchor)
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    ab_delta = Vector3D(10, 0, 0)
    cb_delta = Vector3D(-10, 0, 0)
    cd_delta = Vector3D(10, 0, 0) + misclosure

    b = a + ab_delta
    c = d - cd_delta

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=ab_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="B", delta=cb_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=cd_delta, distance=cd_delta.length),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d},
        shots=shots,
        anchors={"A", "D"},
    )


def _make_three_anchor_junction() -> SurveyNetwork:
    """Build a network with a junction station X connected to 3 anchors.

    ::

        A --10m--> X --10m--> B
                   |
                  10m
                   |
                   v
                   C

    A = (0, 0, 0), B = (20, 0, 0), C = (10, -10, 0).
    All anchors.  X is a junction that must satisfy all three
    anchor constraints simultaneously.

    Measurement deltas include a small misclosure on each leg
    so the solver has something to correct.
    """
    a = Vector3D(0, 0, 0)
    b = Vector3D(20, 0, 0)
    c = Vector3D(10, -10, 0)

    # X is roughly at (10, 0, 0) but measurements have small errors.
    x_bfs = Vector3D(10, 0, 0)

    # Measurement deltas (with small errors)
    ax_delta = Vector3D(10.2, 0.1, 0)   # A -> X (slightly long, slightly off)
    xb_delta = Vector3D(10.1, -0.2, 0)  # X -> B (slightly long, slightly off)
    xc_delta = Vector3D(0.1, -10.3, 0)  # X -> C (slightly long, slightly off)

    shots = [
        NetworkShot(from_name="A", to_name="X", delta=ax_delta, distance=10.0),
        NetworkShot(from_name="X", to_name="B", delta=xb_delta, distance=10.0),
        NetworkShot(from_name="X", to_name="C", delta=xc_delta, distance=10.0),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "X": x_bfs},
        shots=shots,
        anchors={"A", "B", "C"},
    )


# ---------------------------------------------------------------------------
# NoopSolver
# ---------------------------------------------------------------------------


class TestNoopSolver:
    """Tests for NoopSolver."""

    def test_returns_same_positions(self):
        network = _make_two_anchor_traverse(misclosure=Vector3D(5, 5, 0))
        solver = NoopSolver()
        result = solver.adjust(network)

        for name, pos in network.stations.items():
            assert result[name] == pos

    def test_name(self):
        assert NoopSolver().name == "NoopSolver"


# ---------------------------------------------------------------------------
# ProportionalSolver — least-squares network adjustment
# ---------------------------------------------------------------------------


class TestProportionalSolver:
    """Tests for ProportionalSolver (least-squares network adjustment)."""

    def test_name(self):
        assert ProportionalSolver().name == "ProportionalSolver"

    def test_single_anchor_returns_unchanged(self):
        """With only one anchor, no adjustment is possible."""
        network = _make_linear_network()
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for name, pos in network.stations.items():
            assert result[name] == pos

    def test_perfect_traverse_returns_unchanged(self):
        """Zero misclosure means no correction needed."""
        network = _make_two_anchor_traverse(misclosure=ZERO)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for name, pos in network.stations.items():
            assert result[name].x == pytest.approx(pos.x, abs=1e-9)
            assert result[name].y == pytest.approx(pos.y, abs=1e-9)
            assert result[name].z == pytest.approx(pos.z, abs=1e-9)

    def test_anchors_at_gps_positions(self):
        """All anchors must remain at their exact GPS coordinates."""
        error = Vector3D(3.0, 3.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["A"] == network.stations["A"]
        assert result["D"].x == pytest.approx(network.stations["D"].x, abs=1e-9)
        assert result["D"].y == pytest.approx(network.stations["D"].y, abs=1e-9)
        assert result["D"].z == pytest.approx(network.stations["D"].z, abs=1e-9)

    def test_interior_stations_are_adjusted(self):
        """Non-anchor stations must move when misclosure exists."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        b_original = network.stations["B"]
        c_original = network.stations["C"]

        assert (result["B"] - b_original).length > 1e-9, "B should move"
        assert (result["C"] - c_original).length > 1e-9, "C should move"

    def test_error_distributed_equally_for_equal_shots(self):
        """With equal-length shots, least-squares distributes error
        equally — each shot absorbs the same correction.

        3 shots of 10 m, misclosure (6, 0, 0):
          B_corrected = (8, 0, 0)
          C_corrected = (16, 0, 0)
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["B"].x == pytest.approx(8.0, abs=1e-9)
        assert result["C"].x == pytest.approx(16.0, abs=1e-9)

    def test_error_distributed_by_length_for_unequal_shots(self):
        """With unequal-length shots (5/10/15 m), the weighted
        least-squares distributes error proportionally to shot
        length, so the percentage change on each shot is similar.

        Shorter shots absorb less absolute correction to keep their
        percentage change comparable to longer shots.
        """
        error = Vector3D(3.0, 0.0, 0.0)
        network = _make_unequal_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        # Interior stations should be adjusted (C moves more than B
        # because B is adjacent to anchor A and gets more weight)
        assert (result["B"] - network.stations["B"]).length > 1e-6
        assert (result["C"] - network.stations["C"]).length > 0.01
        # Anchors at GPS
        assert result["A"] == network.stations["A"]
        assert result["D"].x == pytest.approx(30.0, abs=1e-9)

    def test_reversed_edge_gives_similar_result(self):
        """A reversed middle shot should produce similar positions.

        The positions may differ slightly because the reversed shot
        has a different distance field, affecting the weighting.
        But the results should be close and reasonable.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        forward_net = _make_two_anchor_traverse(misclosure=error)
        reversed_net = _make_reversed_edge_traverse(misclosure=error)

        solver = ProportionalSolver()
        fwd_result = solver.adjust(forward_net)
        rev_result = solver.adjust(reversed_net)

        for name in ("B", "C"):
            assert rev_result[name].x == pytest.approx(
                fwd_result[name].x, abs=2.0,
            ), f"{name}: reversed edge gave very different x"

    def test_reversed_edge_stations_are_reasonable(self):
        """With a reversed edge, no shots fly off wildly."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_reversed_edge_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert 5.0 < result["B"].x < 15.0
        assert 15.0 < result["C"].x < 25.0

        for from_n, to_n in [("A", "B"), ("B", "C"), ("C", "D")]:
            eff = (result[to_n] - result[from_n]).length
            assert eff < 20.0, f"Shot {from_n}->{to_n}: {eff:.1f} m is too long"

    def test_all_stations_present_in_result(self):
        """Every station must appear in the output."""
        network = _make_two_anchor_traverse(misclosure=Vector3D(1, 1, 0))
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert set(result.keys()) == set(network.stations.keys())

    def test_side_branch_station_is_adjusted(self):
        """Spur station E must also be corrected."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_with_spur(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        e_original = network.stations["E"]
        assert (result["E"] - e_original).length > 1e-9, "E should move"

    def test_side_branch_inherits_branch_point_correction(self):
        """E branches from B, so its correction equals B's correction.

        In the least-squares solve, E has only one equation (B->E),
        so E = solved_B + be_delta.  The correction E - E_original
        equals B - B_original.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_with_spur(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        b_corr = result["B"] - network.stations["B"]
        e_corr = result["E"] - network.stations["E"]

        assert b_corr.length > 1e-9
        assert e_corr.x == pytest.approx(b_corr.x, abs=1e-9)
        assert e_corr.y == pytest.approx(b_corr.y, abs=1e-9)
        assert e_corr.z == pytest.approx(b_corr.z, abs=1e-9)

    # -- closure tests -------------------------------------------------------

    def test_perfect_closure_at_anchors(self):
        """Both anchors must be at their exact GPS positions."""
        error = Vector3D(0.3, 0.1, -0.05)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["A"] == network.stations["A"]
        assert result["D"].x == pytest.approx(30.0, abs=1e-9)
        assert result["D"].y == pytest.approx(0.0, abs=1e-9)
        assert result["D"].z == pytest.approx(0.0, abs=1e-9)

    def test_perfect_closure_unequal_shots(self):
        """Unequal-shot traverse: anchors at GPS."""
        error = Vector3D(0.5, -0.2, 0.1)
        network = _make_unequal_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["D"].x == pytest.approx(30.0, abs=1e-9)
        assert result["D"].y == pytest.approx(0.0, abs=1e-9)
        assert result["D"].z == pytest.approx(0.0, abs=1e-9)

    def test_last_shot_is_computed(self):
        """The last shot (C -> D) is computed through the solver.

        With 3 equal shots and 0.3 m misclosure, each shot absorbs
        0.1 m, so the effective C->D delta is (10.2, 0, 0).
        """
        error = Vector3D(0.3, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        effective_cd = result["D"] - result["C"]
        assert effective_cd.x == pytest.approx(10.2, abs=1e-6)
        assert effective_cd.y == pytest.approx(0.0, abs=1e-9)
        assert effective_cd.z == pytest.approx(0.0, abs=1e-9)

    # -- constraint validation tests -----------------------------------------

    def test_small_misclosure_within_length_limits(self):
        """With 1 % misclosure, all shots stay within 5 % length limit."""
        error = Vector3D(0.3, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for shot in network.shots:
            effective = result[shot.to_name] - result[shot.from_name]
            survey_len = shot.delta.length
            eff_len = effective.length
            ratio = abs(eff_len - survey_len) / survey_len
            assert ratio <= 0.05 + 1e-6, (
                f"Shot {shot.from_name}->{shot.to_name}: "
                f"length changed by {ratio * 100:.2f}%"
            )

    def test_3d_misclosure_within_limits(self):
        """3-D misclosure: all shots within limits."""
        error = Vector3D(0.2, -0.15, 0.1)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for shot in network.shots:
            effective = result[shot.to_name] - result[shot.from_name]
            survey_len = shot.delta.length
            eff_len = effective.length
            ratio = abs(eff_len - survey_len) / survey_len
            assert ratio <= 0.05 + 1e-6, (
                f"Shot {shot.from_name}->{shot.to_name}: "
                f"length changed by {ratio * 100:.2f}%"
            )

    def test_solver_is_deterministic(self):
        """Same input gives same output regardless of tolerance params.

        The least-squares solution is computed purely from the
        network geometry.  The tolerance params only affect
        post-solve validation warnings.
        """
        error = Vector3D(1.0, 0.5, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        result_a = ProportionalSolver(
            max_length_change=0.01, max_angle_change=0.01,
        ).adjust(network)
        result_b = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)

        for name in network.stations:
            assert result_a[name].x == pytest.approx(result_b[name].x, abs=1e-12)
            assert result_a[name].y == pytest.approx(result_b[name].y, abs=1e-12)
            assert result_a[name].z == pytest.approx(result_b[name].z, abs=1e-12)

    def test_default_limits_from_constants(self):
        """ProportionalSolver() uses the constants as defaults."""
        solver_default = ProportionalSolver()
        solver_explicit = ProportionalSolver(
            max_length_change=SOLVER_MAX_LENGTH_CHANGE,
            max_angle_change=SOLVER_MAX_HEADING_CHANGE,
        )

        error = Vector3D(1.0, 0.5, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        result_default = solver_default.adjust(network)
        result_explicit = solver_explicit.adjust(network)

        for name in network.stations:
            assert result_default[name].x == pytest.approx(
                result_explicit[name].x, abs=1e-12,
            )
            assert result_default[name].y == pytest.approx(
                result_explicit[name].y, abs=1e-12,
            )
            assert result_default[name].z == pytest.approx(
                result_explicit[name].z, abs=1e-12,
            )

    # -- three-anchor junction tests -----------------------------------------

    def test_three_anchor_junction_anchors_fixed(self):
        """All three anchors must remain at their GPS positions."""
        network = _make_three_anchor_junction()
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for name in ("A", "B", "C"):
            assert result[name] == network.stations[name], (
                f"Anchor {name} moved from GPS"
            )

    def test_three_anchor_junction_consistent(self):
        """Junction station X must satisfy all three anchor constraints.

        The solved X should be close to (10, 0, 0) and produce
        reasonable shots to all three anchors -- no wild shots.
        """
        network = _make_three_anchor_junction()
        solver = ProportionalSolver()
        result = solver.adjust(network)

        x = result["X"]
        # X should be near (10, 0, 0)
        assert 9.0 < x.x < 11.0, f"X.x = {x.x:.2f}, expected near 10"
        assert -1.0 < x.y < 1.0, f"X.y = {x.y:.2f}, expected near 0"

        # All shots from/to X should be reasonable length (near 10 m)
        for anchor_name, expected_len in [("A", 10.0), ("B", 10.0), ("C", 10.0)]:
            anchor = result[anchor_name]
            eff_len = (x - anchor).length
            assert 8.0 < eff_len < 12.0, (
                f"Shot X->{anchor_name}: effective length {eff_len:.2f} m, "
                f"expected near {expected_len}"
            )

    def test_three_anchor_junction_all_stations_present(self):
        """All stations including X must be in the result."""
        network = _make_three_anchor_junction()
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert set(result.keys()) == {"A", "B", "C", "X"}

    def test_three_anchor_junction_balanced(self):
        """The residuals to each anchor should be roughly balanced.

        With equal-weight least-squares, no single anchor should
        dominate the solution.
        """
        network = _make_three_anchor_junction()
        solver = ProportionalSolver()
        result = solver.adjust(network)

        x = result["X"]
        residuals = []
        for shot in network.shots:
            from_pos = result[shot.from_name]
            to_pos = result[shot.to_name]
            effective = to_pos - from_pos
            residual = effective - shot.delta
            residuals.append(residual.length)

        # No single residual should be dramatically larger than others
        max_residual = max(residuals)
        min_residual = min(residuals)
        assert max_residual < 3.0 * min_residual + 0.01, (
            f"Residuals are unbalanced: {residuals}"
        )


# ---------------------------------------------------------------------------
# SurveyNetwork
# ---------------------------------------------------------------------------


class TestSurveyNetwork:
    """Tests for SurveyNetwork."""

    def test_adjacency_is_undirected(self):
        network = _make_linear_network()
        adj = network.adjacency

        a_neighbors = {s.to_name for s in adj["A"]}
        b_neighbors = {s.to_name for s in adj["B"]}
        assert "B" in a_neighbors
        assert "A" in b_neighbors

    def test_adjacency_is_cached(self):
        network = _make_linear_network()
        adj1 = network.adjacency
        adj2 = network.adjacency
        assert adj1 is adj2
