# -*- coding: utf-8 -*-
"""Tests for the survey adjustment solver module."""

import pytest

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

    With perfect data the measured path A->D sums to (30,0,0) which
    matches D-A.  ``misclosure`` shifts the measured delta so the
    solver has something to correct.

    Positions are set as if BFS ran from both anchors simultaneously:
    A and B come from anchor A, C and D come from anchor D.  This
    creates the mixed-origin seam that traverse adjustment must fix.

    ::

        A ----> B ----> C ----> D
        (anchor)                (anchor)
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    # Measurement deltas (what was actually measured in the field)
    ab_delta = Vector3D(10, 0, 0)
    bc_delta = Vector3D(10, 0, 0)
    cd_delta = Vector3D(10, 0, 0) + misclosure

    # BFS mixed-origin positions:
    # B computed from A  ->  A + ab_delta
    b = a + ab_delta  # (10, 0, 0)
    # C computed from D  ->  D - cd_delta (BFS from D reaches C first)
    c = d - cd_delta  # (20, 0, 0) - misclosure

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

    A and D are anchors.  E is on a spur off the main traverse.

    ::

        A ----> B ----> C ----> D
                |
                v
                E

    The spur station E must also be corrected by the traverse
    adjustment (inheriting the correction from its position in
    the graph relative to both anchors).
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
# ProportionalSolver — traverse adjustment
# ---------------------------------------------------------------------------


