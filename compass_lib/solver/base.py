# -*- coding: utf-8 -*-
"""Abstract base class for survey adjustment solvers.

To implement a new solver algorithm:

1. Subclass ``SurveyAdjuster``.
2. Implement the ``adjust`` method.
3. Optionally override ``name`` for logging / UI labels.

The solver receives a :class:`SurveyNetwork` (station positions, shots,
anchor list) and returns a dictionary mapping station names to adjusted
3-D coordinates.  Anchor stations must **not** be moved.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compass_lib.solver.models import SurveyNetwork
    from compass_lib.solver.models import Vector3D


class SurveyAdjuster(ABC):
    """Abstract base class for survey adjustment algorithms.

    Subclasses must implement :meth:`adjust`.  The contract is:

    * Input: a :class:`SurveyNetwork` with raw BFS-propagated positions.
    * Output: a ``dict[str, Vector3D]`` of *adjusted* station positions.
    * Anchor stations (``network.anchors``) must keep their original
      coordinates.
    """

    @property
    def name(self) -> str:
        """Human-readable name of the solver (for logging / UI)."""
        return self.__class__.__name__

    @abstractmethod
    def adjust(self, network: SurveyNetwork) -> dict[str, Vector3D]:
        """Adjust station coordinates.

        Args:
            network: The survey network with raw BFS coordinates.

        Returns:
            Dictionary of ``station_name -> adjusted (x, y, z)``
            coordinates.  Every station in ``network.stations`` must
            appear in the result.
        """
        ...
