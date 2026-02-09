# -*- coding: utf-8 -*-
"""Proportional traverse adjustment solver.

When multiple anchors exist, multi-anchor BFS creates mixed-origin
positions with a visible seam where the two propagation fronts meet.
For each anchor pair (A, B) the solver re-propagates the **entire**
network from A using measurement deltas, computes the misclosure at B,
then corrects **every** station by
``-d_A / (d_A + d_B) * misclosure`` where d_A and d_B are the
graph-distances (cumulative shot length) to each anchor.  This
distributes the error smoothly across the whole network — including
side branches — with no seam.

Algorithm
---------
1. Build an undirected adjacency graph from the network shots.
2. For each connected anchor pair, re-propagate the full network from
   one anchor, compute graph distances from both anchors, and apply a
   distance-weighted correction to every reachable station.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections import deque
from itertools import combinations

from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import ZERO
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full-network re-propagation helpers
# ---------------------------------------------------------------------------


def _bfs_propagate(
    start: str,
    start_pos: Vector3D,
    adj: dict[str, list[NetworkShot]],
) -> tuple[dict[str, Vector3D], dict[str, float]]:
    """BFS from *start*, accumulating positions and graph-distances.

    Positions are computed by summing measurement deltas from *start_pos*.
    Distances are cumulative shot lengths (used as interpolation weights).

    Args:
        start: Starting station name.
        start_pos: Known position of *start*.
        adj: Undirected adjacency list with measurement deltas.

    Returns:
        ``(positions, distances)`` dictionaries keyed by station name.
    """
    positions: dict[str, Vector3D] = {start: start_pos}
    distances: dict[str, float] = {start: 0.0}
    queue: deque[str] = deque([start])

    while queue:
        current = queue.popleft()
        for shot in adj.get(current, []):
            neighbor = shot.to_name
            if neighbor in positions:
                continue
            positions[neighbor] = positions[current] + shot.delta
            distances[neighbor] = distances[current] + shot.distance
            queue.append(neighbor)

    return positions, distances


def _bfs_distances(
    start: str,
    adj: dict[str, list[NetworkShot]],
) -> dict[str, float]:
    """BFS from *start*, returning cumulative shot-length distances only.

    Lighter version of :func:`_bfs_propagate` when positions are not needed.
    """
    distances: dict[str, float] = {start: 0.0}
    queue: deque[str] = deque([start])

    while queue:
        current = queue.popleft()
        for shot in adj.get(current, []):
            neighbor = shot.to_name
            if neighbor in distances:
                continue
            distances[neighbor] = distances[current] + shot.distance
            queue.append(neighbor)

    return distances


# ---------------------------------------------------------------------------
# Polar helpers — work directly with survey compass heading & inclination
# ---------------------------------------------------------------------------

_MIN_ANGLE_TOL = math.radians(2.0)  # minimum angular tolerance (avoids 0 for small headings)


def _to_polar(
    dx: float, dy: float, dz: float,
) -> tuple[float, float, float]:
    """Cartesian (easting, northing, elevation) → (length, bearing, inclination).

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
    """(length, bearing_rad, inclination_rad) → cartesian delta."""
    horiz = length * math.cos(inclination)
    return Vector3D(
        horiz * math.sin(bearing),
        horiz * math.cos(bearing),
        length * math.sin(inclination),
    )


def _positive_bearing(b: float) -> float:
    """Normalise bearing to ``[0, 2π)``."""
    b = b % (2.0 * math.pi)
    if b < 0:
        b += 2.0 * math.pi
    return b


