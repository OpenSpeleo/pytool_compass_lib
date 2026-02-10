# -*- coding: utf-8 -*-
"""Sparse CG-based network adjustment with traverse-quality weighting.

Combines Ariane's performance strategy (sparse normal equations solved
via Conjugate Gradient) with our traverse-quality weighting (Larry Fish
method) and full 3D adjustment.

**From Ariane:**

- Builds the Normal Equations ``N x = n`` directly in sparse format
  (weighted graph Laplacian), instead of assembling a dense design
  matrix and calling ``lstsq``.  Memory drops from O(stations²) to
  O(edges); solve time from O(n³) to O(nnz × iterations).
- Uses Conjugate Gradient (CG) to solve the symmetric positive-definite
  system, with a direct-solver fallback for robustness.
- Warm-starts CG from BFS-propagated positions.

**From our approach:**

- Full 3D adjustment (X, Y, Z) — Ariane only adjusts the horizontal
  plane.
- Traverse-quality weighting: shots on good traverses (low misclosure
  per shot) are protected with high weight; shots on bad traverses
  absorb the error.  Blunders stay localised (Larry Fish insight).
- ``1/L²`` base weight (percentage-equalising) rather than Ariane's
  ``1/L``.
- Post-solve validation and detailed logging.
"""

from __future__ import annotations

import logging
from collections import deque
from itertools import combinations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import cg as sparse_cg
from scipy.sparse.linalg import spsolve

from compass_lib.constants import SOLVER_MAX_HEADING_CHANGE
from compass_lib.constants import SOLVER_MAX_LENGTH_CHANGE
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Vector3D

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Traverse quality helpers
# ---------------------------------------------------------------------------


def _find_path(
    start: str,
    end: str,
    adj: dict[str, list[NetworkShot]],
    blocked: frozenset[str] = frozenset(),
) -> list[str] | None:
    """BFS shortest path, avoiding *blocked* intermediate stations."""
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


def _compute_traverse_quality(
    network: SurveyNetwork,
) -> dict[tuple[str, str], float]:
    """Compute per-shot traverse quality scores.

    For each pair of adjacent anchors, find the traverse path and
    compute misclosure per shot.  Each shot gets the quality score
    of the **best** traverse it belongs to (lowest misclosure/shot).

    Returns
    -------
    dict
        Mapping ``(min(a, b), max(a, b)) -> quality`` where *quality*
        is misclosure-per-shot in metres.
    """
    anchors = network.anchors
    adj = network.adjacency
    shot_key_to_quality: dict[tuple[str, str], float] = {}

    # Build a directed edge lookup for O(1) path-walk instead of
    # scanning adjacency lists per step.
    edge_delta: dict[tuple[str, str], Vector3D] = {}
    for shot in network.shots:
        edge_delta[(shot.from_name, shot.to_name)] = shot.delta
        edge_delta[(shot.to_name, shot.from_name)] = -shot.delta

    anchor_list = sorted(anchors)
    all_anchors_frozen = frozenset(anchors)

    for a, b in combinations(anchor_list, 2):
        # Derive blocked set efficiently from the pre-computed full set.
        other = all_anchors_frozen - {a, b}
        path = _find_path(a, b, adj, blocked=other)
        if path is None or len(path) < 2:
            continue

        # Forward-propagate to compute misclosure — O(path_length)
        # using the edge lookup instead of scanning adjacency lists.
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
            "Traverse %s -> %s: %d shots, misclosure=%.1f m, "
            "quality=%.3f m/shot",
            a, b, n_shots, misclosure.length, quality,
        )

    return shot_key_to_quality


# ---------------------------------------------------------------------------
# Sparse Normal Equations solver
# ---------------------------------------------------------------------------


