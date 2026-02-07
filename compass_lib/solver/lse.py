# -*- coding: utf-8 -*-
"""Traverse-quality weighted least-squares solver (Larry Fish method).

Weights each shot by the quality of the traverse it belongs to.
Shots on good traverses (small misclosure per shot) get **high**
weight and are protected.  Shots on bad traverses (large misclosure
per shot) get **low** weight and absorb the error.

This prevents blunders in bad traverses from contaminating good
data -- the core insight from Larry Fish's articles on loop closure.
"""

from __future__ import annotations

import logging
from collections import deque
from itertools import combinations

import numpy as np

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


def _find_path(
    start: str,
    end: str,
    adj: dict[str, list[NetworkShot]],
    blocked: frozenset[str] = frozenset(),
) -> list[str] | None:
    """BFS shortest path, avoiding blocked stations."""
    if start == end:
        return [start]
    parent: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])
    while queue:
        current = queue.popleft()
        for shot in adj.get(current, []):
            n = shot.to_name
            if n in parent or (n in blocked and n != end):
                continue
            parent[n] = current
            if n == end:
                path: list[str] = []
                node: str | None = end
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return path
            queue.append(n)
    return None


def _solve_lse(
    network: SurveyNetwork,
    max_length_frac: float,
    max_angle_frac: float,
) -> dict[str, Vector3D]:
    """Traverse-quality weighted lstsq."""
    # Filter out anchors that don't exist in stations (orphan link
    # stations, already warned about upstream).
    anchors = network.anchors & set(network.stations.keys())
    non_anchors = sorted(set(network.stations.keys()) - anchors)

    if not non_anchors:
        return dict(network.stations)

    m = len(non_anchors)
    station_to_idx = {name: i for i, name in enumerate(non_anchors)}
    anchor_pos: dict[str, Vector3D] = {name: network.stations[name] for name in anchors}
    adj = network.adjacency

    # -- Centre coordinates for numerical stability ---------------------------
    # UTM coordinates can be O(10^5..10^6).  Subtracting a reference
    # point keeps all lstsq values near zero, avoiding precision loss.
    _all_pos = list(anchor_pos.values())
    origin = Vector3D(
        sum(p.x for p in _all_pos) / len(_all_pos),
        sum(p.y for p in _all_pos) / len(_all_pos),
        sum(p.z for p in _all_pos) / len(_all_pos),
    )
    anchor_pos_c = {n: p - origin for n, p in anchor_pos.items()}

    # -- Compute traverse quality for each shot ----------------------------
    #
    # For each pair of adjacent anchors, find the traverse path and
    # compute misclosure per shot.  Each shot gets the quality score
    # of the BEST traverse it belongs to (lowest misclosure/shot).

    shot_key_to_quality: dict[tuple[str, str], float] = {}

    # Build a directed edge lookup for O(1) path-walk.
    edge_delta: dict[tuple[str, str], Vector3D] = {}
    for shot in network.shots:
        edge_delta[(shot.from_name, shot.to_name)] = shot.delta
        edge_delta[(shot.to_name, shot.from_name)] = -shot.delta

    anchor_list = sorted(anchors)
    all_anchors_frozen = frozenset(anchors)

    for a, b in combinations(anchor_list, 2):
        other = all_anchors_frozen - {a, b}
        path = _find_path(a, b, adj, blocked=other)
        if path is None or len(path) < 2:
            continue

        # Forward-propagate to compute misclosure — O(path_length).
        pos = network.stations[a]
        n_shots = 0
        for i in range(len(path) - 1):
            delta = edge_delta.get((path[i], path[i + 1]))
            if delta is not None:
                pos = pos + delta
                n_shots += 1

        if n_shots == 0:
            continue

        misclosure = pos - network.stations[b]
        quality = misclosure.length / n_shots  # metres per shot

        # Assign quality to each shot on this traverse (keep best).
        for i in range(len(path) - 1):
            p, q = path[i], path[i + 1]
            key = (p, q) if p < q else (q, p)
            if key not in shot_key_to_quality or quality < shot_key_to_quality[key]:
                shot_key_to_quality[key] = quality

        logger.debug(
            "Traverse %s -> %s: %d shots, misclosure=%.1f m, quality=%.3f m/shot",
            a,
            b,
            n_shots,
            misclosure.length,
            quality,
        )

    # -- Build design matrix with traverse-quality weights -----------------

    row_a_entries: list[tuple[int, int, float]] = []
    row_b_list: list[tuple[float, float, float]] = []
    row_weights: list[float] = []
    row_idx = 0

    for shot in network.shots:
        from_anc = shot.from_name in anchors
        to_anc = shot.to_name in anchors
        if from_anc and to_anc:
            continue

        dx, dy, dz = shot.delta.x, shot.delta.y, shot.delta.z
        L = max(shot.distance, 0.1)

        # Base weight: 1/L^2 (percentage-equalising).
        base_w = 1.0 / (L * L)

        # Traverse quality factor: shots on good traverses get
        # BOOSTED weight (protected), shots on bad traverses get
        # REDUCED weight (absorb error).
        key = (min(shot.from_name, shot.to_name), max(shot.from_name, shot.to_name))
        quality = shot_key_to_quality.get(key)

        if quality is not None and quality > 1e-6:
            # quality = misclosure per shot (metres).
            # Good traverse: quality ≈ 0.1 → boost weight 100x
            # Bad traverse: quality ≈ 5.0 → reduce weight 0.04x
            # Factor = 1 / quality^2
            quality_factor = 1.0 / (quality * quality)
        else:
            # Shot not on any traverse (side branch) or perfect
            # quality: use base weight only.
            quality_factor = 1.0

        w = base_w * quality_factor

        if from_anc:
            a = anchor_pos_c[shot.from_name]
            row_a_entries.append((row_idx, station_to_idx[shot.to_name], 1.0))
            row_b_list.append((a.x + dx, a.y + dy, a.z + dz))
        elif to_anc:
            a = anchor_pos_c[shot.to_name]
            row_a_entries.append((row_idx, station_to_idx[shot.from_name], -1.0))
            row_b_list.append((dx - a.x, dy - a.y, dz - a.z))
        else:
            row_a_entries.append((row_idx, station_to_idx[shot.from_name], -1.0))
            row_a_entries.append((row_idx, station_to_idx[shot.to_name], 1.0))
            row_b_list.append((dx, dy, dz))

        row_weights.append(w)
        row_idx += 1

    n_rows = row_idx
    if n_rows == 0:
        return dict(network.stations)

    A = np.zeros((n_rows, m), dtype=np.float64)

    # Vectorised fill via advanced indexing.
    if row_a_entries:
        _a = np.array(row_a_entries, dtype=np.float64)
        A[_a[:, 0].astype(np.intp), _a[:, 1].astype(np.intp)] = _a[:, 2]

    _b = np.array(row_b_list, dtype=np.float64)
    bx = _b[:, 0].copy()
    by = _b[:, 1].copy()
    bz = _b[:, 2].copy()

    W = np.sqrt(np.array(row_weights, dtype=np.float64))
    Aw = A * W[:, np.newaxis]

    sol_x, _, _, _ = np.linalg.lstsq(Aw, bx * W, rcond=None)
    sol_y, _, _, _ = np.linalg.lstsq(Aw, by * W, rcond=None)
    sol_z, _, _, _ = np.linalg.lstsq(Aw, bz * W, rcond=None)

    # -- Build result dict (translate back from centred coords) ---------------

    result: dict[str, Vector3D] = {}
    for name in anchors:
        result[name] = network.stations[name]
    for name, idx in station_to_idx.items():
        result[name] = Vector3D(
            float(sol_x[idx]) + origin.x,
            float(sol_y[idx]) + origin.y,
            float(sol_z[idx]) + origin.z,
        )
    for name in network.stations:
        if name not in result:
            result[name] = network.stations[name]

    # -- Validate (vectorised) ----------------------------------------------

    if network.shots:
        n_s = len(network.shots)
        _dx = np.empty(n_s, dtype=np.float64)
        _dy = np.empty(n_s, dtype=np.float64)
        _dz = np.empty(n_s, dtype=np.float64)
        _sl = np.empty(n_s, dtype=np.float64)
        for _i, _sh in enumerate(network.shots):
            _f = result[_sh.from_name]
            _t = result[_sh.to_name]
            _dx[_i] = _t.x - _f.x
            _dy[_i] = _t.y - _f.y
            _dz[_i] = _t.z - _f.z
            _sl[_i] = _sh.delta.length
        _el = np.sqrt(_dx * _dx + _dy * _dy + _dz * _dz)
        _mask = _sl > 1e-9
        _ratio = np.abs(_el[_mask] - _sl[_mask]) / _sl[_mask]
        violation_count = int(np.sum(_ratio > max_length_frac))

        if violation_count:
            logger.warning(
                "%d shot(s) exceed length tolerance (%.0f%%)",
                violation_count,
                max_length_frac * 100,
            )

    logger.info(
        "Adjusted %d station(s) via LSE solver (%d shots, %d anchors, %d traverses)",
        len(non_anchors),
        n_rows,
        len(anchors),
        len(shot_key_to_quality),
    )

    return result


class LSESolver(SurveyAdjuster):
    """Traverse-quality weighted solver (Larry Fish method).

    Shots on good traverses (small misclosure) are protected with
    high weight.  Shots on bad traverses absorb the error.
    Blunders stay localised.
    """

    def __init__(
        self,
        max_length_change: float = SOLVER_MAX_LENGTH_CHANGE,
        max_angle_change: float = SOLVER_MAX_HEADING_CHANGE,
    ) -> None:
        self._max_length_change = max_length_change
        self._max_angle_change = max_angle_change

    @property
    def name(self) -> str:
        return "LSESolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        if len(network.anchors) < 2:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        return _solve_lse(
            network,
            self._max_length_change,
            self._max_angle_change,
        )
