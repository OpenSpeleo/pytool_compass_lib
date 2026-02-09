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
    adjustment (inheriting the correction from its branch point B).
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
    Total = 30 m, same as the equal-length helpers.

    With uniform distribution each shot gets ``misclosure / 3``
    regardless of length, unlike distance-weighted which would
    give shorter shots a smaller share.

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

    The original shots are:
      A -> B  (forward, delta = (10, 0, 0))
      C -> B  (REVERSE, delta = (-10, 0, 0))
      C -> D  (forward, delta = (10, 0, 0) + misclosure)

    The BFS path A -> B -> C -> D traverses the middle edge B -> C,
    but the original survey measured it as C -> B.  The solver must
    handle this reversed direction correctly.

    ::

        A ----> B <---- C ----> D
        (anchor)  reversed shot  (anchor)
    """
    a = Vector3D(0, 0, 0)
    d = Vector3D(30, 0, 0)

    ab_delta = Vector3D(10, 0, 0)
    # Original shot goes C -> B (heading west, delta = (-10, 0, 0))
    cb_delta = Vector3D(-10, 0, 0)
    cd_delta = Vector3D(10, 0, 0) + misclosure

    b = a + ab_delta  # (10, 0, 0)
    c = d - cd_delta  # (20, 0, 0) - misclosure

    shots = [
        NetworkShot(from_name="A", to_name="B", delta=ab_delta, distance=10.0),
        # Note: direction is C -> B, NOT B -> C
        NetworkShot(from_name="C", to_name="B", delta=cb_delta, distance=10.0),
        NetworkShot(from_name="C", to_name="D", delta=cd_delta, distance=cd_delta.length),
    ]

    return SurveyNetwork(
        stations={"A": a, "B": b, "C": c, "D": d},
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
    """Tests for ProportionalSolver uniform traverse adjustment."""

    def test_name(self):
        assert ProportionalSolver().name == "ProportionalSolver"

    def test_single_anchor_returns_unchanged(self):
        """With only one anchor, no traverse exists -- positions stay put."""
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
        """Both anchors must remain at their exact GPS coordinates.

        Every shot is computed through the solver with proper clamping.
        A final linear shift pins both anchors at their GPS positions
        without creating any implicit unclamped shots.
        """
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

        b_moved = (result["B"] - b_original).length > 1e-9
        c_moved = (result["C"] - c_original).length > 1e-9

        assert b_moved, "B should have been adjusted"
        assert c_moved, "C should have been adjusted"

    def test_correction_is_uniform(self):
        """Each shot gets an equal share of the misclosure.

        With 3 equal-length shots (10 m each) and misclosure (6, 0, 0):
          per-shot correction = (2, 0, 0)

        Forward-propagated positions from A:
          B_prop = A + ab = (10, 0, 0)
          C_prop = A + ab + bc = (20, 0, 0)

        Corrected positions (each shot absorbs 2 m):
          B_corrected = (10, 0, 0) - 1 * (2, 0, 0) = (8, 0, 0)
          C_corrected = (20, 0, 0) - 2 * (2, 0, 0) = (16, 0, 0)

        Uses relaxed limits because the test misclosure (20 % of shot
        length) is intentionally large for easy arithmetic.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        )
        result = solver.adjust(network)

        assert result["B"].x == pytest.approx(8.0, abs=1e-9)
        assert result["C"].x == pytest.approx(16.0, abs=1e-9)

    def test_uniform_distribution_unequal_shots(self):
        """With unequal-length shots, uniform distribution gives each
        shot the same correction regardless of its length.

        Shots: A->B = 5 m, B->C = 10 m, C->D = 15 m + misclosure.
        Misclosure = (3, 0, 0), so per-shot correction = (1, 0, 0).

        Forward-propagated from A:
          B = (5, 0, 0)
          C = (15, 0, 0)
          D_computed = (33, 0, 0)

        Corrected:
          B = 5 - 1*1 = 4
          C = 15 - 2*1 = 13
          D = 33 - 3*1 = 30  (matches anchor D)

        With distance-weighted distribution the results would be:
          B = 5 - (5/30)*3 = 4.5
          C = 15 - (15/30)*3 = 13.5
        so the test distinguishes uniform from proportional.
        """
        error = Vector3D(3.0, 0.0, 0.0)
        network = _make_unequal_traverse(misclosure=error)
        solver = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        )
        result = solver.adjust(network)

        assert result["B"].x == pytest.approx(4.0, abs=1e-9)
        assert result["C"].x == pytest.approx(13.0, abs=1e-9)

    def test_reversed_edge_gives_same_result(self):
        """A reversed middle shot must produce the same correction as
        a forward middle shot.

        The path A -> B -> C -> D is the same geometry regardless of
        whether the original survey measured B -> C or C -> B.  The
        solver must handle the reversed direction transparently.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        forward_net = _make_two_anchor_traverse(misclosure=error)
        reversed_net = _make_reversed_edge_traverse(misclosure=error)

        solver = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        )
        fwd_result = solver.adjust(forward_net)
        rev_result = solver.adjust(reversed_net)

        for name in ("B", "C"):
            assert rev_result[name].x == pytest.approx(
                fwd_result[name].x, abs=1e-6,
            ), f"{name}: reversed edge gave different x"
            assert rev_result[name].y == pytest.approx(
                fwd_result[name].y, abs=1e-6,
            ), f"{name}: reversed edge gave different y"
            assert rev_result[name].z == pytest.approx(
                fwd_result[name].z, abs=1e-6,
            ), f"{name}: reversed edge gave different z"

    def test_reversed_edge_stations_are_reasonable(self):
        """With a reversed edge, station positions must remain in the
        correct neighborhood -- no shots flying off 100x too long.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_reversed_edge_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        # B should be near (10, 0, 0), C near (20, 0, 0)
        assert 5.0 < result["B"].x < 15.0, (
            f"B.x = {result['B'].x:.1f}, expected near 10"
        )
        assert 15.0 < result["C"].x < 25.0, (
            f"C.x = {result['C'].x:.1f}, expected near 20"
        )

        # Every effective shot must be less than 2x the survey length
        for from_n, to_n in [("A", "B"), ("B", "C"), ("C", "D")]:
            eff = (result[to_n] - result[from_n]).length
            assert eff < 20.0, (
                f"Shot {from_n}->{to_n}: effective length {eff:.1f} m "
                f"is unreasonably large"
            )

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

    def test_side_branch_inherits_branch_point_correction(self):
        """E branches from B, so its correction equals B's correction.

        With the uniform algorithm, E is re-propagated from B's
        corrected position using the original B->E delta.  Therefore
        E's shift from its original position is identical to B's.
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_with_spur(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        b_correction = result["B"] - network.stations["B"]
        e_correction = result["E"] - network.stations["E"]

        # Both should be non-zero
        assert b_correction.length > 1e-9
        assert e_correction.length > 1e-9

        # E inherits B's correction exactly
        assert e_correction.x == pytest.approx(b_correction.x, abs=1e-9)
        assert e_correction.y == pytest.approx(b_correction.y, abs=1e-9)
        assert e_correction.z == pytest.approx(b_correction.z, abs=1e-9)

    # -- closure tests -------------------------------------------------------

    def test_perfect_closure_at_anchor_b(self):
        """Both anchors are pinned at their exact GPS coordinates.

        The solver computes all shots with clamping, then a final
        linear shift distributes the tiny residual to pin both
        anchors exactly.
        """
        error = Vector3D(0.3, 0.1, -0.05)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        # Both anchors must be at their exact GPS positions.
        assert result["A"] == network.stations["A"]
        assert result["D"].x == pytest.approx(30.0, abs=1e-9)
        assert result["D"].y == pytest.approx(0.0, abs=1e-9)
        assert result["D"].z == pytest.approx(0.0, abs=1e-9)

        # The path A -> B -> C -> D should form a continuous traverse
        # where each segment uses roughly the original measurement
        path_length = (
            (result["B"] - result["A"]).length
            + (result["C"] - result["B"]).length
            + (result["D"] - result["C"]).length
        )
        # Total path length should be close to 30 m (original traverse)
        assert path_length == pytest.approx(30.0, abs=0.5)

    def test_perfect_closure_unequal_shots(self):
        """Traverse with unequal shots closes exactly at anchor B."""
        error = Vector3D(0.5, -0.2, 0.1)
        network = _make_unequal_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        assert result["D"].x == pytest.approx(30.0, abs=1e-9)
        assert result["D"].y == pytest.approx(0.0, abs=1e-9)
        assert result["D"].z == pytest.approx(0.0, abs=1e-9)

    # -- clamping tests ------------------------------------------------------

    def test_clamping_limits_length_change(self):
        """With default limits (5 % length), each shot's effective
        length stays within +/-5 % of the original survey measurement.

        Uses a realistic misclosure (3 % of traverse length) that the
        solver can fully absorb.
        """
        error = Vector3D(1.0, 0.0, 0.0)
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

    def test_clamping_reduces_first_station_correction(self):
        """For the first interior station, clamped correction is
        smaller than unclamped (clamping limits the first shot).
        """
        error = Vector3D(6.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        unclamped = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)
        clamped = ProportionalSolver().adjust(network)

        unclamped_shift = (unclamped["B"] - network.stations["B"]).length
        clamped_shift = (clamped["B"] - network.stations["B"]).length
        assert clamped_shift < unclamped_shift, (
            f"B: clamped shift ({clamped_shift:.3f}) should be "
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

    def test_clamping_with_off_axis_misclosure(self):
        """Off-axis misclosure: per-shot polar clamping must keep
        every shot's heading and length close to the survey.

        Uses a realistic off-axis misclosure (small relative to
        traverse length) so the solver can fully absorb it.
        """
        error = Vector3D(0.3, 0.5, 0.0)
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

    def test_all_shots_clamped_with_reasonable_misclosure(self):
        """With a moderate misclosure (within solver capacity), ALL
        shots -- including the last -- respect the length and heading
        constraints.

        Uses 1 % misclosure on a 30 m traverse (0.3 m total error,
        0.1 m per shot = 1 % of 10 m, well within 5 % limit).
        """
        error = Vector3D(0.3, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()  # default 5 % / 15 %
        result = solver.adjust(network)

        shot_pairs = [
            ("A", "B", network.shots[0].delta),
            ("B", "C", network.shots[1].delta),
            ("C", "D", network.shots[2].delta),
        ]
        for from_n, to_n, survey_delta in shot_pairs:
            effective = result[to_n] - result[from_n]
            survey_len = survey_delta.length
            eff_len = effective.length

            length_ratio = abs(eff_len - survey_len) / survey_len
            assert length_ratio <= 0.05 + 1e-6, (
                f"Shot {from_n}->{to_n}: "
                f"length changed by {length_ratio * 100:.2f}%"
            )

    def test_last_shot_is_computed(self):
        """The last shot (C -> D) must be explicitly computed through
        the solver, not just 'connect the dot' to anchor D.

        With a small unclamped misclosure, the effective last shot
        should differ from the raw measurement by exactly the per-shot
        uniform correction.
        """
        error = Vector3D(0.3, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        )
        result = solver.adjust(network)

        # With uniform distribution (3 shots, 0.3 m misclosure):
        # per-shot correction = 0.1 m
        # Last shot delta = (10.3, 0, 0) - (0.1, 0, 0) = (10.2, 0, 0)
        effective_cd = result["D"] - result["C"]
        assert effective_cd.x == pytest.approx(10.2, abs=1e-6)
        assert effective_cd.y == pytest.approx(0.0, abs=1e-9)
        assert effective_cd.z == pytest.approx(0.0, abs=1e-9)

    def test_anchor_adjacent_shots_respect_length_limit(self):
        """The first shot (from anchor A) and last shot (to anchor D)
        must both respect the 5 % length constraint.

        This verifies the multi-pass solver does not let anchor-
        adjacent shots silently absorb the entire residual.
        """
        # 1 % misclosure — easily within solver capacity.
        error = Vector3D(0.3, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()  # default 5 % / 15 %
        result = solver.adjust(network)

        # First shot (A -> B): anchor A at origin
        first_eff = result["B"] - result["A"]
        first_survey_len = network.shots[0].delta.length  # 10.0
        first_ratio = abs(first_eff.length - first_survey_len) / first_survey_len
        assert first_ratio <= 0.05 + 1e-6, (
            f"First shot A->B: length changed by {first_ratio * 100:.2f}%"
        )

        # Last shot (C -> D): anchor D at (30, 0, 0)
        last_eff = result["D"] - result["C"]
        last_survey_len = network.shots[2].delta.length  # ~10.3
        last_ratio = abs(last_eff.length - last_survey_len) / last_survey_len
        assert last_ratio <= 0.05 + 1e-6, (
            f"Last shot C->D: length changed by {last_ratio * 100:.2f}%"
        )

    def test_anchor_adjacent_shots_with_3d_misclosure(self):
        """3-D misclosure: all shots including anchor-adjacent ones
        must stay within the 5 % length / 15 % heading limits.
        """
        # Misclosure with all three components.
        error = Vector3D(0.2, -0.15, 0.1)
        network = _make_two_anchor_traverse(misclosure=error)
        solver = ProportionalSolver()
        result = solver.adjust(network)

        for i, (from_n, to_n) in enumerate(
            [("A", "B"), ("B", "C"), ("C", "D")],
        ):
            effective = result[to_n] - result[from_n]
            survey_len = network.shots[i].delta.length
            eff_len = effective.length

            length_ratio = abs(eff_len - survey_len) / survey_len
            assert length_ratio <= 0.05 + 1e-6, (
                f"Shot {from_n}->{to_n}: "
                f"length changed by {length_ratio * 100:.2f}%"
            )

    def test_custom_limits(self):
        """Solver respects custom max_length_change / max_angle_change.

        With a realistic misclosure, tighter clamping limits produce
        smaller per-shot corrections before the final linear shift.
        """
        error = Vector3D(1.0, 0.0, 0.0)
        network = _make_two_anchor_traverse(misclosure=error)

        tight = ProportionalSolver(
            max_length_change=0.01, max_angle_change=0.05,
        ).adjust(network)
        loose = ProportionalSolver(
            max_length_change=10.0, max_angle_change=10.0,
        ).adjust(network)

        # With loose limits every shot absorbs its full uniform share,
        # so the solver residual is zero and the linear shift is zero.
        # With tight limits some correction is clamped, producing a
        # non-zero residual that the linear shift must distribute.
        # The results should differ (tight can't absorb as much
        # per-shot), but both should produce valid positions.
        any_differ = False
        for name in ("B", "C"):
            if (tight[name] - loose[name]).length > 1e-6:
                any_differ = True
        assert any_differ, "Tight and loose limits should produce different results"

    def test_default_limits_from_constants(self):
        """ProportionalSolver() with no arguments uses the constants
        SOLVER_MAX_LENGTH_CHANGE and SOLVER_MAX_HEADING_CHANGE.
        """
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
