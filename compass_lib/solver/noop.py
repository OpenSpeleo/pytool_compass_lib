# -*- coding: utf-8 -*-
"""No-op survey adjustment solver.

Returns station coordinates unchanged.  Useful as a default, for
testing, or when the caller explicitly wants raw BFS coordinates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from compass_lib.solver.base import SurveyAdjuster

if TYPE_CHECKING:
    from compass_lib.solver.models import SurveyNetwork
    from compass_lib.solver.models import Vector3D


class NoopSolver(SurveyAdjuster):
    """Solver that performs no adjustment (identity transform)."""

    @property
    def name(self) -> str:
        return "NoopSolver"

    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        """Return all station positions unchanged."""
        return dict(network.stations)