def _solve_ariane(
    network: SurveyNetwork,
    max_length_frac: float,
    cg_maxiter: int = 60_000,
    cg_tol: float = 1e-8,
) -> dict[str, Vector3D]:
    """Sparse CG solver with traverse-quality weighting.

    Assembles the Normal Equations (weighted graph Laplacian) directly
    in sparse COO format and solves via Conjugate Gradient, following
    Ariane's approach but extended to 3D with Larry Fish weighting.

    The observation equation per edge ``(u → v)`` is::

        x_v - x_u = dx_observed   (and same for y, z)

    Minimising ``Σ w_e · (x_v - x_u - dx)²`` over all edges yields
    the Normal Equations  ``N · x = rhs``  where *N* is the weighted
    graph Laplacian over free vertices (symmetric positive-definite
    when at least one anchor exists).
    """
    # Filter out anchors that don't exist in stations (orphan link
    # stations, already warned about upstream).
    anchors = network.anchors & set(network.stations.keys())
    non_anchors = sorted(set(network.stations.keys()) - anchors)

    if not non_anchors:
        return dict(network.stations)

    n = len(non_anchors)
    station_to_idx = {name: i for i, name in enumerate(non_anchors)}
    anchor_pos: dict[str, Vector3D] = {
        name: network.stations[name] for name in anchors
    }

    # -- Centre coordinates for numerical stability ---------------------------
    _all_pos = list(anchor_pos.values())
    origin = Vector3D(
        sum(p.x for p in _all_pos) / len(_all_pos),
        sum(p.y for p in _all_pos) / len(_all_pos),
        sum(p.z for p in _all_pos) / len(_all_pos),
    )
    anchor_pos_c = {n: p - origin for n, p in anchor_pos.items()}

    # -- Traverse quality (Larry Fish) --------------------------------------
    shot_quality = _compute_traverse_quality(network)

    # -- Assemble sparse Normal Equations directly --------------------------
    #
    # Following Ariane's approach: build  N = A^T W A  and  rhs = A^T W b
    # edge-by-edge in COO format.  The matrix N is the weighted graph
    # Laplacian over free vertices — symmetric positive-definite when at
    # least one anchor exists.

    coo_rows: list[int] = []
    coo_cols: list[int] = []
    coo_vals: list[float] = []

    rhs_x = np.zeros(n, dtype=np.float64)
    rhs_y = np.zeros(n, dtype=np.float64)
    rhs_z = np.zeros(n, dtype=np.float64)

    # Initial guess from BFS-propagated positions (warm start for CG),
    # centred around the anchor centroid for numerical stability.
    x0 = np.zeros(n, dtype=np.float64)
    y0 = np.zeros(n, dtype=np.float64)
    z0 = np.zeros(n, dtype=np.float64)
    for name, idx in station_to_idx.items():
        pos = network.stations[name] - origin
        x0[idx] = pos.x
        y0[idx] = pos.y
        z0[idx] = pos.z

    n_edges = 0
    for shot in network.shots:
        from_anc = shot.from_name in anchors
        to_anc = shot.to_name in anchors
        if from_anc and to_anc:
            continue  # Both fixed — nothing to solve.

        dx, dy, dz = shot.delta.x, shot.delta.y, shot.delta.z
        L = max(shot.distance, 0.1)

        # Base weight: 1/L² (percentage-equalising).
        base_w = 1.0 / (L * L)

        # Traverse-quality factor (Larry Fish).
        key = (
            min(shot.from_name, shot.to_name),
            max(shot.from_name, shot.to_name),
        )
        quality = shot_quality.get(key)
        if quality is not None and quality > 1e-6:
            quality_factor = 1.0 / (quality * quality)
        else:
            quality_factor = 1.0

        w = base_w * quality_factor
        n_edges += 1

        u_idx = station_to_idx.get(shot.from_name)  # None if anchor
        v_idx = station_to_idx.get(shot.to_name)     # None if anchor

        if u_idx is not None and v_idx is not None:
            # Case 1: both free — full Laplacian contribution.
            #   N[u,u] += w,   N[v,v] += w
            #   N[u,v] -= w,   N[v,u] -= w
            coo_rows.extend([u_idx, v_idx, u_idx, v_idx])
            coo_cols.extend([u_idx, v_idx, v_idx, u_idx])
            coo_vals.extend([w, w, -w, -w])

            rhs_x[u_idx] -= w * dx
            rhs_x[v_idx] += w * dx
            rhs_y[u_idx] -= w * dy
            rhs_y[v_idx] += w * dy
            rhs_z[u_idx] -= w * dz
            rhs_z[v_idx] += w * dz

        elif u_idx is not None:
            # Case 2: u free, v fixed (anchor).
            #   N[u,u] += w
            #   rhs[u] += w · (x_v_fixed - dx)
            coo_rows.append(u_idx)
            coo_cols.append(u_idx)
            coo_vals.append(w)

            v_pos = anchor_pos_c[shot.to_name]
            rhs_x[u_idx] += w * (v_pos.x - dx)
            rhs_y[u_idx] += w * (v_pos.y - dy)
            rhs_z[u_idx] += w * (v_pos.z - dz)

        elif v_idx is not None:
            # Case 3: u fixed (anchor), v free.
            #   N[v,v] += w
            #   rhs[v] += w · (x_u_fixed + dx)
            coo_rows.append(v_idx)
            coo_cols.append(v_idx)
            coo_vals.append(w)

            u_pos = anchor_pos_c[shot.from_name]
            rhs_x[v_idx] += w * (u_pos.x + dx)
            rhs_y[v_idx] += w * (u_pos.y + dy)
            rhs_z[v_idx] += w * (u_pos.z + dz)

        # Case 4 (both fixed) already filtered above.

    if not coo_rows:
        return dict(network.stations)

    # Build sparse CSR matrix (COO → CSR; duplicate entries are summed).
    N = coo_matrix(
        (
            np.array(coo_vals, dtype=np.float64),
            (
                np.array(coo_rows, dtype=np.int32),
                np.array(coo_cols, dtype=np.int32),
            ),
        ),
        shape=(n, n),
    ).tocsr()

    # -- Solve via Conjugate Gradient for each axis -------------------------
    #
    # N is symmetric positive-definite (weighted graph Laplacian with at
    # least one anchor removed), so CG is guaranteed to converge.
    # X, Y, Z are independent and can be solved separately (Ariane solves
    # X and Y in parallel threads; here we solve sequentially for
    # simplicity but the structure allows trivial parallelisation).

    sol_x, info_x = sparse_cg(
        N, rhs_x, x0=x0, atol=cg_tol, maxiter=cg_maxiter,
    )
    sol_y, info_y = sparse_cg(
        N, rhs_y, x0=y0, atol=cg_tol, maxiter=cg_maxiter,
    )
    sol_z, info_z = sparse_cg(
        N, rhs_z, x0=z0, atol=cg_tol, maxiter=cg_maxiter,
    )

    # Fallback to direct solver if CG did not converge.
    if info_x != 0:
        logger.warning(
            "CG did not converge for X (info=%d), "
            "falling back to direct solver", info_x,
        )
        sol_x = spsolve(N, rhs_x)
    if info_y != 0:
        logger.warning(
            "CG did not converge for Y (info=%d), "
            "falling back to direct solver", info_y,
        )
        sol_y = spsolve(N, rhs_y)
    if info_z != 0:
        logger.warning(
            "CG did not converge for Z (info=%d), "
            "falling back to direct solver", info_z,
        )
        sol_z = spsolve(N, rhs_z)

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
                violation_count, max_length_frac * 100,
            )

    logger.info(
        "Adjusted %d station(s) via Ariane solver "
        "(%d shots, %d anchors, %d traverses, sparse CG)",
        len(non_anchors), n_edges, len(anchors),
        len(shot_quality),
    )

    return result


