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

from compass_lib.solver.base import SurveyAdjuster
from compass_lib.solver.models import NetworkShot
from compass_lib.solver.models import SurveyNetwork
from compass_lib.solver.models import Traverse
from compass_lib.solver.models import Vector3D
from compass_lib.solver.noop import NoopSolver
from compass_lib.solver.proportional import ProportionalSolver

__all__ = [
    "NetworkShot",
    "NoopSolver",
    "ProportionalSolver",
    "SurveyAdjuster",
    "SurveyNetwork",
    "Traverse",
    "Vector3D",
]
