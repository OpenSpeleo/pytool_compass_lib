# -*- coding: utf-8 -*-
"""Survey adjustment solvers for cave survey networks.

Usage::

    from compass_lib.solver import ProportionalSolver
    from compass_lib.geojson import convert_mak_to_geojson

    geojson = convert_mak_to_geojson(path, solver=ProportionalSolver())

Available solvers:

- :class:`NoopSolver` -- no adjustment (raw BFS, the default)
- :class:`ProportionalSolver` -- proportional traverse error
  distribution by graph distance (fast, suitable for most networks)

To create a custom solver, subclass :class:`SurveyAdjuster` and
implement the :meth:`~SurveyAdjuster.adjust` method.
"""

from compass_lib.solver.ariane import ArianeSolver
from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.lse import LSESolver
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Traverse
from compass_lib.solver.models import Vector3D
from compass_lib.solver.noop import NoopSolver
from compass_lib.solver.proportional import ProportionalSolver
from compass_lib.solver.sparse import SparseSolver

__all__ = [
    "ArianeSolver",
    "LSESolver",
    "NetworkShot",
    "NoopSolver",
    "ProportionalSolver",
    "SparseSolver",
    "SurveyAdjuster",
    "SurveyNetwork",
    "Traverse",
    "Vector3D",
]