# ---------------------------------------------------------------------------
# Solver class
# ---------------------------------------------------------------------------


class ArianeSolver(SurveyAdjuster):
    """Sparse CG solver with traverse-quality weighting.

    Combines Ariane's sparse normal-equations / Conjugate Gradient
    approach with Larry Fish's traverse-quality weighting and full
    3D adjustment.

    Key properties:

    - **O(edges) memory** instead of O(stations²) — scales to
      100k+ station networks.
    - **O(nnz × iterations) solve time** instead of O(n³).
    - **Traverse-quality weights** protect good surveys from
      blunder contamination.
    - **Full 3D** (X, Y, Z) — Ariane only adjusts the horizontal
      plane.

    Parameters
    ----------
    max_length_change : float
        Maximum relative change to a shot's tape length during
        adjustment.  Used for post-solve validation warnings.
    max_angle_change : float
        Maximum relative change to a shot's heading during
        adjustment.  Used for post-solve validation warnings.
    cg_maxiter : int
        Maximum iterations for the Conjugate Gradient solver.
        Default 60 000 (matching Ariane).
    cg_tol : float
        Absolute residual tolerance for CG convergence.
    """

    def __init__(
        self,
        max_length_change: float = SOLVER_MAX_LENGTH_CHANGE,
        max_angle_change: float = SOLVER_MAX_HEADING_CHANGE,
        cg_maxiter: int = 60_000,
        cg_tol: float = 1e-8,
    ) -> None:
        self._max_length_change = max_length_change
        self._max_angle_change = max_angle_change
        self._cg_maxiter = cg_maxiter
        self._cg_tol = cg_tol

    @property
    def name(self) -> str:
        return "ArianeSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        if len(network.anchors) < 2:
            logger.info("Fewer than 2 anchors -- nothing to adjust")
            return dict(network.stations)

        return _solve_ariane(
            network,
            self._max_length_change,
            cg_maxiter=self._cg_maxiter,
            cg_tol=self._cg_tol,
        )