def _clamp_bearing(
    new_b: float, orig_b: float, max_frac: float,
) -> float:
    """Clamp *new_b* so it stays within ±*max_frac* of *orig_b*.

    Tolerance is ``max_frac × compass_reading`` (in [0, 360°]), with a
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
    """Clamp *new_i* so it stays within ±*max_frac* of |*orig_i*|.

    Floor of :data:`_MIN_ANGLE_TOL` is applied for nearly-horizontal
    shots.
    """
    tol = max(max_frac * abs(orig_i), _MIN_ANGLE_TOL)
    diff = new_i - orig_i
    if abs(diff) <= tol:
        return new_i
    return orig_i + math.copysign(tol, diff)


# ---------------------------------------------------------------------------
# Per-shot clamped re-propagation
# ---------------------------------------------------------------------------


def _clamped_propagate(
    start: str,
    start_pos: Vector3D,
    adj: dict[str, list[NetworkShot]],
    original_shots: list[NetworkShot],
    misclosure: Vector3D,
    dist_a: dict[str, float],
    dist_b: dict[str, float],
    max_length_frac: float,
    max_angle_frac: float,
) -> dict[str, Vector3D]:
    """BFS from *start* with **per-shot** polar clamping.

    Instead of applying a single scaled misclosure vector to every
    position, each shot is individually corrected and then clamped in
    polar coordinates (survey length, compass heading, inclination) so
    that no single measurement deviates from the original survey by
    more than the given tolerances.

    Args:
        start: Origin anchor station.
        start_pos: Known position of *start*.
        adj: Undirected adjacency list.
        original_shots: The original (forward-direction) shots.
        misclosure: Total misclosure vector for this anchor pair.
        dist_a: Graph-distances from the origin anchor.
        dist_b: Graph-distances from the far anchor.
        max_length_frac: E.g. ``0.05`` for 5 %.
        max_angle_frac: E.g. ``0.15`` for 15 %.

    Returns:
        Dictionary of station positions after clamped correction.
    """
    # Fast lookup: for every directed edge, find the *original* shot
    # (the one whose polar values represent the actual survey reading).
    orig_lookup: dict[tuple[str, str], NetworkShot] = {}
    for shot in original_shots:
        orig_lookup[(shot.from_name, shot.to_name)] = shot
        orig_lookup[(shot.to_name, shot.from_name)] = shot

    positions: dict[str, Vector3D] = {start: start_pos}
    queue: deque[str] = deque([start])

    while queue:
        current = queue.popleft()
        for adj_shot in adj.get(current, []):
            neighbor = adj_shot.to_name
            if neighbor in positions:
                continue

            # --- ideal proportional correction for this edge ---------------
            d_a_cur = dist_a.get(current, 0.0)
            d_b_cur = dist_b.get(current, 0.0)
            d_a_nbr = dist_a.get(neighbor, 0.0)
            d_b_nbr = dist_b.get(neighbor, 0.0)
            t_cur = d_a_cur + d_b_cur
            t_nbr = d_a_nbr + d_b_nbr
            f_cur = d_a_cur / t_cur if t_cur > 0 else 0.0
            f_nbr = d_a_nbr / t_nbr if t_nbr > 0 else 0.0
            delta_f = f_nbr - f_cur

            correction = Vector3D(
                delta_f * misclosure.x,
                delta_f * misclosure.y,
                delta_f * misclosure.z,
            )

            # --- look up the original survey measurement -------------------
            orig_shot = orig_lookup.get((current, neighbor))
            if orig_shot is None:
                # Fallback: no clamping possible, use adjacency delta.
                positions[neighbor] = positions[current] + adj_shot.delta
                queue.append(neighbor)
                continue

            is_reversed = orig_shot.from_name != current

            # Work in the *original survey direction* for polar clamping.
            if is_reversed:
                survey_delta = -orig_shot.delta
                correction = -correction
            else:
                survey_delta = orig_shot.delta

            corrected_delta = survey_delta - correction

            # --- decompose into polar (length, heading, inclination) -------
            o_len, o_brg, o_inc = _to_polar(
                survey_delta.x, survey_delta.y, survey_delta.z,
            )
            n_len, n_brg, n_inc = _to_polar(
                corrected_delta.x, corrected_delta.y, corrected_delta.z,
            )

            if o_len < 1e-9:
                # Zero-length shot — nothing useful to clamp.
                positions[neighbor] = positions[current] + adj_shot.delta
                queue.append(neighbor)
                continue

            # --- clamp each component against the survey reading -----------
            c_len = max(
                o_len * (1.0 - max_length_frac),
                min(n_len, o_len * (1.0 + max_length_frac)),
            )
            c_brg = _clamp_bearing(n_brg, o_brg, max_angle_frac)
            c_inc = _clamp_inclination(n_inc, o_inc, max_angle_frac)

            clamped = _from_polar(c_len, c_brg, c_inc)

            # Convert back to BFS traversal direction.
            if is_reversed:
                clamped = -clamped

            positions[neighbor] = positions[current] + clamped
            queue.append(neighbor)

    return positions


# ---------------------------------------------------------------------------
# Proportional solver
# ---------------------------------------------------------------------------


class ProportionalSolver(SurveyAdjuster):
    """Proportional traverse adjustment with per-shot polar clamping.

    For each connected pair of anchor stations the solver:

    1. Re-propagates the **entire** network from anchor A using
       measurement deltas to compute the misclosure at anchor B.
    2. Re-propagates again with per-shot clamped corrections: each
       shot's proportional share of the misclosure is decomposed
       into changes to the **survey compass heading**, inclination,
       and tape length, and each component is individually clamped
       to stay within the configured tolerance of the **original
       survey reading**.

    This guarantees that no single shot's effective compass heading
    or length ever deviates from the original survey by more than
    the allowed percentage, while still distributing as much of the
    traverse error as the limits permit.
    """

    def __init__(
        self,
        max_length_change: float = 0.05,
        max_angle_change: float = 0.15,
    ) -> None:
        """Create a solver with per-shot survey-measurement limits.

        Args:
            max_length_change: Maximum relative length change per shot
                (``0.05`` = 5 %).
            max_angle_change: Maximum relative change to the compass
                heading and inclination per shot (``0.15`` = 15 % of
                the original survey reading).
        """
        self._max_length_change = max_length_change
        self._max_angle_change = max_angle_change

    @property
    def name(self) -> str:
        return "ProportionalSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        """Adjust station coordinates via per-shot clamped correction.

        For each connected anchor pair (A, B):

        1. BFS-propagate from A (unclamped) to measure the misclosure.
        2. BFS-propagate from A **again**, this time applying a
           per-shot proportional correction that is clamped in polar
           coordinates so that every shot's compass heading and length
           stay within the configured tolerance of the original survey.
        """
        has_traverses = len(network.anchors) >= 2

        if not has_traverses:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        result: dict[str, Vector3D] = dict(network.stations)

        traverse_positions: dict[str, list[Vector3D]] = defaultdict(list)
        traverse_count = 0
        adj = network.adjacency

        for anchor_a, anchor_b in combinations(sorted(network.anchors), 2):
            # 1. Unclamped propagation to measure misclosure.
            propagated, dist_a = _bfs_propagate(
                anchor_a, network.stations[anchor_a], adj,
            )
            if anchor_b not in propagated:
                continue

            misclosure = propagated[anchor_b] - network.stations[anchor_b]
            if misclosure.length < 1e-9:
                continue

            dist_b = _bfs_distances(anchor_b, adj)

            logger.debug(
                "Traverse %s -> %s: misclosure=%.3f m "
                "(dx=%.3f, dy=%.3f, dz=%.3f)",
                anchor_a, anchor_b, misclosure.length,
                misclosure.x, misclosure.y, misclosure.z,
            )

            # 2. Clamped re-propagation — each shot individually
            #    limited to ±5 % length / ±15 % heading.
            corrected = _clamped_propagate(
                anchor_a, network.stations[anchor_a],
                adj, network.shots, misclosure,
                dist_a, dist_b,
                self._max_length_change,
                self._max_angle_change,
            )

            for name, pos in corrected.items():
                if name in network.anchors:
                    continue
                traverse_positions[name].append(pos)

            traverse_count += 1

        # Average when multiple anchor pairs contribute.
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

        logger.info(
            "Adjusted %d station(s) via %d traverse(s)",
            traverse_adjusted_count, traverse_count,
        )
        return result
