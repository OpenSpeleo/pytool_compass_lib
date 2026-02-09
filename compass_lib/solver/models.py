# -*- coding: utf-8 -*-
"""Data structures for the survey adjustment solver.

This module is deliberately decoupled from GeoJSON, UTM, Compass file
formats, and any other domain-specific concern.  It operates purely on
station names, 3-D delta vectors, and shot lengths so that any solver
algorithm can be tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import NamedTuple

if TYPE_CHECKING:
    from compass_lib.geojson import ComputedSurvey
    from compass_lib.geojson import Station


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class Vector3D(NamedTuple):
    """An immutable 3-D vector (easting, northing, elevation) in metres."""

    x: float
    y: float
    z: float

    def __add__(self, other: Vector3D) -> Vector3D:  # type: ignore[override]
        return Vector3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3D) -> Vector3D:
        return Vector3D(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector3D:  # type: ignore[override]
        return Vector3D(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> Vector3D:
        return self.__mul__(scalar)

    def __neg__(self) -> Vector3D:
        return Vector3D(-self.x, -self.y, -self.z)

    @property
    def length(self) -> float:
        """Euclidean length of the vector."""
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5


ZERO = Vector3D(0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# Network primitives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NetworkShot:
    """A single shot in the survey network.

    All values are in metres and already corrected for declination /
    convergence.  ``delta`` is the vector **from** ``from_name`` **to**
    ``to_name``.
    """

    from_name: str
    to_name: str
    delta: Vector3D
    distance: float  # original shot length in metres (for weighting)


@dataclass
class Traverse:
    """A traverse between two fixed anchor stations.

    A traverse connects two *different* anchor stations whose
    coordinates are both known.  The misclosure is the difference
    between the measured path delta and the known coordinate difference
    of the two anchors.

    Attributes:
        from_anchor: Name of the starting anchor station.
        to_anchor: Name of the ending anchor station.
        station_names: Ordered station names from ``from_anchor`` to
            ``to_anchor`` (inclusive at both ends).
        shots: Ordered ``NetworkShot`` objects along the traverse,
            matching ``station_names`` pairwise.
        misclosure: ``sum(shot.delta) - (to_pos - from_pos)``.
            A perfect traverse has misclosure == ZERO.
    """

    from_anchor: str
    to_anchor: str
    station_names: list[str]
    shots: list[NetworkShot]
    misclosure: Vector3D = ZERO

    @property
    def total_length(self) -> float:
        """Sum of all shot distances along the traverse."""
        return sum(s.distance for s in self.shots)


# ---------------------------------------------------------------------------
# Survey network
# ---------------------------------------------------------------------------


@dataclass
class SurveyNetwork:
    """The full survey network used by survey adjustment solvers.

    This is the *only* object a solver receives.  It contains everything
    needed to adjust coordinates, with no coupling to Compass or GeoJSON
    data types.

    Attributes:
        stations: Station name  ->  raw BFS-computed position.
        shots: Every shot in the network (directed).
        anchors: Station names whose coordinates are *fixed* and must
            not be adjusted (e.g. GPS-tied stations).
    """

    stations: dict[str, Vector3D] = field(default_factory=dict)
    shots: list[NetworkShot] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)

    # -- adjacency cache (built lazily) ------------------------------------

    _adjacency: dict[str, list[NetworkShot]] | None = field(
        default=None, init=False, repr=False
    )

    @property
    def adjacency(self) -> dict[str, list[NetworkShot]]:
        """Undirected adjacency list (lazily built, cached)."""
        if self._adjacency is None:
            adj: dict[str, list[NetworkShot]] = {}
            for shot in self.shots:
                adj.setdefault(shot.from_name, []).append(shot)
                # Add reverse direction
                rev = NetworkShot(
                    from_name=shot.to_name,
                    to_name=shot.from_name,
                    delta=-shot.delta,
                    distance=shot.distance,
                )
                adj.setdefault(shot.to_name, []).append(rev)
            self._adjacency = adj
        return self._adjacency

    # -- factory -----------------------------------------------------------

    @classmethod
    def from_computed_survey(
        cls,
        survey: ComputedSurvey,
        anchors: dict[str, Station],
    ) -> SurveyNetwork:
        """Build a ``SurveyNetwork`` from an already-propagated survey.

        Shot deltas are taken from the **measurement-based** displacement
        stored on each leg (``measurement_delta``), NOT from coordinate
        differences.  This is critical because coordinate differences
        between consecutive stations already incorporate propagation
        error, masking the actual misclosure that traverse adjustment
        needs to correct.
        """
        stations: dict[str, Vector3D] = {}
        for name, st in survey.stations.items():
            stations[name] = Vector3D(st.easting, st.northing, st.elevation)

        # Build a reverse lookup: Station object id -> dict key.
        # Station.name is the *display* name (unscoped), but dict keys
        # may be file-scoped.  Legs reference Station objects, so we
        # need to recover the scoped key for each leg endpoint.
        station_obj_to_key: dict[int, str] = {
            id(st): key for key, st in survey.stations.items()
        }

        shots: list[NetworkShot] = []
        seen: set[tuple[str, str]] = set()
        for leg in survey.legs:
            from_key = station_obj_to_key.get(id(leg.from_station))
            to_key = station_obj_to_key.get(id(leg.to_station))
            if from_key is None or to_key is None:
                continue

            key = (from_key, to_key)
            rev_key = (to_key, from_key)
            if key in seen or rev_key in seen:
                continue
            seen.add(key)

            if leg.measurement_delta is not None:
                # Use the measurement-based delta (distance, bearing,
                # inclination with declination/convergence applied).
                de, dn, dz = leg.measurement_delta
                delta = Vector3D(de, dn, dz)
            else:
                # Fallback: coordinate difference (less accurate for
                # traverse adjustment, but better than nothing).
                from_pos = stations.get(from_key)
                to_pos = stations.get(to_key)
                if from_pos is None or to_pos is None:
                    continue
                delta = to_pos - from_pos

            shots.append(
                NetworkShot(
                    from_name=from_key,
                    to_name=to_key,
                    delta=delta,
                    distance=(delta.length if delta.length > 0 else 1e-6),
                )
            )

        anchor_names = set(anchors.keys())
        return cls(stations=stations, shots=shots, anchors=anchor_names)
