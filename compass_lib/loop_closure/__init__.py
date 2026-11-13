"""Compass data adapters for loop-closure solvers implemented in cave-closure."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from cave_closure import LoopClosureAlgorithm
from cave_closure import LoopClosureMode
from cave_closure import prepare_arrays
from cave_closure import solve_l1_loop_closure_json as _solve_l1_loop_closure_json

from compass_lib.constants import FEET_TO_METERS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from compass_lib.project.models import CompassMakFile
    from compass_lib.survey.models import CompassShot
    from compass_lib.survey.models import CompassSurveyHeader


def normalized_delta(
    shot: CompassShot,
    header: CompassSurveyHeader,
    *,
    declination: float,
    convergence: float,
) -> tuple[float, float, float]:
    """Calibrate derived values once; one distance produces one complete factor.

    Prefer frontsight components, falling back to reversed backsights. Redundant
    angles are not independently expanded into two shots sharing one tape reading.
    W-format is entry/display metadata and does not imply absolute depths.
    """
    if shot.length is None:
        raise ValueError("shot has no distance")
    length = (shot.length + header.length_correction) * FEET_TO_METERS
    bearing = (
        shot.frontsight_azimuth + header.frontsight_azimuth_correction
        if shot.frontsight_azimuth is not None
        else shot.backsight_azimuth + header.backsight_azimuth_correction + 180
        if shot.backsight_azimuth is not None
        else None
    )
    inclination = (
        shot.frontsight_inclination + header.frontsight_inclination_correction
        if shot.frontsight_inclination is not None
        else -(shot.backsight_inclination + header.backsight_inclination_correction)
        if shot.backsight_inclination is not None
        else None
    )
    if bearing is None or inclination is None:
        raise ValueError("shot requires bearing and inclination")
    if (
        not all(
            math.isfinite(v)
            for v in (length, bearing, inclination, declination, convergence)
        )
        or length < 0
        or abs(inclination) > 90
    ):
        raise ValueError("invalid calibrated shot")
    bearing = math.radians(bearing + declination - convergence)
    inclination = math.radians(inclination)
    horizontal = length * math.cos(inclination)
    return (
        horizontal * math.sin(bearing),
        horizontal * math.cos(bearing),
        length * math.sin(inclination),
    )


@dataclass(frozen=True)
class LoopClosureSnapshot:
    """Owned immutable numerical preparation, independent of later model mutation."""

    prepared: object
    observation_ids: tuple[str, ...]

    def solve(self, **kwargs):
        result = self.prepared.solve(**kwargs)
        result.require_converged()
        return result


def prepare_loop_closure(
    project: CompassMakFile,
    *,
    mode: LoopClosureMode,
    algorithm: LoopClosureAlgorithm = LoopClosureAlgorithm.LSE_REDUCED_PCG,
    sigma_m: float,
    frame_corrections: Mapping[tuple[str, int], tuple[float, float]],
    controls=None,
    preserved_z=None,
) -> LoopClosureSnapshot:
    """Prepare raw observations with explicit per-survey declination/convergence.

    Corrections are keyed by (file name, survey index); station scope follows the
    existing MAK rules. C preserves normalized displacement exactly. X excludes
    processing; P and L remain numerical observations. Covariance is an explicit
    independent isotropic Cartesian placement model, not a raw instrument model.
    """
    # geojson imports this adapter's type through the package interfaces.
    from compass_lib.geojson import _compute_file_scopes  # noqa: PLC0415 - circular import
    from compass_lib.geojson import _get_link_names  # noqa: PLC0415 - circular import
    from compass_lib.geojson import _scope_name  # noqa: PLC0415 - circular import

    if not math.isfinite(sigma_m) or sigma_m <= 0:
        raise ValueError("sigma_m must be positive and finite")
    mode = LoopClosureMode(mode)
    scopes, links = _compute_file_scopes(project), _get_link_names(project)
    rows = []
    for file_index, directive in enumerate(project.file_directives):
        if directive.data is None:
            continue
        for survey_index, survey in enumerate(directive.data.surveys):
            if not any(not shot.excluded_from_all_processing for shot in survey.shots):
                continue
            correction = frame_corrections[directive.file, survey_index]
            for shot_index, shot in enumerate(survey.shots):
                if shot.excluded_from_all_processing:
                    continue
                identity = f"file:{file_index}/survey:{survey_index}/shot:{shot_index}"
                try:
                    delta = normalized_delta(
                        shot,
                        survey.header,
                        declination=correction[0],
                        convergence=correction[1],
                    )
                except ValueError as exc:
                    raise ValueError(f"{identity}: {exc}") from exc
                scope = scopes.get(directive.file, 0)
                rows.append(
                    (
                        identity,
                        _scope_name(shot.from_station_name, scope, links),
                        _scope_name(shot.to_station_name, scope, links),
                        delta,
                        shot.do_not_adjust,
                    )
                )
    controls = {} if controls is None else controls
    ids = sorted({name for _, u, v, _, _ in rows for name in (u, v)} | set(controls))
    index = {name: i for i, name in enumerate(ids)}
    dimension = 3 if mode == LoopClosureMode.SPATIAL else 2
    hard = [
        (
            f"control:{name}",
            index[name],
            list(range(dimension)),
            list(value[:dimension]),
            None,
        )
        for name, value in sorted(controls.items())
    ]
    relationships = [
        (f"protected:{identity}", "hard_offset", index[u], index[v], delta)
        for identity, u, v, delta, protected in rows
        if protected
    ]
    variance = sigma_m**2
    covariance = [[variance, 0.0, 0.0], [0.0, variance, 0.0], [0.0, 0.0, variance]]
    prepared = prepare_arrays(
        ids,
        [row[0] for row in rows],
        [(index[u], index[v]) for _, u, v, _, _ in rows],
        [row[3] for row in rows],
        [covariance for _ in rows],
        mode=mode,
        algorithm=algorithm,
        preserved_z=(
            [preserved_z[name] for name in ids]
            if mode == LoopClosureMode.HORIZONTAL and preserved_z is not None
            else None
        ),
        controls=hard,
        relationships=relationships,
        reading_ids=[[f"{row[0]}/distance", f"{row[0]}/angles"] for row in rows],
        provenance=[
            "Compass raw DAT; calibrated once; caller-declared frame corrections",
            (
                "Independent isotropic Cartesian placement covariance; "
                "no absolute depths inferred"
            ),
        ],
    )
    return LoopClosureSnapshot(prepared, tuple(row[0] for row in rows))


class LoopClosureMethod(StrEnum):
    LEAST_SQUARES = "least_squares"
    INVERSE_LENGTH_WEIGHTED_L1 = "inverse_length_weighted_l1"


@dataclass(frozen=True)
class LoopClosure:
    """Immutable configuration for Gaussian source or legacy graph loop closure."""

    mode: LoopClosureMode
    sigma_m: float | None
    algorithm: LoopClosureAlgorithm | None = LoopClosureAlgorithm.LSE_REDUCED_PCG
    frame_corrections: Mapping[tuple[str, int], tuple[float, float]] | None = None
    method: LoopClosureMethod = LoopClosureMethod.LEAST_SQUARES
    name: str | None = None
    length_floor_m: float = 0.1
    minimum_anchor_count: int = 2
    deduplicate_edges: bool = True
    max_iterations: int | None = None

    def __post_init__(self):
        if not isinstance(self.mode, LoopClosureMode):
            raise TypeError("mode must be a LoopClosureMode")
        if not isinstance(self.method, LoopClosureMethod):
            raise TypeError("method must be a LoopClosureMethod")
        if self.method == LoopClosureMethod.INVERSE_LENGTH_WEIGHTED_L1:
            if self.algorithm is not None or self.sigma_m is not None:
                raise ValueError("L1 requires algorithm=None and sigma_m=None")
            return
        if not isinstance(self.algorithm, LoopClosureAlgorithm):
            raise TypeError("algorithm must be a LoopClosureAlgorithm")
        if self.sigma_m is None or not math.isfinite(self.sigma_m) or self.sigma_m <= 0:
            raise ValueError("sigma_m must be positive and finite")

    def apply(self, project, computed, anchors):
        if self.method == LoopClosureMethod.INVERSE_LENGTH_WEIGHTED_L1:
            names = list(computed.stations)
            index = {name: i for i, name in enumerate(names)}
            identities = {
                id(station): name for name, station in computed.stations.items()
            }
            observations = []
            for i, leg in enumerate(computed.legs):
                start = identities.get(id(leg.from_station))
                stop = identities.get(id(leg.to_station))
                if start is not None and stop is not None:
                    observations.append(
                        (f"leg:{i}", index[start], index[stop], leg.measurement_delta)
                    )
            result = json.loads(
                _solve_l1_loop_closure_json(
                    {
                        "station_ids": names,
                        "observations": observations,
                        "initial_positions": [
                            (station.easting, station.northing, station.elevation)
                            for station in computed.stations.values()
                        ],
                        "anchor_indices": [
                            index[name] for name in anchors if name in index
                        ],
                        "options": {
                            "mode": self.mode.value,
                            "length_floor_m": self.length_floor_m,
                            "minimum_anchor_count": self.minimum_anchor_count,
                            "deduplicate_edges": self.deduplicate_edges,
                            "max_iterations": self.max_iterations,
                        },
                    }
                )
            )
            return {row["station"]: row["value"] for row in result["coordinates"]}
        snapshot = prepare_loop_closure(
            project,
            mode=self.mode,
            algorithm=self.algorithm,
            sigma_m=self.sigma_m,
            frame_corrections=(
                self.frame_corrections
                if self.frame_corrections is not None
                else computed.frame_corrections
            ),
            controls={
                name: (s.easting, s.northing, s.elevation)
                for name, s in anchors.items()
            },
            preserved_z={name: s.elevation for name, s in computed.stations.items()},
        )
        return dict(snapshot.solve(max_iterations=self.max_iterations).coordinates)