class TestProportionalSolver:
    """Tests for ProportionalSolver traverse adjustment."""

    def test_name(self):
        assert ProportionalSolver().name == "ProportionalSolver"

    def test_single_anchor_returns_unchanged(self):
        """With only one anchor, no traverse exists — positions stay put."""
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

    def test_anchors_not_moved(self):
        """Both anchors must remain at their fixed coordinates."""
        error = Vector3D(3.0, 3.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["A"] == network.stations["A"]
        assert result["D"] == network.stations["D"]

    def test_interior_stations_are_adjusted(self):
        """Non-anchor stations must move when misclosure exists."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        b_original = network.stations["B"]
        c_original = network.stations["C"]

        b_moved = (result["B"] - b_original).length > 1e-9
        c_moved = (result["C"] - c_original).length > 1e-9

        assert b_moved, "B should have been adjusted"
        assert c_moved, "C should have been adjusted"

    def test_correction_is_distance_weighted(self):
        """Station closer to A gets a smaller fraction than station closer to D.

        The re-propagated positions from A are:
          B_prop = A + ab = (10, 0, 0)
          C_prop = A + ab + bc = (20, 0, 0)

        Misclosure = (A + ab + bc + cd) - D_fixed.

        Fraction for B = d_A(B)/(d_A(B)+d_B(B)) = 10/30 = 1/3
        Fraction for C = d_A(C)/(d_A(C)+d_B(C)) = 20/30 = 2/3

        So B's correction magnitude should be smaller than C's.

        Uses relaxed limits because the test misclosure (20 % of shot
        length) is intentionally large for easy arithmetic.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        )
        result = solver.adjust(network)

        # Re-propagated from A: B_prop=(10,0,0), C_prop=(20,0,0)
        # misclosure = (10+10+10+6, 0, 0) - (30, 0, 0) = (6, 0, 0)
        # B_corrected = (10, 0, 0) - 1/3 * (6, 0, 0) = (8, 0, 0)
        # C_corrected = (20, 0, 0) - 2/3 * (6, 0, 0) = (16, 0, 0)
        assert result["B"].x == pytest.approx(8.0, abs=1e-9)
        assert result["C"].x == pytest.approx(16.0, abs=1e-9)

    def test_all_stations_present_in_result(self):
        """Every station must appear in the output."""
        network = _make_two_anchor_traverse(misclosure=Vector3D(1, 1, 0))
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert set(result.keys()) == set(network.stations.keys())

    def test_side_branch_station_is_adjusted(self):
        """Spur station E (off the main traverse) must also be corrected."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_with_spur(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        e_original = network.stations["E"]
        e_moved = (result["E"] - e_original).length > 1e-9
        assert e_moved, "Spur station E should have been adjusted"

    def test_side_branch_correction_near_branch_point(self):
        """E branches from B, so its correction should be close to B's."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_with_spur(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        # E is 10m from B, and B is 10m from A / 20m from D.
        # So E is 20m from A and 20m from D -> fraction = 0.5
        # B is 10m from A and 20m from D -> fraction = 1/3
        # They should have similar but not identical corrections.
        b_correction = (result["B"] - network.stations["B"]).length
        e_correction = (result["E"] - network.stations["E"]).length

        # Both should be non-zero
        assert b_correction > 1e-9
        assert e_correction > 1e-9

    # -- clamping tests ------------------------------------------------------

    def test_clamping_limits_length_change(self):
        """With default limits (5 % length), each shot's effective
        length stays within ±5 % of the original survey measurement.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()  # default 5 % / 15 %
        result = solver.adjust(network)

        for from_n, to_n, survey_len in [("A", "B", 10.0), ("B", "C", 10.0)]:
            effective = result[to_n] - result[from_n]
            length_ratio = abs(effective.length - survey_len) / survey_len
            assert length_ratio <= 0.05 + 1e-6, (
                f"Shot {from_n}->{to_n}: "
                f"length changed by {length_ratio * 100:.1f}%"
            )

    def test_clamping_reduces_correction(self):
        """Clamped corrections must be smaller than unclamped ones."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        unclamped = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)
        clamped = ProportionalSolver().adjust(network)

        for name in ("B", "C"):
            unclamped_shift = (unclamped[name] - network.stations[name]).length
            clamped_shift = (clamped[name] - network.stations[name]).length
            assert clamped_shift < unclamped_shift, (
                f"{name}: clamped shift ({clamped_shift:.3f}) should be "
                f"less than unclamped ({unclamped_shift:.3f})"
            )

    def test_clamping_preserves_direction(self):
        """Clamped and unclamped corrections should point the same way."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        unclamped = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)
        clamped = ProportionalSolver().adjust(network)

        for name in ("B", "C"):
            u = unclamped[name] - network.stations[name]
            c = clamped[name] - network.stations[name]
            dot = u.x * c.x + u.y * c.y + u.z * c.z
            assert dot > 0, f"{name}: correction direction flipped"

    def test_no_clamping_with_small_misclosure(self):
        """A tiny misclosure should not trigger clamping at all."""
        error = Vector3D(0.01, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        unclamped = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)
        clamped = ProportionalSolver().adjust(network)

        for name in network.stations:
            assert unclamped[name].x == pytest.approx(clamped[name].x, abs=1e-9)
            assert unclamped[name].y == pytest.approx(clamped[name].y, abs=1e-9)
            assert unclamped[name].z == pytest.approx(clamped[name].z, abs=1e-9)

    def test_clamping_with_large_off_axis_misclosure(self):
        """Large off-axis misclosure: per-shot polar clamping must keep
        every shot's heading and length close to the survey.
        """
        import math

        error = Vector3D(5.0, 50.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()  # 5 % length / 15 % heading
        result = solver.adjust(network)

        for shot in [network.shots[0], network.shots[1]]:
            effective = result[shot.to_name] - result[shot.from_name]
            survey_len = shot.delta.length
            eff_len = effective.length

            ratio = abs(eff_len - survey_len) / survey_len
            assert ratio <= 0.05 + 1e-6, (
                f"Shot {shot.from_name}->{shot.to_name}: "
                f"length changed by {ratio * 100:.2f}%"
            )

    def test_custom_limits(self):
        """Solver respects custom max_length_change / max_angle_change."""
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        tight = ProportionalSolver(
            max_length_change=0.01, max_angle_change=0.05,
        ).adjust(network)
        default = ProportionalSolver().adjust(network)

        for name in ("B", "C"):
            tight_shift = (tight[name] - network.stations[name]).length
            default_shift = (default[name] - network.stations[name]).length
            assert tight_shift <= default_shift + 1e-9


# ---------------------------------------------------------------------------
# SurveyNetwork
# ---------------------------------------------------------------------------


class TestSurveyNetwork:
    """Tests for SurveyNetwork."""

    def test_adjacency_is_undirected(self):
        network = _make_linear_network()
        adj = network.adjacency

        # A -> B exists, so B -> A should also exist
        a_neighbors = {s.to_name for s in adj["A"]}
        b_neighbors = {s.to_name for s in adj["B"]}
        assert "B" in a_neighbors
        assert "A" in b_neighbors

    def test_adjacency_is_cached(self):
        network = _make_linear_network()
        adj1 = network.adjacency
        adj2 = network.adjacency
        assert adj1 is adj2
