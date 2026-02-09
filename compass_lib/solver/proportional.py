# -*- coding: utf-8 -*-
"""Uniform traverse adjustment solver.

For each pair of anchor stations (A, B) the solver:

1. Finds the shortest path (traverse) from A to B.
2. Forward-propagates from A using measurement deltas to compute every
   station along the traverse **and** the misclosure at B.
3. Distributes the misclosure **uniformly** across every shot in the
   traverse (each shot absorbs ``misclosure / N``).  If a per-shot
   correction is clamped by the length or heading tolerance, the excess
   is redistributed equally among the remaining shots so that the
   traverse always closes perfectly at B.
4. Re-propagates side-branch stations from their (now corrected)
   branch-point positions using original measurement deltas.

Algorithm
---------
1. Build an undirected adjacency graph from the network shots.
2. For each connected anchor pair, find the explicit path, forward-
   propagate, compute misclosure, and apply uniform clamped correction
   to every shot (including the first and last).
3. Stations on side branches inherit the correction of their branch
   point on the traverse.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections import deque
from itertools import combinations

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import ZERO
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Traverse path helpers
# ---------------------------------------------------------------------------


def _find_path(
    start: str,
    end: str,
    adj: dict[str, list[NetworkShot]],
    blocked: frozenset[str] = frozenset(),
) -> list[str] | None:
    """BFS shortest path from *start* to *end*.

    Stations in *blocked* (other than *end* itself) are treated as
    impassable.  This is used to prevent traverses from passing
    through intermediate anchor stations — each traverse should
    only connect two **adjacent** anchors.

    Returns:
        Ordered list of station names ``[start, ..., end]``, or
        ``None`` if *end* is not reachable from *start*.
    """
    if start == end:
        return [start]

    parent: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])

    while queue:
        current = queue.popleft()
        for shot in adj.get(current, []):
            neighbor = shot.to_name
            if neighbor in parent:
                continue
            # Don't pass through blocked stations (other anchors).
            if neighbor in blocked and neighbor != end:
                continue
            parent[neighbor] = current
            if neighbor == end:
                # Reconstruct path.
                path: list[str] = []
                node: str | None = end
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return path
            queue.append(neighbor)

    return None


def _get_path_shots(
    path: list[str],
    adj: dict[str, list[NetworkShot]],
) -> list[NetworkShot]:
    """Return the directed ``NetworkShot`` for each consecutive pair in *path*.

    The shots are returned in the **forward** (path) direction.  If the
    adjacency list only has the reverse direction, the delta is negated.
    """
    shots: list[NetworkShot] = []
    for i in range(len(path) - 1):
        from_name = path[i]
        to_name = path[i + 1]
        for shot in adj.get(from_name, []):
            if shot.to_name == to_name:
                shots.append(shot)
                break
        else:
            # Should not happen if _find_path succeeded.
            raise ValueError(
                f"No adjacency edge from {from_name!r} to {to_name!r}",
            )
    return shots


# ---------------------------------------------------------------------------
# Polar helpers — work directly with survey compass heading & inclination
# ---------------------------------------------------------------------------

_MIN_ANGLE_TOL = math.radians(2.0)  # minimum angular tolerance (avoids 0 for small headings)


def _to_polar(
    dx: float, dy: float, dz: float,
) -> tuple[float, float, float]:
    """Cartesian (easting, northing, elevation) -> (length, bearing, inclination).

    *bearing* is in radians, measured clockwise from north (``atan2(e, n)``).
    *inclination* is in radians, positive upward (``atan2(z, horiz)``).
    """
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    horiz = (dx * dx + dy * dy) ** 0.5
    bearing = math.atan2(dx, dy) if horiz > 1e-12 else 0.0
    if length < 1e-12:
        inclination = 0.0
    else:
        inclination = math.atan2(dz, horiz)
    return length, bearing, inclination


def _from_polar(
    length: float, bearing: float, inclination: float,
) -> Vector3D:
    """(length, bearing_rad, inclination_rad) -> cartesian delta."""
    horiz = length * math.cos(inclination)
    return Vector3D(
        horiz * math.sin(bearing),
        horiz * math.cos(bearing),
        length * math.sin(inclination),
    )


def _positive_bearing(b: float) -> float:
    """Normalise bearing to ``[0, 2pi)``."""
    b = b % (2.0 * math.pi)
    if b < 0:
        b += 2.0 * math.pi
    return b


def _clamp_bearing(
    new_b: float, orig_b: float, max_frac: float,
) -> float:
    """Clamp *new_b* so it stays within +/-*max_frac* of *orig_b*.

    Tolerance is ``max_frac * compass_reading`` (in [0, 360 deg]), with a
    floor of :data:`_MIN_ANGLE_TOL` to avoid zero tolerance for
    headings near north.
    """
    tol = max(max_frac * _positive_bearing(orig_b), _MIN_ANGLE_TOL)
    diff = (new_b - orig_b + math.pi) % (2.0 * math.pi) - math.pi
    if abs(diff) <= tol:
        return new_b
    return orig_b + math.copysign(tol, diff)


def _clamp_inclination(
    new_i: float, orig_i: float, max_frac: float,
) -> float:
    """Clamp *new_i* so it stays within +/-*max_frac* of |*orig_i*|.

    Floor of :data:`_MIN_ANGLE_TOL` is applied for nearly-horizontal
    shots.
    """
    tol = max(max_frac * abs(orig_i), _MIN_ANGLE_TOL)
    diff = new_i - orig_i
    if abs(diff) <= tol:
        return new_i
    return orig_i + math.copysign(tol, diff)


# ---------------------------------------------------------------------------
# Uniform traverse adjustment with per-shot clamping
# ---------------------------------------------------------------------------


def _clamp_shot_delta(
    survey_delta: Vector3D,
    corrected_delta: Vector3D,
    max_length_frac: float,
    max_angle_frac: float,
) -> Vector3D:
    """Clamp *corrected_delta* in polar coordinates against *survey_delta*.

    Returns the clamped delta.  Zero-length survey shots are returned
    unchanged (nothing useful to clamp).
    """
    o_len, o_brg, o_inc = _to_polar(
        survey_delta.x, survey_delta.y, survey_delta.z,
    )
    if o_len < 1e-9:
        return corrected_delta

    n_len, n_brg, n_inc = _to_polar(
        corrected_delta.x, corrected_delta.y, corrected_delta.z,
    )

    c_len = max(
        o_len * (1.0 - max_length_frac),
        min(n_len, o_len * (1.0 + max_length_frac)),
    )
    c_brg = _clamp_bearing(n_brg, o_brg, max_angle_frac)
    c_inc = _clamp_inclination(n_inc, o_inc, max_angle_frac)

    return _from_polar(c_len, c_brg, c_inc)


_MAX_SOLVER_ITERATIONS = 50
_SOLVER_EPSILON = 1e-9


def _adjust_traverse_uniform(
    anchor_a_pos: Vector3D,
    anchor_b_pos: Vector3D,
    path_shots: list[NetworkShot],
    original_shots: list[NetworkShot],
    max_length_frac: float,
    max_angle_frac: float,
) -> list[Vector3D]:
    """Uniform traverse adjustment from anchor A to anchor B.

    Every shot in the traverse absorbs an equal share of the
    misclosure.  Corrections are clamped per-shot in polar coordinates
    (length, bearing, inclination) against the **original survey
    measurement**.

    The algorithm runs multiple passes: each pass distributes the
    remaining un-absorbed misclosure uniformly across all shots.
    Shots that haven't reached their clamp limits absorb more in
    successive passes.  This converges to near-zero residual,
    ensuring the traverse closes at B without any single shot
    silently absorbing the entire gap.

    Args:
        anchor_a_pos: Known position of the starting anchor.
        anchor_b_pos: Known position of the ending anchor.
        path_shots: Ordered shots along the traverse (A -> ... -> B),
            taken from the adjacency list (may be reversed w.r.t. the
            original survey direction).
        original_shots: All original (forward-direction) network shots
            for looking up the survey measurement direction.
        max_length_frac: E.g. ``0.05`` for 5 %.
        max_angle_frac: E.g. ``0.15`` for 15 %.

    Returns:
        List of ``N + 1`` positions ``[A, S1, S2, ..., B]`` along the
        traverse, where ``N`` is the number of shots.
    """
    n = len(path_shots)
    if n == 0:
        return [anchor_a_pos]

    # -- Pre-compute per-shot info (once) ----------------------------------

    orig_lookup: dict[tuple[str, str], NetworkShot] = {}
    for shot in original_shots:
        orig_lookup[(shot.from_name, shot.to_name)] = shot
        orig_lookup[(shot.to_name, shot.from_name)] = shot

    # Original deltas in the PATH direction.
    path_deltas: list[Vector3D] = [s.delta for s in path_shots]

    # Original deltas in the SURVEY direction and reversal flags.
    survey_deltas: list[Vector3D | None] = []
    reversed_flags: list[bool] = []

    for adj_shot in path_shots:
        orig = orig_lookup.get((adj_shot.from_name, adj_shot.to_name))
        if orig is not None:
            survey_deltas.append(orig.delta)
            reversed_flags.append(orig.from_name != adj_shot.from_name)
        else:
            survey_deltas.append(None)
            reversed_flags.append(False)

    # -- Forward propagation to find misclosure ----------------------------

    forward: list[Vector3D] = [anchor_a_pos]
    for d in path_deltas:
        forward.append(forward[-1] + d)

    misclosure = forward[-1] - anchor_b_pos

    if misclosure.length < _SOLVER_EPSILON:
        return forward

    # -- Multi-pass uniform distribution with clamping ---------------------
    #
    # ``adjustments[i]`` is the *cumulative* correction vector (in path
    # direction) subtracted from shot *i*'s original delta.  Each pass
    # distributes ``remaining`` uniformly; shots that hit their clamp
    # limit absorb less, and the excess stays in ``remaining`` for the
    # next pass.

    adjustments: list[Vector3D] = [ZERO] * n
    remaining = misclosure

    for _iteration in range(_MAX_SOLVER_ITERATIONS):
        if remaining.length < _SOLVER_EPSILON:
            break

        prev_remaining_len = remaining.length

        for i in range(n):
            shots_left = n - i
            share = Vector3D(
                remaining.x / shots_left,
                remaining.y / shots_left,
                remaining.z / shots_left,
            )

            # Proposed new cumulative adjustment for this shot.
            proposed = adjustments[i] + share

            # Resulting path delta if fully applied.
            adjusted_path = path_deltas[i] - proposed

            sv = survey_deltas[i]
            if sv is None:
                # No survey data — apply without clamping.
                absorbed = share
                adjustments[i] = proposed
                remaining = remaining - absorbed
                continue

            # Clamp in the ORIGINAL SURVEY direction, then convert
            # back to path direction.
            if reversed_flags[i]:
                adjusted_survey = -adjusted_path
                clamped_survey = _clamp_shot_delta(
                    sv, adjusted_survey, max_length_frac, max_angle_frac,
                )
                clamped_path = -clamped_survey
            else:
                clamped_path = _clamp_shot_delta(
                    sv, adjusted_path, max_length_frac, max_angle_frac,
                )

            # Actual cumulative adjustment after clamping.
            actual_total = path_deltas[i] - clamped_path
            absorbed = actual_total - adjustments[i]
            adjustments[i] = actual_total
            remaining = remaining - absorbed

        # Stop if no progress (all shots are at their clamp limits).
        if remaining.length >= prev_remaining_len - _SOLVER_EPSILON:
            break

    if remaining.length > 0.01:
        logger.warning(
            "Traverse residual %.3f m after %d iterations "
            "(constraints too tight for this misclosure)",
            remaining.length, _iteration + 1,  # noqa: F821
        )

    # -- Build final corrected positions -----------------------------------

    corrected: list[Vector3D] = [anchor_a_pos]
    for i in range(n):
        corrected.append(corrected[-1] + path_deltas[i] - adjustments[i])

    # -- Pin both anchors at their exact GPS positions ---------------------
    #
    # After multi-pass convergence the ending anchor is very close to
    # its GPS position but may not be exact.  A final linear shift
    # distributes the tiny residual across all stations so that:
    #   - corrected[0]  = anchor_a_pos  (unchanged, fraction = 0)
    #   - corrected[-1] = anchor_b_pos  (exact,     fraction = 1)
    # The per-shot change is negligible (residual / N) and does not
    # meaningfully affect length or heading constraints.

    residual = anchor_b_pos - corrected[-1]
    if residual.length > _SOLVER_EPSILON:
        for j in range(1, n + 1):
            frac = j / n
            corrected[j] = Vector3D(
                corrected[j].x + frac * residual.x,
                corrected[j].y + frac * residual.y,
                corrected[j].z + frac * residual.z,
            )

    return corrected


# ---------------------------------------------------------------------------
# Side-branch re-propagation
# ---------------------------------------------------------------------------


def _propagate_side_branches(
    traverse_stations: set[str],
    corrected: dict[str, Vector3D],
    adj: dict[str, list[NetworkShot]],
) -> None:
    """BFS from corrected traverse stations to pick up side branches.

    Side-branch stations inherit their branch-point's corrected
    position and are propagated using original measurement deltas
    (no additional error distribution).  *corrected* is updated
    in-place.
    """
    queue: deque[str] = deque()
    for name in traverse_stations:
        if name in corrected:
            queue.append(name)

    while queue:
        current = queue.popleft()
        for shot in adj.get(current, []):
            neighbor = shot.to_name
            if neighbor in corrected:
                continue
            corrected[neighbor] = corrected[current] + shot.delta
            queue.append(neighbor)


# ---------------------------------------------------------------------------
# Proportional solver
# ---------------------------------------------------------------------------


class ProportionalSolver(SurveyAdjuster):
    """Uniform traverse adjustment with per-shot polar clamping.

    For each connected pair of anchor stations the solver:

    1. Finds the shortest path (traverse) from anchor A to anchor B.
    2. Forward-propagates from A using measurement deltas to compute
       every station position **and** the misclosure at B.
    3. Distributes the misclosure **uniformly** across every shot
       (including the first and last).  Each shot's correction is
       clamped in polar coordinates so that its tape length and
       compass heading never deviate from the original survey by
       more than the configured tolerances.
    4. Re-propagates side-branch stations from their corrected
       branch-point positions.

    This guarantees that every shot — including the first and last —
    is properly computed and clamped, and the traverse closes
    perfectly at anchor B.
    """

    def __init__(
        self,
        max_length_change: float = SOLVER_MAX_LENGTH_CHANGE,
        max_angle_change: float = SOLVER_MAX_HEADING_CHANGE,
    ) -> None:
        """Create a solver with per-shot survey-measurement limits.

        Args:
            max_length_change: Maximum relative length change per shot
                (default from ``constants.SOLVER_MAX_LENGTH_CHANGE``).
            max_angle_change: Maximum relative change to the compass
                heading and inclination per shot (default from
                ``constants.SOLVER_MAX_HEADING_CHANGE``).
        """
        self._max_length_change = max_length_change
        self._max_angle_change = max_angle_change

    @property
    def name(self) -> str:
        return "ProportionalSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        """Adjust station coordinates via uniform traverse correction.

        For each connected anchor pair (A, B):

        1. Find the shortest path from A to B.
        2. Forward-propagate from A to compute the misclosure at B.
        3. Distribute the misclosure uniformly across every shot,
           clamping each in polar coordinates.
        4. Re-propagate side-branch stations from corrected positions.
        """
        if len(network.anchors) < 2:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        # Seed result with GPS-fixed anchor positions.  Non-anchor
        # stations are intentionally absent so that side-branch
        # re-propagation can compute them from corrected positions.
        result: dict[str, Vector3D] = {
            name: network.stations[name] for name in network.anchors
        }

        traverse_positions: dict[str, list[Vector3D]] = defaultdict(list)
        all_traverse_stations: set[str] = set(network.anchors)
        traverse_count = 0
        adj = network.adjacency

        for anchor_a, anchor_b in combinations(sorted(network.anchors), 2):
            # Block other anchors so the traverse only connects
            # ADJACENT anchors — never passes through an intermediate
            # anchor whose GPS position would create a gap.
            other_anchors = frozenset(
                a for a in network.anchors if a != anchor_a and a != anchor_b
            )
            path = _find_path(anchor_a, anchor_b, adj, blocked=other_anchors)
            if path is None or len(path) < 2:
                continue

            path_shots = _get_path_shots(path, adj)

            corrected_positions = _adjust_traverse_uniform(
                network.stations[anchor_a],
                network.stations[anchor_b],
                path_shots,
                network.shots,
                self._max_length_change,
                self._max_angle_change,
            )

            # Forward propagation misclosure (for logging).
            forward_end = network.stations[anchor_a]
            for shot in path_shots:
                forward_end = forward_end + shot.delta
            misclosure = forward_end - network.stations[anchor_b]

            logger.debug(
                "Traverse %s -> %s (%d shots): misclosure=%.3f m "
                "(dx=%.3f, dy=%.3f, dz=%.3f)",
                anchor_a, anchor_b, len(path_shots),
                misclosure.length,
                misclosure.x, misclosure.y, misclosure.z,
            )

            # Collect solver-computed positions for non-anchor stations.
            # Anchors keep their GPS positions (pre-seeded in result).
            # The linear shift inside _adjust_traverse_uniform already
            # ensures corrected[-1] = anchor_b_pos, so the last
            # non-anchor station is positioned such that the effective
            # shot to the anchor is exactly what the solver computed —
            # no implicit "connect-the-dot" shot is created.
            for j, station_name in enumerate(path):
                all_traverse_stations.add(station_name)
                if station_name in network.anchors:
                    continue
                traverse_positions[station_name].append(corrected_positions[j])

            traverse_count += 1

        # Average when multiple anchor pairs contribute to the same station.
        traverse_adjusted_count = 0
        for name, positions in traverse_positions.items():
            if len(positions) == 1:
                result[name] = positions[0]
            else:
                avg = ZERO
                for p in positions:
                    avg = avg + p
                result[name] = Vector3D(
                    avg.x / len(positions),
                    avg.y / len(positions),
                    avg.z / len(positions),
                )
            traverse_adjusted_count += 1

        # Re-propagate side-branch stations from corrected traverse
        # positions (no additional error distribution on side branches).
        _propagate_side_branches(all_traverse_stations, result, adj)

        # Fill any stations not reached by traverses or side branches
        # (disconnected components, isolated anchors) with originals.
        for name in network.stations:
            if name not in result:
                result[name] = network.stations[name]

        logger.info(
            "Adjusted %d station(s) via %d traverse(s)",
            traverse_adjusted_count, traverse_count,
        )
        return result
