# -*- coding: utf-8 -*-
"""Weighted least-squares network adjustment solver.

Solves for all non-anchor station positions simultaneously via a
single weighted least-squares system.  Each shot equation is weighted
by ``1 / L²`` (where *L* is the survey shot length), so that the
solver minimises the sum of squared **percentage** changes rather
than absolute changes.  This keeps short shots (which are more
sensitive to percentage distortion) close to their survey values.

Anchors remain at their exact GPS positions (they are not unknowns).
The solver handles any topology — trees, loops, junctions with 3+
anchors — in one pass with no pairwise iteration or averaging.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


def _solve_network(
    network: SurveyNetwork,
    max_length_frac: float,
    max_angle_frac: float,
) -> dict[str, Vector3D]:
    """Weighted least-squares network solve.

    Weight per shot = ``1 / L²`` so that percentage changes are
    equalised across shots of different lengths.
    """
    anchors = network.anchors
    non_anchors = sorted(set(network.stations.keys()) - anchors)

    if not non_anchors:
        return dict(network.stations)

    m = len(non_anchors)
    station_to_idx = {name: i for i, name in enumerate(non_anchors)}

    anchor_pos: dict[str, Vector3D] = {
        name: network.stations[name] for name in anchors
    }

    # -- Build design matrix and RHS vectors -------------------------------

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

        if from_anc:
            a = anchor_pos[shot.from_name]
            row_a_entries.append((row_idx, station_to_idx[shot.to_name], 1.0))
            row_b_list.append((a.x + dx, a.y + dy, a.z + dz))
        elif to_anc:
            a = anchor_pos[shot.to_name]
            row_a_entries.append((row_idx, station_to_idx[shot.from_name], -1.0))
            row_b_list.append((dx - a.x, dy - a.y, dz - a.z))
        else:
            row_a_entries.append((row_idx, station_to_idx[shot.from_name], -1.0))
            row_a_entries.append((row_idx, station_to_idx[shot.to_name], 1.0))
            row_b_list.append((dx, dy, dz))

        row_weights.append(1.0 / (L * L))
        row_idx += 1

    n_rows = row_idx
    if n_rows == 0:
        return dict(network.stations)

    A = np.zeros((n_rows, m), dtype=np.float64)
    bx = np.zeros(n_rows, dtype=np.float64)
    by = np.zeros(n_rows, dtype=np.float64)
    bz = np.zeros(n_rows, dtype=np.float64)

    for r, c, v in row_a_entries:
        A[r, c] = v
    for i, (vx, vy, vz) in enumerate(row_b_list):
        bx[i] = vx
        by[i] = vy
        bz[i] = vz

    # Apply weights.
    W = np.sqrt(np.array(row_weights, dtype=np.float64))
    A *= W[:, np.newaxis]
    bx *= W
    by *= W
    bz *= W

    # Solve.
    sol_x, _, _, _ = np.linalg.lstsq(A, bx, rcond=None)
    sol_y, _, _, _ = np.linalg.lstsq(A, by, rcond=None)
    sol_z, _, _, _ = np.linalg.lstsq(A, bz, rcond=None)

    # -- Build result ------------------------------------------------------

    result: dict[str, Vector3D] = {}
    for name in anchors:
        result[name] = network.stations[name]
    for name, idx in station_to_idx.items():
        result[name] = Vector3D(
            float(sol_x[idx]), float(sol_y[idx]), float(sol_z[idx]),
        )
    for name in network.stations:
        if name not in result:
            result[name] = network.stations[name]

    # -- Validate ----------------------------------------------------------

    violation_count = 0
    for shot in network.shots:
        s_len = shot.delta.length
        if s_len < 1e-9:
            continue
        eff = result[shot.to_name] - result[shot.from_name]
        e_len = eff.length
        if abs(e_len - s_len) / s_len > max_length_frac:
            violation_count += 1

    if violation_count:
        logger.warning(
            "%d shot(s) exceed length tolerance (%.0f%%)",
            violation_count, max_length_frac * 100,
        )

    logger.info(
        "Adjusted %d station(s) (%d shots, %d anchors)",
        m, n_rows, len(anchors),
    )

    return result


# ---------------------------------------------------------------------------
# Solver class
# ---------------------------------------------------------------------------


class ProportionalSolver(SurveyAdjuster):
    """Weighted least-squares network adjustment solver.

    Equalises percentage changes across shots by weighting each
    equation by ``1/L²``.  Handles multi-anchor junctions in one
    pass.  Anchors stay at GPS.
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
        return "ProportionalSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        if len(network.anchors) < 2:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        return _solve_network(
            network,
            self._max_length_change,
            self._max_angle_change,
        )
