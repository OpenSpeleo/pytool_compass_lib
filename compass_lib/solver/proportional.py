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
# Proportional solver
# ---------------------------------------------------------------------------


class ProportionalSolver(SurveyAdjuster):
    """Proportional traverse adjustment solver.

    For each connected pair of anchor stations the solver:

    1. Re-propagates the **entire** network from anchor A using
       measurement deltas (eliminates the mixed-origin seam created
       by multi-anchor BFS).
    2. Computes the misclosure at anchor B.
    3. Computes graph-distances d_A and d_B for every station.
    4. Corrects each station by ``-d_A / (d_A + d_B) * misclosure``.

    Stations near A barely move, stations near B get nearly the full
    correction, and side-branches interpolate naturally.
    """

    @property
    def name(self) -> str:
        return "ProportionalSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        """Adjust station coordinates via traverse correction.

        For each connected anchor pair (A, B):

        1. Re-propagate the **entire** network from A using measurement
           deltas.  This gives seam-free positions but accumulates all
           error at B.
        2. Compute the misclosure at B.
        3. For **every** station, compute graph-distances d_A and d_B
           (cumulative shot length to each anchor).
        4. Correct each station's position by
           ``-d_A / (d_A + d_B) * misclosure``.

        This distributes the error smoothly: stations near A barely
        move, stations near B get nearly the full correction, and
        side-branches interpolate naturally.
        """
        has_traverses = len(network.anchors) >= 2

        if not has_traverses:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        # Start with the raw BFS positions.
        result: dict[str, Vector3D] = dict(network.stations)

        # =================================================================
        # Traverse adjustment (full re-propagation)
        # =================================================================
        traverse_positions: dict[str, list[Vector3D]] = defaultdict(list)
        traverse_count = 0
        adj = network.adjacency

        for anchor_a, anchor_b in combinations(sorted(network.anchors), 2):
            # 1. Re-propagate every station from anchor A.
            propagated, dist_a = _bfs_propagate(
                anchor_a, network.stations[anchor_a], adj
            )

            # Skip if B is unreachable from A.
            if anchor_b not in propagated:
                continue

            # 2. Misclosure at B.
            misclosure = propagated[anchor_b] - network.stations[anchor_b]
            if misclosure.length < 1e-9:
                continue

            # 3. Graph-distances from B.
            dist_b = _bfs_distances(anchor_b, adj)

            logger.debug(
                "Traverse %s -> %s: misclosure=%.3f m (dx=%.3f, dy=%.3f, dz=%.3f)",
                anchor_a,
                anchor_b,
                misclosure.length,
                misclosure.x,
                misclosure.y,
                misclosure.z,
            )

            # 4. Distance-weighted correction for every station.
            for name, prop_pos in propagated.items():
                if name in network.anchors:
                    continue
                d_a = dist_a.get(name, 0.0)
                d_b = dist_b.get(name, 0.0)
                total_d = d_a + d_b
                if total_d <= 0:
                    continue
                fraction = d_a / total_d
                traverse_positions[name].append(prop_pos - fraction * misclosure)

            traverse_count += 1

        # Write traverse-adjusted positions (average when multiple pairs).
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
            traverse_adjusted_count,
            traverse_count,
        )
        return result
