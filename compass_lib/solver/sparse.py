# -*- coding: utf-8 -*-
"""Sparse (L1-norm) network adjustment solver.

Minimises the **total magnitude** of corrections across all shots
(L1 norm) rather than the sum of squared corrections (L2 norm).
This produces **sparse** corrections: most shots stay very close to
their survey measurements, and only a few shots at key locations
absorb the misclosure.

The L1 problem is solved as a linear program (LP) via
``scipy.optimize.linprog``.

Anchors remain at their exact GPS positions.
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.optimize import linprog  # type: ignore[import-untyped]

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


def _solve_l1(
    network: SurveyNetwork,
    max_length_frac: float,
) -> dict[str, Vector3D]:
    """L1-norm network solve via linear programming.

    Minimises  sum( w_i * |residual_i| )  where residual_i is the
    difference between the effective shot delta and the measured delta.
    Weight w_i = 1/L_i (equalises percentage-change sensitivity).

    The LP is solved independently for x, y, z.
    """
    # Filter out anchors that don't exist in stations (orphan link
    # stations, already warned about upstream).
    anchors = network.anchors & set(network.stations.keys())
    non_anchors = sorted(set(network.stations.keys()) - anchors)

    if not non_anchors:
        return dict(network.stations)

    m = len(non_anchors)
    station_to_idx = {name: i for i, name in enumerate(non_anchors)}

    anchor_pos: dict[str, Vector3D] = {
        name: network.stations[name] for name in anchors
    }

    # -- Centre coordinates for numerical stability ---------------------------
    # UTM coordinates can be O(10^5..10^6).  Subtracting a reference
    # point keeps all LP values near zero, avoiding precision loss
    # in the HiGHS solver.
    _all_pos = list(anchor_pos.values())
    origin = Vector3D(
        sum(p.x for p in _all_pos) / len(_all_pos),
        sum(p.y for p in _all_pos) / len(_all_pos),
        sum(p.z for p in _all_pos) / len(_all_pos),
    )
    anchor_pos_c = {n: p - origin for n, p in anchor_pos.items()}

    # -- Build the design matrix A and RHS (same structure as lstsq) -------

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

        row_weights.append(1.0 / L)
        row_idx += 1

    n_rows = row_idx
    if n_rows == 0:
        return dict(network.stations)

    # Build numpy arrays — vectorised fill.
    A = np.zeros((n_rows, m), dtype=np.float64)
    w = np.array(row_weights, dtype=np.float64)

    if row_a_entries:
        _a = np.array(row_a_entries, dtype=np.float64)
        A[_a[:, 0].astype(np.intp), _a[:, 1].astype(np.intp)] = _a[:, 2]

    _b = np.array(row_b_list, dtype=np.float64)
    bx = _b[:, 0].copy()
    by = _b[:, 1].copy()
    bz = _b[:, 2].copy()

    # -- Solve L1 as LP for each axis --------------------------------------
    #
    # minimize   sum( w_i * (sp_i + sn_i) )
    # subject to A*x - sp + sn = b
    #            sp >= 0,  sn >= 0,  x free
    #
    # Variables: [x (m), sp (n_rows), sn (n_rows)]
    # Total: m + 2*n_rows

    n_vars = m + 2 * n_rows

    # Cost vector: 0 for x, w for sp, w for sn
    c_lp = np.zeros(n_vars, dtype=np.float64)
    c_lp[m : m + n_rows] = w
    c_lp[m + n_rows :] = w

    # Equality constraint: A*x - I*sp + I*sn = b
    # => [A, -I, I] @ [x, sp, sn] = b
    A_eq = np.zeros((n_rows, n_vars), dtype=np.float64)
    A_eq[:, :m] = A
    _diag_idx = np.arange(n_rows)
    A_eq[_diag_idx, m + _diag_idx] = -1.0           # -sp_i
    A_eq[_diag_idx, m + n_rows + _diag_idx] = 1.0   # +sn_i

    # Bounds: x is free (-inf, inf), sp/sn >= 0
    bounds = [(None, None)] * m + [(0, None)] * (2 * n_rows)

    def solve_axis(b_vec: np.ndarray) -> np.ndarray:
        result = linprog(
            c_lp,
            A_eq=A_eq,
            b_eq=b_vec,
            bounds=bounds,
            method="highs",
            options={"presolve": True},
        )
        if not result.success:
            logger.warning("L1 solver: %s", result.message)
            # Fallback to zero (no adjustment).
            return np.zeros(m, dtype=np.float64)
        return result.x[:m]

    sol_x = solve_axis(bx)
    sol_y = solve_axis(by)
    sol_z = solve_axis(bz)

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

    # -- Validate (vectorised, single pass) ---------------------------------

    violation_count = 0
    near_zero = 0
    total_shots = 0

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
        total_shots = int(np.sum(_mask))
        _ratio = np.abs(_el[_mask] - _sl[_mask]) / _sl[_mask]
        violation_count = int(np.sum(_ratio > max_length_frac))
        near_zero = int(np.sum(_ratio < 0.001))

    if violation_count:
        logger.warning(
            "%d shot(s) exceed length tolerance (%.0f%%)",
            violation_count, max_length_frac * 100,
        )
    logger.info(
        "Adjusted %d station(s) via L1 sparse solver "
        "(%d shots, %d anchors, %d/%d shots unchanged)",
        len(non_anchors), n_rows, len(anchors),
        near_zero, total_shots,
    )

    return result


class SparseSolver(SurveyAdjuster):
    """Sparse (L1-norm) network adjustment solver.

    Minimises the total magnitude of corrections, producing sparse
    solutions where most shots stay close to their survey measurements
    and only a few key shots absorb the misclosure.
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
        return "SparseSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        if len(network.anchors) < 2:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        return _solve_l1(network, self._max_length_change)
