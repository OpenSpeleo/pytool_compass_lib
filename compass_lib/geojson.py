# -*- coding: utf-8 -*-
"""GeoJSON export for Compass survey data.

This module converts Compass survey data (MAK + DAT files) to GeoJSON format.
It computes station coordinates by traversing the survey shots from fixed
reference points (link stations with coordinates or the project location).

GeoJSON output uses WGS84 coordinates (longitude, latitude, elevation in meters).

Architecture follows openspeleo_lib pattern:
- Build station graph from shots
- Propagate coordinates via BFS from anchor points
- Convert to GeoJSON using the geojson library

Declination handling:
- Declination is ALWAYS calculated from the project anchor location and survey date
- The datum specified in the MAK file is ignored; WGS84 is always used
- This provides consistent, accurate magnetic declination values

Convergence handling:
- UTM convergence angle is ALWAYS applied to align survey azimuths with the UTM grid
- The convergence value comes from the MAK file (% or * directive, or @ location)

Exclusion flags:
- X (total exclusion): Shot excluded from all processing
- P (plotting exclusion): Shot excluded from GeoJSON output
- L (length exclusion): Ignored (only affects length statistics)
- C (close exclusion): Ignored (only affects closure statistics)
"""

from __future__ import annotations

import datetime
import logging
import math
import uuid
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import orjson
import utm
from geojson import Feature
from geojson import FeatureCollection
from geojson import LineString
from geojson import Point
from geojson import Polygon
from pyproj import Transformer
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from compass_lib.constants import FEET_TO_METERS
from compass_lib.constants import GEOJSON_COORDINATE_PRECISION
from compass_lib.constants import JSON_ENCODING
from compass_lib.constants import METERS_TO_FEET
from compass_lib.enums import Datum
from compass_lib.geo_utils import GeoLocation
from compass_lib.geo_utils import get_declination
from compass_lib.io import load_project
from compass_lib.solver.models import SurveyNetwork

if TYPE_CHECKING:
    from pathlib import Path

    from compass_lib.project.models import CompassMakFile
    from compass_lib.solver.base import SurveyAdjuster
    from compass_lib.survey.models import CompassShot
    from compass_lib.survey.models import CompassSurvey

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class NoKnownAnchorError(Exception):
    """Raised when a survey has no known anchor station."""


class DisconnectedStationError(Exception):
    """Raised when a station is disconnected from the graph."""


class InvalidCoordinateError(Exception):
    """Raised when coordinate conversion fails."""


# -----------------------------------------------------------------------------
# Data Classes
# -----------------------------------------------------------------------------


@dataclass
class Station:
    """A computed station with UTM coordinates."""

    name: str
    easting: float  # UTM easting in meters
    northing: float  # UTM northing in meters
    elevation: float  # Elevation in meters
    file: str = ""
    survey: str = ""
    origin: str = ""  # Anchor station this was propagated from (debug)
    path_distance: float = 0.0  # Cumulative survey distance from origin (meters)


@dataclass
class SurveyLeg:
    """A survey leg (shot) between two stations."""

    from_station: Station
    to_station: Station
    distance: float
    azimuth: float | None
    inclination: float | None
    file: str = ""
    survey: str = ""
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None
    lruds_at_to_station: bool = (
        False  # Controls which station LRUDs are associated with
    )
    excluded_from_plotting: bool = False
    """P-flag: shot participates in coordinate propagation but is
    not rendered in the GeoJSON output (no leg or passage feature).
    """
    measurement_delta: tuple[float, float, float] | None = None
    """Measurement-based displacement (de, dn, dz) in metres.

    Computed from the shot's distance, bearing, inclination with
    declination and convergence applied.  Used by survey adjustment solvers
    to detect misclosure (coordinate differences telescope to zero,
    but measurement deltas do not).
    """


@dataclass
class MisclosureLeg:
    """A misclosure gap between two BFS propagation fronts.

    When solver is None (cross-origin), this shows where the BFS from
    one anchor computed a station at position ``ghost`` while the
    station already exists at position ``existing``.  The gap between
    them is the raw survey misclosure.

    When solver is not None (same-origin), this shows where a loop
    within the same BFS front has a closure error.  The ``ghost`` is
    the position computed by the arriving (typically longer) path; the
    ``existing`` is the position already set by the first path to
    reach the station.  The longest path is considered the "true"
    segment; closure error is ghost - existing.
    """

    existing: Station  # Station already computed by another anchor's BFS
    ghost: Station  # Where the current anchor's BFS would place it
    file: str = ""
    survey: str = ""
    same_origin: bool = False  # True for loops within the same BFS front


@dataclass
class ComputedSurvey:
    """Computed survey with station coordinates."""

    stations: dict[str, Station] = field(default_factory=dict)
    legs: list[SurveyLeg] = field(default_factory=list)
    misclosures: list[MisclosureLeg] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)
    utm_zone: int | None = None
    utm_northern: bool = True
    datum: Datum | None = None


# -----------------------------------------------------------------------------
# Origin colour palette (simplestyle spec)
# -----------------------------------------------------------------------------

#: Distinct colours assigned to each BFS origin anchor so that legs and
#: stations can be visually distinguished by their propagation source.
#: Viewers that support the simplestyle spec (geojson.io, GitHub, QGIS,
#: Mapbox, …) will render these automatically.
ORIGIN_COLORS: list[str] = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # grey
    "#bcbd22",  # olive
    "#17becf",  # cyan
]


# -----------------------------------------------------------------------------
# Coordinate Utilities
# -----------------------------------------------------------------------------


def length_to_meters(length_ft: float) -> float:
    """Convert length from feet to meters."""
    return length_ft * FEET_TO_METERS


# Cache for pyproj transformers (source CRS -> transformer)
_transformer_cache: dict[str, Transformer] = {}


def _get_transformer(zone: int, northern: bool, datum: Datum) -> Transformer:
    """Get or create a cached transformer from UTM to WGS84.

    Args:
        zone: UTM zone number
        northern: True for northern hemisphere
        datum: The source datum

    Returns:
        Transformer from the source UTM CRS to WGS84
    """
    source_epsg = datum.get_utm_epsg(zone, northern)
    if source_epsg not in _transformer_cache:
        _transformer_cache[source_epsg] = Transformer.from_crs(
            source_epsg,
            "EPSG:4326",  # WGS84
            always_xy=True,
        )
    return _transformer_cache[source_epsg]


def utm_to_wgs84(
    easting: float,
    northing: float,
    zone: int,
    northern: bool,
    datum: Datum,
) -> tuple[float, float]:
    """Convert UTM coordinates to WGS84 (longitude, latitude).

    Uses pyproj for proper datum transformation, which is critical when
    the source data is in NAD27 or NAD83 (common for older Compass files).

    Args:
        easting: UTM easting in meters
        northing: UTM northing in meters
        zone: UTM zone number (1-60 north, -1 to -60 south; absolute value used)
        northern: True if northern hemisphere
        datum: Source datum (default WGS84, use NAD27 for older data)

    Returns:
        Tuple of (longitude, latitude) in degrees (GeoJSON order)

    Raises:
        InvalidCoordinateError: If conversion fails
    """
    try:
        transformer = _get_transformer(abs(zone), northern, datum)
        lon, lat = transformer.transform(easting, northing)
        return (
            round(float(lon), GEOJSON_COORDINATE_PRECISION),
            round(float(lat), GEOJSON_COORDINATE_PRECISION),
        )
    except Exception as e:
        raise InvalidCoordinateError(
            f"Failed to convert UTM ({easting}, {northing}) zone {zone} "
            f"datum {datum}: {e}"
        ) from e


# -----------------------------------------------------------------------------
# Declination and Convergence
# -----------------------------------------------------------------------------


def get_project_location_wgs84(project: CompassMakFile) -> GeoLocation | None:
    """Get the project anchor location as WGS84 lat/lon.

    The anchor location is used for calculating magnetic declination.
    It is found in this priority order:
    1. LocationDirective (@) if it has a valid location (zone != 0)
    2. First fixed station with coordinates from link stations

    Args:
        project: The Compass project

    Returns:
        GeoLocation with lat/lon, or None if no valid location found
    """
    if not project.utm_zone:
        logger.warning("No UTM zone found in project")
        return None

    # Determine hemisphere from zone sign (positive = north, negative = south)
    northern = project.utm_zone > 0
    utm_zone = abs(project.utm_zone)

    # Try 1: Use project location (@) if valid
    loc = project.location
    if loc and loc.has_location:
        try:
            lat, lon = utm.to_latlon(
                loc.easting, loc.northing, utm_zone, northern=northern
            )
            return GeoLocation(latitude=lat, longitude=lon)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to convert project location to lat/lon: "
                "easting=%.2f, northing=%.2f, zone=%d, northern=%b",
                loc.easting,
                loc.northing,
                utm_zone,
                northern,
            )

    # Try 2: Use first fixed station with coordinates
    fixed_stations = project.get_fixed_stations()
    if fixed_stations:
        first_fixed = fixed_stations[0]
        fixed_loc = first_fixed.location
        if fixed_loc:
            # Convert feet to meters if needed
            factor = FEET_TO_METERS if fixed_loc.unit.lower() == "f" else 1.0

            easting = fixed_loc.easting * factor
            northing = fixed_loc.northing * factor

            try:
                lat, lon = utm.to_latlon(easting, northing, utm_zone, northern=northern)
                logger.info(
                    "Using fixed station '%s' as anchor location: (%.4f, %.4f)",
                    first_fixed.name,
                    lat,
                    lon,
                )
                return GeoLocation(latitude=lat, longitude=lon)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to convert fixed station '%s' to lat/lon: "
                    "easting=%.2f, northing=%.2f, zone=%d, northern=%b",
                    first_fixed.name,
                    easting,
                    northing,
                    utm_zone,
                    northern,
                )

    logger.warning("No valid anchor location found for declination calculation")
    return None


def get_station_location_wgs84(
    station: Station,
    utm_zone: int,
    utm_northern: bool,
    datum: Datum = Datum.WGS_1984,
) -> GeoLocation:
    """Convert a station's UTM coordinates to WGS84 lat/lon for declination calculation.

    IMPORTANT: Compass stores ALL UTM coordinates in northern hemisphere format,
    regardless of the zone sign. The zone sign only indicates which hemisphere
    the cave is in for grid orientation purposes (convergence corrections).

    Therefore, we ALWAYS use northern=True when converting coordinates to get
    the actual geographic location for declination calculation.

    The datum parameter is CRITICAL for older Compass projects that use NAD27.
    The shift between NAD27 and WGS84 can be ~200 meters in some regions.

    Args:
        station: Station with UTM coordinates
        utm_zone: UTM zone number (can be negative for southern hemisphere)
        utm_northern: Hemisphere flag (parameter kept for API consistency but not used)
        datum: Source datum for the UTM coordinates (default WGS84)

    Returns:
        GeoLocation with actual WGS84 lat/lon coordinates

    Raises:
        InvalidCoordinateError: If conversion fails
    """
    # Always use northern=True because Compass stores all coordinates in northern format
    # The zone sign is only used for convergence/grid orientation,
    # not coordinate storage
    lon, lat = utm_to_wgs84(
        station.easting, station.northing, utm_zone, northern=True, datum=datum
    )
    return GeoLocation(latitude=lat, longitude=lon)


def calculate_survey_declination(
    station_location: GeoLocation,
    survey_date: datetime.date | None,
) -> float:
    """Calculate magnetic declination for a survey survey.

    Uses a station location from the survey and the survey date to calculate
    the magnetic declination using the IGRF model. The station location should
    be from an anchor station in the survey's file, or from the current station
    being processed.

    Args:
        station_location: Location of a station from the survey in WGS84
        survey_date: Date of the survey survey

    Returns:
        Declination in degrees (positive = east, negative = west)

    Raises:
        Exception: If declination calculation fails
    """
    try:
        if survey_date is None:
            raise ValueError("Impossible to determine the survey date")  # noqa: TRY301

        # Convert date to datetime for the IGRF calculation
        dt = datetime.datetime(survey_date.year, survey_date.month, survey_date.day)  # noqa: DTZ001
        return get_declination(station_location, dt)

    except Exception:
        logger.exception(
            "Failed to calculate declination for date %s at location (%.4f, %.4f)",
            survey_date,
            station_location.latitude,
            station_location.longitude,
        )
        raise


# -----------------------------------------------------------------------------
# Graph Building
# -----------------------------------------------------------------------------


_FILE_SCOPE_SEP = "\x1f"
"""Unit-separator character used to scope station names.

Station names that are NOT listed as link stations in the MAK file are
prefixed with ``{scope_id}<US>`` to prevent cross-scope merges.
Link station names remain unscoped so that they correctly bridge scopes.

Scoping follows the "global until explicit linking" rule:

- By default station names are **global** across all DAT files.
  Files that do not declare bare (coordinate-free) link stations share
  the current scope group, so identical names freely merge.
- A file that lists at least one link station **without** coordinates
  (a bare name) starts a **new** scope group.  Only the declared link
  station names bridge the two groups; all other names are isolated.
- Link stations **with** coordinates are anchors (fixed reference
  points) and do **not** create a scope boundary.
"""


def _get_link_names(project: CompassMakFile) -> set[str]:
    """Collect all link station names across every file directive.

    These names are "global" — they intentionally appear in multiple
    DAT files and must share a single graph node.  All other station
    names are scope-grouped to prevent accidental cross-scope merges.
    """
    return {ls.name for fd in project.file_directives for ls in fd.link_stations}


def _compute_file_scopes(project: CompassMakFile) -> dict[str, int]:
    """Assign a scope-group ID to each file directive.

    Station names are **global until explicit linking**: files that do
    not declare bare link stations share the current scope group (their
    station names freely merge).  When a file directive lists at least
    one link station **without** coordinates the scope counter
    increments, isolating that file's non-link station names from the
    previous group.

    Link stations that carry coordinates are **anchors** (fixed
    reference points) and do **not** create a scope boundary.

    Returns:
        Mapping of ``file_directive.file`` → scope-group ID.
    """
    file_scopes: dict[str, int] = {}
    current_scope = 0
    for fd in project.file_directives:
        # Explicit linking = at least one link station WITHOUT coordinates.
        # Link stations with coordinates are just anchors (fixed points).
        has_explicit_linking = any(ls.location is None for ls in fd.link_stations)
        if has_explicit_linking:
            current_scope += 1
        file_scopes[fd.file] = current_scope
    return file_scopes


def _scope_name(name: str, scope_id: int, link_names: set[str]) -> str:
    """Return a scope-grouped station name, or the raw name for link stations."""
    if name in link_names:
        return name
    return f"{scope_id}{_FILE_SCOPE_SEP}{name}"


def _display_name(scoped_name: str) -> str:
    """Strip the file-scope prefix to recover the original station name."""
    if _FILE_SCOPE_SEP in scoped_name:
        return scoped_name.split(_FILE_SCOPE_SEP, 1)[1]
    return scoped_name


def build_station_graph(
    project: CompassMakFile,
) -> tuple[
    dict[str, list[tuple[CompassShot, str, str, CompassSurvey, bool]]],
    list[tuple[CompassShot, str, str, CompassSurvey]],
]:
    """Build adjacency graph from all shots in project.

    Station names follow the **global-until-explicit-linking** rule:
    files that do not declare link stations share a scope group so
    identical station names freely merge.  When a file directive lists
    explicit link stations a new scope group starts, and only the
    declared link station names bridge the two groups.  Link station
    names remain global (unscoped) across all scopes.

    Excludes:
    - Shots marked as excluded_from_all_processing (X flag)
    - Self-loops (from == to station, data errors)

    Returns:
        Tuple of (adjacency_dict, all_shots_list)
    """
    link_names = _get_link_names(project)
    file_scopes = _compute_file_scopes(project)

    all_shots: list[tuple[CompassShot, str, str, CompassSurvey]] = []
    adjacency: dict[
        str, list[tuple[CompassShot, str, str, CompassSurvey, bool, str, str]]
    ] = {}

    for file_dir in project.file_directives:
        if not file_dir.data:
            continue

        scope_id = file_scopes.get(file_dir.file, 0)

        for survey in file_dir.data.surveys:
            survey_name = survey.header.survey_name or "unnamed"
            for shot in survey.shots:
                # Skip shots excluded from all processing (X flag).
                # P-flagged shots (excluded from plotting) are kept in
                # the graph for coordinate propagation; the resulting
                # legs are marked so they can be hidden in GeoJSON output.
                if shot.excluded_from_all_processing:
                    continue

                all_shots.append((shot, file_dir.file, survey_name, survey))

                from_name = _scope_name(shot.from_station_name, scope_id, link_names)
                to_name = _scope_name(shot.to_station_name, scope_id, link_names)

                # Skip self-loops (from == to).  These are data errors
                # that create impossible solver constraints.
                if from_name == to_name:
                    logger.warning(
                        "Skipping self-loop: %s -> %s in %s:%s",
                        shot.from_station_name,
                        shot.to_station_name,
                        file_dir.file,
                        survey_name,
                    )
                    continue

                if from_name not in adjacency:
                    adjacency[from_name] = []
                if to_name not in adjacency:
                    adjacency[to_name] = []

                # Add forward and reverse connections.
                # Pre-scoped names are stored in the tuple so BFS
                # does not need to re-scope per shot.
                adjacency[from_name].append(
                    (
                        shot,
                        file_dir.file,
                        survey_name,
                        survey,
                        False,
                        from_name,
                        to_name,
                    )
                )
                adjacency[to_name].append(
                    (shot, file_dir.file, survey_name, survey, True, from_name, to_name)
                )

    return adjacency, all_shots


def find_anchor_stations(project: CompassMakFile) -> dict[str, Station]:
    """Find all anchor stations with known coordinates.

    Anchors come from:
    1. Link stations with fixed coordinates in file directives
    2. Project location (as origin for first station)

    Returns:
        Dictionary of station name -> Station with coordinates
    """
    anchors: dict[str, Station] = {}

    # Get fixed stations from link stations
    for file_dir in project.file_directives:
        for link_station in file_dir.link_stations:
            if link_station.location:
                loc = link_station.location
                factor = FEET_TO_METERS if loc.unit.lower() == "f" else 1.0
                anchors[link_station.name] = Station(
                    name=link_station.name,
                    easting=loc.easting * factor,
                    northing=loc.northing * factor,
                    elevation=loc.elevation * factor,
                    file=file_dir.file,
                )
                logger.debug(
                    "Anchor station: %s at (%.2f, %.2f, %.2f)",
                    link_station.name,
                    loc.easting * factor,
                    loc.northing * factor,
                    loc.elevation * factor,
                )

    return anchors


# -----------------------------------------------------------------------------
# Coordinate Propagation
# -----------------------------------------------------------------------------


def compute_shot_delta(
    shot: CompassShot,
    is_reverse: bool,
    declination: float,
    convergence: float,
) -> tuple[float, float, float]:
    """Compute the displacement vector (de, dn, dz) for a shot.

    This is the measurement-based delta in metres, accounting for
    direction, declination, and convergence.  It is independent of
    any station positions.

    Args:
        shot: The shot data
        is_reverse: Whether traversing in reverse direction
        declination: Magnetic declination (degrees)
        convergence: UTM convergence angle (degrees)

    Returns:
        Tuple of (delta_easting, delta_northing, delta_elevation) in metres.
    """
    distance = shot.length or 0.0

    # Get azimuth/inclination based on direction
    if is_reverse:
        if shot.backsight_azimuth is not None:
            azimuth = shot.backsight_azimuth
        elif shot.frontsight_azimuth is not None:
            azimuth = (shot.frontsight_azimuth + 180.0) % 360.0
        else:
            azimuth = None

        if shot.backsight_inclination is not None:
            inclination = -shot.backsight_inclination
        elif shot.frontsight_inclination is not None:
            inclination = -shot.frontsight_inclination
        else:
            inclination = None
    else:
        azimuth = shot.frontsight_azimuth
        inclination = shot.frontsight_inclination

    azimuth = azimuth if azimuth is not None else 0.0
    inclination = inclination if inclination is not None else 0.0

    azimuth_corrected = azimuth + declination - convergence
    azimuth_rad = math.radians(azimuth_corrected)
    inclination_rad = math.radians(inclination)

    distance_m = length_to_meters(distance)
    horizontal_distance = distance_m * math.cos(inclination_rad)
    vertical_distance = distance_m * math.sin(inclination_rad)

    delta_easting = horizontal_distance * math.sin(azimuth_rad)
    delta_northing = horizontal_distance * math.cos(azimuth_rad)

    return (delta_easting, delta_northing, vertical_distance)


def compute_next_station(
    from_station: Station,
    shot: CompassShot,
    to_name: str,
    is_reverse: bool,
    declination: float,
    convergence: float,
) -> Station:
    """Compute coordinates of the next station from a shot.

    Args:
        from_station: Starting station with known coordinates
        shot: The shot data
        to_name: Name of the target station
        is_reverse: Whether traversing in reverse direction
        declination: Magnetic declination to apply (degrees, calculated from location+date)
        convergence: UTM convergence angle to apply (degrees, from project)

    Returns:
        Station with computed coordinates
    """  # noqa: E501
    de, dn, dz = compute_shot_delta(shot, is_reverse, declination, convergence)

    return Station(
        name=to_name,
        easting=from_station.easting + de,
        northing=from_station.northing + dn,
        elevation=from_station.elevation + dz,
    )


def propagate_coordinates(
    project: CompassMakFile,
    anchors: dict[str, Station],
    adjacency: dict[str, list[tuple[CompassShot, str, str, CompassSurvey, bool]]],
    *,
    detect_same_origin_loops: bool = False,
) -> ComputedSurvey:
    """Propagate coordinates from anchor stations via BFS.

    Declination is calculated per survey using:
    - Project anchor location (from @ directive)
    - Survey date from survey header

    UTM convergence is always applied from the project settings.

    Args:
        project: The Compass project
        anchors: Dictionary of anchor stations with known coordinates
        adjacency: Station adjacency graph
        detect_same_origin_loops: When True, record :class:`MisclosureLeg`
            entries for loops that close within the same BFS front (same
            origin).  The longest path from the origin to the closing
            station is the "true" segment; the gap between its computed
            position and the existing position is the raw closure error.
            Enable this when a solver will be applied.

    Returns:
        ComputedSurvey with all computed stations and legs
    """
    result = ComputedSurvey()

    # Set metadata
    result.datum = project.datum
    result.utm_zone = project.utm_zone

    # Determine hemisphere from zone sign (positive = north, negative = south)
    if result.utm_zone:
        result.utm_northern = result.utm_zone > 0

    # Get convergence angle from project (always applied)
    convergence = project.utm_convergence
    logger.info("UTM convergence angle: %.3f°", convergence)

    # Get LRUD flags from project
    flags = project.flags
    lruds_at_to_station = flags.lruds_at_to_station if flags else False

    # Cache for survey declinations (calculated once per survey)
    survey_declinations: dict[str, float] = {}

    # Anchor-by-file index for O(1) declination lookup (avoids linear
    # scan over all anchors per survey).
    anchor_by_file: dict[str, Station] = {}
    for _a in anchors.values():
        if _a.file and _a.file not in anchor_by_file:
            anchor_by_file[_a.file] = _a

    # When a solver is active, use *single-origin* BFS: seed from one
    # anchor and traverse the full network (forward + reverse edges).
    # This propagates the entire traverse from the same starting point
    # so that closures appear at the far anchor, not at arbitrary BFS
    # meeting points.  The longest path is the "true" segment.
    _secondary_anchors: dict[str, Station] = {}

    if detect_same_origin_loops and len(anchors) > 1:
        # Pick first connected anchor as primary
        primary_name = next(
            (n for n in anchors if n in adjacency),
            next(iter(anchors.keys())),
        )
        primary_station = anchors[primary_name]
        primary_station.origin = primary_name
        result.stations = {primary_name: primary_station}
        result.anchors = {primary_name}
        _secondary_anchors = {k: v for k, v in anchors.items() if k != primary_name}
    else:
        # Multi-origin BFS: seed from all anchors
        result.stations = dict(anchors)
        result.anchors = set(anchors.keys())
        for anchor_name, anchor_station in result.stations.items():
            anchor_station.origin = anchor_name

    # Validate seeded stations against the shot graph — a station
    # whose name does not appear in any shot is disconnected and
    # cannot seed BFS.
    disconnected = {name for name in result.stations if name not in adjacency}
    if disconnected:
        for name in sorted(disconnected):
            logger.warning(
                "Anchor '%s' (file: %s) has no shots in the survey data "
                "-- check that the link station name matches a station "
                "in the DAT file",
                name,
                result.stations[name].file,
            )
        # Remove disconnected anchors so they don't pollute the BFS
        for name in disconnected:
            del result.stations[name]
            result.anchors.discard(name)

    if not result.stations:
        raise NoKnownAnchorError("No anchor stations found and no shots available")

    logger.info(
        "Starting coordinate propagation from %d anchor(s)", len(result.stations)
    )

    # BFS from anchor stations.
    # Multi-origin mode: FORWARD ONLY (reverse edges skipped).
    # Single-origin mode (solver active): forward + reverse edges
    # so the full traverse is computed from the same starting point
    # and closures appear at the far anchor, not at arbitrary BFS
    # meeting points.
    queue: deque[str] = deque(result.stations.keys())
    visited_stations: set[str] = set(result.stations.keys())
    visited_shots: set[tuple[str, str]] = set()

    while queue:
        current_name = queue.popleft()
        current_station = result.stations.get(current_name)
        if not current_station:
            continue

        for (
            shot,
            file_name,
            survey_name,
            survey,
            is_reverse,
            from_name,
            to_name,
        ) in adjacency.get(current_name, []):
            # Multi-origin: forward only.  Single-origin: both.
            if is_reverse and not detect_same_origin_loops:
                continue

            # Target station depends on traversal direction
            target_name = from_name if is_reverse else to_name

            # Skip already processed shots
            shot_key = (min(from_name, to_name), max(from_name, to_name))
            if shot_key in visited_shots:
                continue
            visited_shots.add(shot_key)

            # Calculate declination for this survey (cached)
            survey_key = f"{file_name}:{survey_name}"
            if survey_key not in survey_declinations:
                survey_anchor = anchor_by_file.get(file_name)
                location_station = survey_anchor if survey_anchor else current_station

                station_wgs84 = get_station_location_wgs84(
                    location_station,
                    result.utm_zone,
                    result.utm_northern,
                    result.datum or Datum.WGS_1984,
                )

                logger.debug(
                    "Survey %s: using station %s at UTM(%.1f, %.1f) zone=%d northern=%s -> WGS84(%.4f, %.4f)",  # noqa: E501
                    survey_key,
                    location_station.name,
                    location_station.easting,
                    location_station.northing,
                    result.utm_zone,
                    result.utm_northern,
                    station_wgs84.latitude,
                    station_wgs84.longitude,
                )

                declination = calculate_survey_declination(
                    station_wgs84, survey.header.date
                )
                survey_declinations[survey_key] = declination
                logger.debug(
                    "Survey %s declination: %.2f° (date: %s, station: %s)",
                    survey_key,
                    declination,
                    survey.header.date,
                    location_station.name,
                )
            else:
                declination = survey_declinations[survey_key]

            # Direction-dependent delta.  For forward edges this uses
            # the frontsight; for reverse edges it uses the backsight
            # (or frontsight + 180° when no backsight is available).
            shot_delta = compute_shot_delta(
                shot,
                is_reverse,
                declination,
                convergence,
            )
            de, dn, dz = shot_delta

            # Compute target station position.
            ghost_e = current_station.easting + de
            ghost_n = current_station.northing + dn
            ghost_z = current_station.elevation + dz

            if target_name not in result.stations:
                # New station: place it at the computed position.
                new_station = Station(
                    name=_display_name(target_name),
                    easting=ghost_e,
                    northing=ghost_n,
                    elevation=ghost_z,
                )
                new_station.file = file_name
                new_station.survey = survey_name
                new_station.origin = current_station.origin
                new_station.path_distance = (
                    current_station.path_distance + length_to_meters(shot.length or 0.0)
                )
                result.stations[target_name] = new_station

                if target_name not in visited_stations:
                    visited_stations.add(target_name)
                    queue.append(target_name)

                # Create the leg.
                leg = SurveyLeg(
                    from_station=current_station,
                    to_station=new_station,
                    distance=shot.length or 0.0,
                    azimuth=shot.frontsight_azimuth,
                    inclination=shot.frontsight_inclination,
                    file=file_name,
                    survey=survey_name,
                    left=shot.left,
                    right=shot.right,
                    up=shot.up,
                    down=shot.down,
                    lruds_at_to_station=lruds_at_to_station,
                    excluded_from_plotting=shot.excluded_from_plotting,
                    measurement_delta=shot_delta,
                )
                result.legs.append(leg)

            else:
                # Target station already exists.  If it was computed by
                # a different origin, record a misclosure gap.
                existing_station = result.stations[target_name]

                if existing_station.origin != current_station.origin:
                    # Ghost = where THIS front would place the station.
                    ghost_station = Station(
                        name=_display_name(target_name) + "'",
                        easting=ghost_e,
                        northing=ghost_n,
                        elevation=ghost_z,
                    )
                    ghost_station.file = file_name
                    ghost_station.survey = survey_name
                    ghost_station.origin = current_station.origin
                    ghost_station.path_distance = (
                        current_station.path_distance
                        + length_to_meters(shot.length or 0.0)
                    )

                    # Leg from current → ghost (shows where BFS goes).
                    leg = SurveyLeg(
                        from_station=current_station,
                        to_station=ghost_station,
                        distance=shot.length or 0.0,
                        azimuth=shot.frontsight_azimuth,
                        inclination=shot.frontsight_inclination,
                        file=file_name,
                        survey=survey_name,
                        left=shot.left,
                        right=shot.right,
                        up=shot.up,
                        down=shot.down,
                        lruds_at_to_station=lruds_at_to_station,
                        excluded_from_plotting=shot.excluded_from_plotting,
                        measurement_delta=shot_delta,
                    )
                    result.legs.append(leg)

                    # Misclosure line from ghost → existing.
                    result.misclosures.append(
                        MisclosureLeg(
                            existing=existing_station,
                            ghost=ghost_station,
                            file=file_name,
                            survey=survey_name,
                        ),
                    )
                else:
                    # Same origin: create a normal leg to the
                    # existing station (loop within same BFS front).
                    leg = SurveyLeg(
                        from_station=current_station,
                        to_station=existing_station,
                        distance=shot.length or 0.0,
                        azimuth=shot.frontsight_azimuth,
                        inclination=shot.frontsight_inclination,
                        file=file_name,
                        survey=survey_name,
                        left=shot.left,
                        right=shot.right,
                        up=shot.up,
                        down=shot.down,
                        lruds_at_to_station=lruds_at_to_station,
                        excluded_from_plotting=shot.excluded_from_plotting,
                        measurement_delta=shot_delta,
                    )
                    result.legs.append(leg)

                    # When a solver will be applied, record same-origin
                    # loop closures.  The whole path is propagated from
                    # the same origin; the longest path to the closing
                    # station is the "true" segment.
                    if detect_same_origin_loops:
                        ghost_station = Station(
                            name=_display_name(target_name) + "'",
                            easting=ghost_e,
                            northing=ghost_n,
                            elevation=ghost_z,
                            file=file_name,
                            survey=survey_name,
                            origin=current_station.origin,
                            path_distance=(
                                current_station.path_distance
                                + length_to_meters(shot.length or 0.0)
                            ),
                        )
                        result.misclosures.append(
                            MisclosureLeg(
                                existing=existing_station,
                                ghost=ghost_station,
                                file=file_name,
                                survey=survey_name,
                                same_origin=True,
                            ),
                        )

    # ── Secondary anchor closure (single-origin BFS) ────────────
    # In single-origin mode, secondary anchors were placed by BFS
    # with propagated positions.  Compare with their known (fixed)
    # positions to get the full-traverse closure, then snap them
    # to the known position so the solver treats them as anchors.
    #
    # Secondary anchors that were NOT reached by BFS belong to
    # disconnected components (separate caves).  They are placed
    # at their known position and queued for additional BFS so
    # their connected stations are also computed.
    _disconnected_secondaries: list[str] = []

    if _secondary_anchors:
        for sec_name, sec_known in _secondary_anchors.items():
            bfs_station = result.stations.get(sec_name)
            if bfs_station is not None:
                gap = (
                    (bfs_station.easting - sec_known.easting) ** 2
                    + (bfs_station.northing - sec_known.northing) ** 2
                    + (bfs_station.elevation - sec_known.elevation) ** 2
                ) ** 0.5
                if gap > 1e-6:
                    ghost = Station(
                        name=sec_known.name + "'",
                        easting=bfs_station.easting,
                        northing=bfs_station.northing,
                        elevation=bfs_station.elevation,
                        file=bfs_station.file,
                        survey=bfs_station.survey,
                        origin=bfs_station.origin,
                        path_distance=bfs_station.path_distance,
                    )
                    result.misclosures.append(
                        MisclosureLeg(
                            existing=Station(
                                name=sec_known.name,
                                easting=sec_known.easting,
                                northing=sec_known.northing,
                                elevation=sec_known.elevation,
                                file=sec_known.file,
                            ),
                            ghost=ghost,
                            file=bfs_station.file,
                            survey=bfs_station.survey,
                        ),
                    )
                    logger.info(
                        "Closure at anchor '%s': %.3f m (path distance: %.1f m)",
                        sec_known.name,
                        gap,
                        bfs_station.path_distance,
                    )
                # Snap to known anchor position for the solver
                bfs_station.easting = sec_known.easting
                bfs_station.northing = sec_known.northing
                bfs_station.elevation = sec_known.elevation
                bfs_station.origin = sec_name
            else:
                # Not reached by BFS — disconnected component.
                # Place at known position and queue for BFS.
                sec_station = Station(
                    name=sec_known.name,
                    easting=sec_known.easting,
                    northing=sec_known.northing,
                    elevation=sec_known.elevation,
                    file=sec_known.file,
                    origin=sec_name,
                )
                result.stations[sec_name] = sec_station
                _disconnected_secondaries.append(sec_name)
            result.anchors.add(sec_name)

    # ── BFS from disconnected secondary anchors ────────────────
    # Each disconnected secondary anchor seeds an independent BFS
    # for its connected component.  These are separate caves that
    # don't share any stations with the primary anchor's component.
    if _disconnected_secondaries:
        logger.info(
            "Running BFS from %d disconnected anchor(s): %s",
            len(_disconnected_secondaries),
            ", ".join(_disconnected_secondaries),
        )
        for sec_name in _disconnected_secondaries:
            sec_queue: deque[str] = deque([sec_name])
            visited_stations.add(sec_name)

            while sec_queue:
                current_name = sec_queue.popleft()
                current_station = result.stations.get(current_name)
                if not current_station:
                    continue

                for (
                    shot,
                    file_name,
                    survey_name,
                    survey,
                    is_reverse,
                    from_name,
                    to_name,
                ) in adjacency.get(current_name, []):
                    # Same traversal rules as main BFS
                    target_name = from_name if is_reverse else to_name

                    shot_key = (min(from_name, to_name), max(from_name, to_name))
                    if shot_key in visited_shots:
                        continue
                    visited_shots.add(shot_key)

                    survey_key = f"{file_name}:{survey_name}"
                    if survey_key not in survey_declinations:
                        survey_anchor = anchor_by_file.get(file_name)
                        location_station = (
                            survey_anchor if survey_anchor else current_station
                        )
                        station_wgs84 = get_station_location_wgs84(
                            location_station,
                            result.utm_zone,
                            result.utm_northern,
                            result.datum or Datum.WGS_1984,
                        )
                        declination = calculate_survey_declination(
                            station_wgs84,
                            survey.header.date,
                        )
                        survey_declinations[survey_key] = declination
                        logger.debug(
                            "Survey %s declination: %.2f° (date: %s)",
                            survey_key,
                            declination,
                            survey.header.date,
                        )
                    else:
                        declination = survey_declinations[survey_key]

                    shot_delta = compute_shot_delta(
                        shot,
                        is_reverse,
                        declination,
                        convergence,
                    )
                    de, dn, dz = shot_delta

                    ghost_e = current_station.easting + de
                    ghost_n = current_station.northing + dn
                    ghost_z = current_station.elevation + dz

                    if target_name not in result.stations:
                        new_station = Station(
                            name=_display_name(target_name),
                            easting=ghost_e,
                            northing=ghost_n,
                            elevation=ghost_z,
                            file=file_name,
                            survey=survey_name,
                            origin=sec_name,
                            path_distance=(
                                current_station.path_distance
                                + length_to_meters(shot.length or 0.0)
                            ),
                        )
                        result.stations[target_name] = new_station

                        if target_name not in visited_stations:
                            visited_stations.add(target_name)
                            sec_queue.append(target_name)

                        leg = SurveyLeg(
                            from_station=current_station,
                            to_station=new_station,
                            distance=shot.length or 0.0,
                            azimuth=shot.frontsight_azimuth,
                            inclination=shot.frontsight_inclination,
                            file=file_name,
                            survey=survey_name,
                            left=shot.left,
                            right=shot.right,
                            up=shot.up,
                            down=shot.down,
                            lruds_at_to_station=lruds_at_to_station,
                            excluded_from_plotting=shot.excluded_from_plotting,
                            measurement_delta=shot_delta,
                        )
                        result.legs.append(leg)
                    else:
                        existing_station = result.stations[target_name]
                        leg = SurveyLeg(
                            from_station=current_station,
                            to_station=existing_station,
                            distance=shot.length or 0.0,
                            azimuth=shot.frontsight_azimuth,
                            inclination=shot.frontsight_inclination,
                            file=file_name,
                            survey=survey_name,
                            left=shot.left,
                            right=shot.right,
                            up=shot.up,
                            down=shot.down,
                            lruds_at_to_station=lruds_at_to_station,
                            excluded_from_plotting=shot.excluded_from_plotting,
                            measurement_delta=shot_delta,
                        )
                        result.legs.append(leg)

                        if detect_same_origin_loops:
                            ghost_station = Station(
                                name=_display_name(target_name) + "'",
                                easting=ghost_e,
                                northing=ghost_n,
                                elevation=ghost_z,
                                file=file_name,
                                survey=survey_name,
                                origin=sec_name,
                                path_distance=(
                                    current_station.path_distance
                                    + length_to_meters(shot.length or 0.0)
                                ),
                            )
                            result.misclosures.append(
                                MisclosureLeg(
                                    existing=existing_station,
                                    ghost=ghost_station,
                                    file=file_name,
                                    survey=survey_name,
                                    same_origin=True,
                                ),
                            )

    # Fallback: stations unreachable by forward-only BFS.
    # Some surveys have the link station as the TO station, so
    # the only way to reach their FROM stations is via reverse.
    # Do a second pass using reverse edges for these orphans only.
    all_graph_stations = set(adjacency.keys())
    orphaned = all_graph_stations - visited_stations

    if orphaned:
        # Seed the queue with all already-computed stations that have
        # reverse edges to orphaned stations.
        fallback_queue: deque[str] = deque()
        for name in list(visited_stations):
            for (
                _,
                _,
                _,
                _,
                is_reverse,
                _from_scoped,
                _,
            ) in adjacency.get(name, []):
                if not is_reverse:
                    continue
                if _from_scoped in orphaned:
                    fallback_queue.append(name)
                    break

        while fallback_queue:
            current_name = fallback_queue.popleft()
            current_station = result.stations.get(current_name)
            if not current_station:
                continue

            for (
                shot,
                file_name,
                survey_name,
                survey,
                is_reverse,
                from_name,
                to_name,
            ) in adjacency.get(current_name, []):
                shot_key = (min(from_name, to_name), max(from_name, to_name))
                if shot_key in visited_shots:
                    continue

                # Determine target and direction.
                target_name = from_name if is_reverse else to_name

                if target_name in result.stations:
                    continue  # Already computed

                visited_shots.add(shot_key)

                survey_key = f"{file_name}:{survey_name}"
                if survey_key not in survey_declinations:
                    survey_anchor = anchor_by_file.get(file_name)
                    location_station = (
                        survey_anchor if survey_anchor else current_station
                    )
                    station_wgs84 = get_station_location_wgs84(
                        location_station,
                        result.utm_zone,
                        result.utm_northern,
                        result.datum or Datum.WGS_1984,
                    )
                    declination = calculate_survey_declination(
                        station_wgs84,
                        survey.header.date,
                    )
                    survey_declinations[survey_key] = declination
                else:
                    declination = survey_declinations[survey_key]

                forward_delta = compute_shot_delta(
                    shot,
                    is_reverse=False,
                    declination=declination,
                    convergence=convergence,
                )
                de, dn, dz = forward_delta

                if is_reverse:
                    # Computing from_station from to_station.
                    new_station = Station(
                        name=_display_name(target_name),
                        easting=current_station.easting - de,
                        northing=current_station.northing - dn,
                        elevation=current_station.elevation - dz,
                    )
                    leg_from = new_station
                    leg_to = current_station
                else:
                    # Computing to_station from from_station.
                    new_station = Station(
                        name=_display_name(target_name),
                        easting=current_station.easting + de,
                        northing=current_station.northing + dn,
                        elevation=current_station.elevation + dz,
                    )
                    leg_from = current_station
                    leg_to = new_station

                new_station.file = file_name
                new_station.survey = survey_name
                new_station.origin = current_station.origin
                new_station.path_distance = (
                    current_station.path_distance + length_to_meters(shot.length or 0.0)
                )
                result.stations[target_name] = new_station
                visited_stations.add(target_name)
                fallback_queue.append(target_name)

                # Leg always in forward direction.
                leg = SurveyLeg(
                    from_station=leg_from,
                    to_station=leg_to,
                    distance=shot.length or 0.0,
                    azimuth=shot.frontsight_azimuth,
                    inclination=shot.frontsight_inclination,
                    file=file_name,
                    survey=survey_name,
                    left=shot.left,
                    right=shot.right,
                    up=shot.up,
                    down=shot.down,
                    lruds_at_to_station=lruds_at_to_station,
                    excluded_from_plotting=shot.excluded_from_plotting,
                    measurement_delta=forward_delta,
                )
                result.legs.append(leg)

        # Re-check for any still-orphaned stations.
        orphaned = all_graph_stations - visited_stations

    if orphaned:
        display = sorted(_display_name(n) for n in orphaned)
        logger.warning(
            "%d station(s) unreachable from any anchor: %s",
            len(orphaned),
            ", ".join(display[:20]) + (" ..." if len(display) > 20 else ""),
        )

    logger.info(
        "Computed %d stations and %d legs",
        len(result.stations),
        len(result.legs),
    )

    return result


def compute_survey_coordinates(
    project: CompassMakFile,
    solver: SurveyAdjuster | None = None,
) -> ComputedSurvey:
    """Compute station coordinates from survey data.

    This is the main entry point for coordinate computation.

    Args:
        project: Loaded CompassMakFile with DAT data
        solver: Optional survey adjuster.  When provided, traverse
            adjustment is applied after BFS propagation.  Pass
            ``ProportionalSolver()`` for proportional correction.

    Returns:
        ComputedSurvey with station coordinates and legs
    """
    adjacency, _ = build_station_graph(project)
    anchors = find_anchor_stations(project)
    result = propagate_coordinates(
        project,
        anchors,
        adjacency,
        detect_same_origin_loops=(solver is not None),
    )

    if solver is not None:
        logger.info("Applying survey adjustment: %s", solver.name)

        # Solver handles all closures — clear misclosure lines
        # so they do not appear in the GeoJSON output.
        result.misclosures.clear()

        # Reconnect ghost-station leg endpoints to real stations.
        _name_to_station: dict[str, Station] = {}
        for _key, _st in result.stations.items():
            _name_to_station[_st.name] = _st
            _dname = _display_name(_key)
            if _dname != _st.name:
                _name_to_station[_dname] = _st

        for leg in result.legs:
            if leg.to_station.name.endswith("'"):
                real = _name_to_station.get(leg.to_station.name[:-1])
                if real is not None:
                    leg.to_station = real
            if leg.from_station.name.endswith("'"):
                real = _name_to_station.get(leg.from_station.name[:-1])
                if real is not None:
                    leg.from_station = real

        # Run solver
        network = SurveyNetwork.from_computed_survey(result, anchors)
        adjusted = solver.adjust(network)
        for name, coords in adjusted.items():
            station = result.stations.get(name)
            if station is not None:
                station.easting = coords.x
                station.northing = coords.y
                station.elevation = coords.z

    return result


# -----------------------------------------------------------------------------
# GeoJSON Feature Creation
# -----------------------------------------------------------------------------


def _cached_utm_to_wgs84(
    easting: float,
    northing: float,
    zone: int,
    northern: bool,
    datum: Datum,
    cache: dict[tuple[float, float], tuple[float, float]] | None = None,
) -> tuple[float, float]:
    """UTM-to-WGS84 with optional coordinate cache.

    When *cache* is provided, results are memoised by ``(easting,
    northing)`` so that the same station is only converted once
    through pyproj regardless of how many legs reference it.
    """
    if cache is not None:
        key = (easting, northing)
        hit = cache.get(key)
        if hit is not None:
            return hit
        result = utm_to_wgs84(easting, northing, zone, northern, datum)
        cache[key] = result
        return result
    return utm_to_wgs84(easting, northing, zone, northern, datum)


def station_to_feature(
    station: Station,
    zone: int,
    northern: bool,
    datum: Datum = Datum.WGS_1984,
    wgs84_cache: dict[tuple[float, float], tuple[float, float]] | None = None,
) -> Feature:
    """Convert a station to a GeoJSON Point Feature.

    Args:
        station: Station with coordinates
        zone: UTM zone number
        northern: True if northern hemisphere
        datum: Source datum for UTM coordinates (critical for NAD27 data)
        wgs84_cache: Optional coordinate cache for deduplication

    Returns:
        GeoJSON Feature with Point geometry
    """
    lon, lat = _cached_utm_to_wgs84(
        station.easting,
        station.northing,
        zone,
        northern,
        datum,
        wgs84_cache,
    )

    properties: dict[str, Any] = {
        "type": "station",
        "name": station.name,
        "file": station.file,
        "survey": station.survey,
        "elevation_m": round(station.elevation, 2),
    }
    if station.origin:
        properties["origin"] = station.origin

    return Feature(
        geometry=Point((lon, lat, round(station.elevation, 2))),
        properties=properties,
    )


def anchor_to_feature(
    station: Station,
    zone: int,
    northern: bool,
    datum: Datum = Datum.WGS_1984,
    wgs84_cache: dict[tuple[float, float], tuple[float, float]] | None = None,
) -> Feature:
    """Convert an anchor station to a GeoJSON Point Feature.

    Anchor stations are fixed reference points with known coordinates
    (from link stations in the MAK file).

    Args:
        station: Anchor station with coordinates
        zone: UTM zone number
        northern: True if northern hemisphere
        datum: Source datum for UTM coordinates (critical for NAD27 data)
        wgs84_cache: Optional coordinate cache for deduplication

    Returns:
        GeoJSON Feature with Point geometry and type "anchor"
    """
    lon, lat = _cached_utm_to_wgs84(
        station.easting,
        station.northing,
        zone,
        northern,
        datum,
        wgs84_cache,
    )

    depth_ft = round(station.elevation * METERS_TO_FEET, 2)

    return Feature(
        geometry=Point((lon, lat, round(station.elevation, 2))),
        properties={
            "id": station.name,
            "depth": abs(depth_ft),
            "name": station.survey,
        },
    )


def leg_to_feature(
    leg: SurveyLeg,
    zone: int,
    northern: bool,
    datum: Datum = Datum.WGS_1984,
    wgs84_cache: dict[tuple[float, float], tuple[float, float]] | None = None,
) -> Feature:
    """Convert a survey leg to a GeoJSON LineString Feature.

    Args:
        leg: Survey leg with from/to stations
        zone: UTM zone number
        northern: True if northern hemisphere
        datum: Source datum for UTM coordinates (critical for NAD27 data)
        wgs84_cache: Optional coordinate cache for deduplication

    Returns:
        GeoJSON Feature with LineString geometry
    """
    from_lon, from_lat = _cached_utm_to_wgs84(
        leg.from_station.easting,
        leg.from_station.northing,
        zone,
        northern,
        datum,
        wgs84_cache,
    )
    to_lon, to_lat = _cached_utm_to_wgs84(
        leg.to_station.easting,
        leg.to_station.northing,
        zone,
        northern,
        datum,
        wgs84_cache,
    )

    depth_m = leg.to_station.elevation
    depth_ft = round(depth_m * METERS_TO_FEET, 2)

    return Feature(
        geometry=LineString(
            [
                (from_lon, from_lat, round(leg.from_station.elevation, 2)),
                (to_lon, to_lat, round(leg.to_station.elevation, 2)),
            ]
        ),
        properties={
            "id": str(uuid.uuid5(uuid.NAMESPACE_OID, leg.to_station.name)),
            "depth": abs(depth_ft),  # Compass depth is < 0
            "name": leg.survey,
        },
    )


def _station_left_right_utm(
    easting: float,
    northing: float,
    azimuth_rad: float,
    left_m: float,
    right_m: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Compute left and right offset positions in UTM from a station and shot direction.

    Returns:
        ((left_e, left_n), (right_e, right_n))
    """
    perp_rad = azimuth_rad + math.pi / 2
    left_e = easting + left_m * math.sin(perp_rad)
    left_n = northing + left_m * math.cos(perp_rad)
    right_e = easting - right_m * math.sin(perp_rad)
    right_n = northing - right_m * math.cos(perp_rad)
    return (left_e, left_n), (right_e, right_n)


def _shapely_to_passage_features(
    geom: Any,
    elev: float,
    properties: dict[str, Any],
) -> list[Feature]:
    """Convert Shapely Polygon or MultiPolygon to GeoJSON Feature(s) with elevation."""
    features: list[Feature] = []
    if geom.is_empty or not geom.is_valid:
        return features
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        return features
    polys = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        if poly.is_empty or not poly.is_valid:
            continue
        ext = list(poly.exterior.coords)
        ring = [
            [
                round(x, GEOJSON_COORDINATE_PRECISION),
                round(y, GEOJSON_COORDINATE_PRECISION),
                elev,
            ]
            for x, y in ext
        ]
        holes = []
        for interior in poly.interiors:
            hole = [
                [
                    round(x, GEOJSON_COORDINATE_PRECISION),
                    round(y, GEOJSON_COORDINATE_PRECISION),
                    elev,
                ]
                for x, y in interior.coords
            ]
            holes.append(hole)
        coords = [ring, *holes]
        features.append(Feature(geometry=Polygon(coords), properties=properties))
    return features


def _build_station_lrud_map(
    survey: ComputedSurvey,
) -> dict[str, tuple[tuple[float, float], tuple[float, float]]]:
    """Build a map of station name -> (left_utm, right_utm) from legs that define LRUD
    at that station.

    For each leg, the station that "owns" the LRUD (FROM if lruds_at_to_station
    is False, TO if True) gets its left/right positions from that leg's azimuth and
    left/right values. This allows tunnel segments to share edges: the left edge of
    one leg connects to the  left edge of the adjacent leg at the shared station.
    """
    result: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {}
    for leg in survey.legs:
        if (leg.left is None and leg.right is None) or leg.azimuth is None:
            continue

        left_m = length_to_meters(leg.left or 0.0)
        right_m = length_to_meters(leg.right or 0.0)
        azimuth_rad = math.radians(leg.azimuth)
        station = leg.to_station if leg.lruds_at_to_station else leg.from_station
        result[station.name] = _station_left_right_utm(
            station.easting, station.northing, azimuth_rad, left_m, right_m
        )
    return result


def passage_to_feature(
    leg: SurveyLeg,
    zone: int,
    northern: bool,
    datum: Datum = Datum.WGS_1984,
    station_lrud: dict[str, tuple[tuple[float, float], tuple[float, float]]]
    | None = None,
    wgs84_cache: dict[tuple[float, float], tuple[float, float]] | None = None,
) -> Feature | None:
    """Convert LRUD data to a passage polygon Feature (one tunnel segment).

    Each leg produces a quadrilateral: the "base" is the left/right at FROM and TO.
    When station_lrud is provided, the left/right at each station come from the leg
    that defines LRUD at that station, so segments connect and form a continuous tunnel.
    If a station is missing from the map, this leg's LRUD and azimuth are used for
    that end.

    Args:
        leg: Survey leg with LRUD data
        zone: UTM zone number
        northern: True if northern hemisphere
        datum: Source datum for UTM coordinates (critical for NAD27 data)
        station_lrud: Optional precomputed map station name -> ((left_e, left_n), (right_e, right_n))
        wgs84_cache: Optional coordinate cache for deduplication

    Returns:
        GeoJSON Feature with Polygon geometry, or None if no LRUD data
    """  # noqa: E501
    if leg.left is None and leg.right is None:
        return None

    if leg.azimuth is None:
        return None

    left_m = length_to_meters(leg.left or 0.0)
    right_m = length_to_meters(leg.right or 0.0)
    azimuth_rad = math.radians(leg.azimuth)

    # FROM end: use station_lrud if available, else this leg at FROM
    if station_lrud and leg.from_station.name in station_lrud:
        (from_left_e, from_left_n), (from_right_e, from_right_n) = station_lrud[
            leg.from_station.name
        ]
    else:
        (from_left_e, from_left_n), (from_right_e, from_right_n) = (
            _station_left_right_utm(
                leg.from_station.easting,
                leg.from_station.northing,
                azimuth_rad,
                left_m,
                right_m,
            )
        )

    # TO end: use station_lrud if available, else this leg at TO
    if station_lrud and leg.to_station.name in station_lrud:
        (to_left_e, to_left_n), (to_right_e, to_right_n) = station_lrud[
            leg.to_station.name
        ]
    else:
        (to_left_e, to_left_n), (to_right_e, to_right_n) = _station_left_right_utm(
            leg.to_station.easting,
            leg.to_station.northing,
            azimuth_rad,
            left_m,
            right_m,
        )

    try:
        from_left = _cached_utm_to_wgs84(
            from_left_e,
            from_left_n,
            zone,
            northern,
            datum,
            wgs84_cache,
        )
        from_right = _cached_utm_to_wgs84(
            from_right_e,
            from_right_n,
            zone,
            northern,
            datum,
            wgs84_cache,
        )
        to_left = _cached_utm_to_wgs84(
            to_left_e,
            to_left_n,
            zone,
            northern,
            datum,
            wgs84_cache,
        )
        to_right = _cached_utm_to_wgs84(
            to_right_e,
            to_right_n,
            zone,
            northern,
            datum,
            wgs84_cache,
        )
    except InvalidCoordinateError:
        return None

    elev = round((leg.from_station.elevation + leg.to_station.elevation) / 2, 2)

    return Feature(
        geometry=Polygon(
            [
                [
                    (from_left[0], from_left[1], elev),
                    (to_left[0], to_left[1], elev),
                    (to_right[0], to_right[1], elev),
                    (from_right[0], from_right[1], elev),
                    (from_left[0], from_left[1], elev),  # Close polygon
                ]
            ]
        ),
        properties={
            "type": "passage",
            "from": leg.from_station.name,
            "to": leg.to_station.name,
            "left_ft": leg.left,
            "right_ft": leg.right,
            "up_ft": leg.up,
            "down_ft": leg.down,
            "lruds_at_to_station": leg.lruds_at_to_station,
        },
    )


# -----------------------------------------------------------------------------
# Main Conversion Functions
# -----------------------------------------------------------------------------


def survey_to_geojson(
    survey: ComputedSurvey,
    *,
    include_stations: bool = True,
    include_legs: bool = True,
    include_passages: bool = False,
    include_anchors: bool = False,
    color_by_origin: bool = True,
    properties: dict[str, Any] | None = None,
) -> FeatureCollection:
    """Convert computed survey to GeoJSON FeatureCollection.

    Args:
        survey: Computed survey with coordinates
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines
        include_anchors: Include Point features for anchor stations
        color_by_origin: Color stations and legs by their propagation
            origin anchor (default True)

    Returns:
        GeoJSON FeatureCollection
    """
    if survey.utm_zone is None:
        raise ValueError(
            "Cannot convert to GeoJSON: UTM zone is not known. "
            "The MAK file must have a LocationDirective (@) or UTMZoneDirective ($)."
        )

    zone = survey.utm_zone
    northern = survey.utm_northern
    datum = survey.datum or Datum.WGS_1984
    features: list[Feature] = []

    # Coordinate cache: avoids redundant pyproj calls for the same
    # (easting, northing) pair.  Each station appears once as a Point,
    # then again as the endpoint of every leg it touches.
    wgs84_cache: dict[tuple[float, float], tuple[float, float]] = {}

    # Build origin -> colour mapping (stable: sorted anchor names)
    origin_color_map: dict[str, str] = {}
    if color_by_origin:
        origin_names = sorted({s.origin for s in survey.stations.values() if s.origin})
        origin_color_map = {
            name: ORIGIN_COLORS[i % len(ORIGIN_COLORS)]
            for i, name in enumerate(origin_names)
        }

    # Add station points
    if include_stations:
        for name, station in survey.stations.items():
            try:
                feat = station_to_feature(station, zone, northern, datum, wgs84_cache)
                if color_by_origin:
                    color = origin_color_map.get(station.origin)
                    if color:
                        feat["properties"]["marker-color"] = color
                features.append(feat)
            except InvalidCoordinateError:
                logger.warning("Skipping station %s: invalid coordinates", name)

    # Add anchor points
    if include_anchors:
        for name in survey.anchors:
            station = survey.stations.get(name)
            if station is None:
                continue
            try:
                feat = anchor_to_feature(station, zone, northern, datum, wgs84_cache)
                if color_by_origin:
                    color = origin_color_map.get(station.origin)
                    if color:
                        feat["properties"]["marker-color"] = color
                features.append(feat)
            except InvalidCoordinateError:
                logger.warning("Skipping anchor %s: invalid coordinates", name)

    # Add survey legs (skip P-excluded legs — they were used for
    # coordinate propagation but are not rendered).
    if include_legs:
        try:
            for leg in survey.legs:
                if leg.excluded_from_plotting:
                    continue
                feat = leg_to_feature(leg, zone, northern, datum, wgs84_cache)
                if color_by_origin:
                    color = origin_color_map.get(leg.from_station.origin)
                    if color:
                        feat["properties"]["stroke"] = color
                        feat["properties"]["stroke-width"] = 2
                        feat["properties"]["stroke-opacity"] = 1
                features.append(feat)
        except InvalidCoordinateError:
            logger.exception("Invalid leg coordinates")
            raise

    # Add misclosure gap lines.
    # Cross-origin misclosures (same_origin=False) are present only
    # when solver is None — raw BFS shows where propagation fronts
    # disagree.
    # Same-origin misclosures (same_origin=True) are present when a
    # solver was applied — they show the raw loop closure error
    # computed with both paths propagated from the same origin,
    # using the longest path as the "true" segment.
    if include_legs and survey.misclosures:
        for misc in survey.misclosures:
            try:
                ex_lon, ex_lat = utm_to_wgs84(
                    misc.existing.easting,
                    misc.existing.northing,
                    zone,
                    northern,
                    datum,
                )
                gh_lon, gh_lat = utm_to_wgs84(
                    misc.ghost.easting,
                    misc.ghost.northing,
                    zone,
                    northern,
                    datum,
                )

                gap_dist = (
                    (misc.existing.easting - misc.ghost.easting) ** 2
                    + (misc.existing.northing - misc.ghost.northing) ** 2
                    + (misc.existing.elevation - misc.ghost.elevation) ** 2
                ) ** 0.5

                props: dict[str, Any] = {
                    "type": "misclosure",
                    "from": misc.ghost.name,
                    "to": misc.existing.name,
                    "gap_m": round(gap_dist, 2),
                    "file": misc.file,
                    "survey": misc.survey,
                    "stroke": "#ff0000",
                    "stroke-width": 3,
                    "stroke-opacity": 1,
                }

                if misc.same_origin:
                    props["same_origin"] = True
                    # Report the true (longest) and closing (shortest)
                    # segment distances so users can assess the loop.
                    true_dist = max(
                        misc.ghost.path_distance,
                        misc.existing.path_distance,
                    )
                    closing_dist = min(
                        misc.ghost.path_distance,
                        misc.existing.path_distance,
                    )
                    props["true_segment_distance_m"] = round(true_dist, 2)
                    props["closing_segment_distance_m"] = round(closing_dist, 2)

                line_feat = Feature(
                    geometry=LineString(
                        [
                            (gh_lon, gh_lat, round(misc.ghost.elevation, 2)),
                            (ex_lon, ex_lat, round(misc.existing.elevation, 2)),
                        ]
                    ),
                    properties=props,
                )
                features.append(line_feat)

            except InvalidCoordinateError:
                pass

    # Add passage polygons (tunnel segments); clip each new segment to the "outside"
    # of the tunnel so far so overlapping layers are not drawn (collision detection).
    if include_passages:
        station_lrud = _build_station_lrud_map(survey)
        existing_tunnel: ShapelyPolygon | None = None
        for leg in survey.legs:
            if leg.excluded_from_plotting:
                continue
            passage = passage_to_feature(
                leg,
                zone,
                northern,
                datum,
                station_lrud,
                wgs84_cache,
            )
            if not passage:
                continue
            ring = passage["geometry"]["coordinates"][0]
            ring_2d = [(c[0], c[1]) for c in ring]
            segment = ShapelyPolygon(ring_2d)
            if not segment.is_valid or segment.is_empty:
                continue
            if existing_tunnel is not None and existing_tunnel.intersects(segment):
                clipped = segment.difference(existing_tunnel)
                if not clipped.is_empty and clipped.is_valid:
                    elev = ring[0][2]
                    props = dict(passage["properties"])
                    features.extend(_shapely_to_passage_features(clipped, elev, props))
                # Merge full segment into tunnel so next segment is clipped against it
                existing_tunnel = unary_union([existing_tunnel, segment])
            else:
                features.append(passage)
                existing_tunnel = (
                    segment
                    if existing_tunnel is None
                    else unary_union([existing_tunnel, segment])
                )

    # Build properties
    fc_properties = {}
    if survey.utm_zone:
        fc_properties["source_utm_zone"] = survey.utm_zone
    if survey.datum:
        fc_properties["source_datum"] = (
            survey.datum.value if isinstance(survey.datum, Datum) else survey.datum
        )
    if properties:
        fc_properties.update(properties)

    return FeatureCollection(
        features, properties=fc_properties if fc_properties else None
    )


def project_to_geojson(
    project: CompassMakFile,
    *,
    include_stations: bool = True,
    include_legs: bool = True,
    include_passages: bool = False,
    include_anchors: bool = False,
    color_by_origin: bool = True,
    solver: SurveyAdjuster | None = None,
) -> FeatureCollection:
    """Convert a Compass project to GeoJSON.

    This is the high-level function that computes coordinates and generates
    GeoJSON in one step.

    Args:
        project: Loaded CompassMakFile with DAT data
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines
        include_anchors: Include Point features for anchor stations
        color_by_origin: Color stations and legs by propagation origin
        solver: Optional survey adjuster

    Returns:
        GeoJSON FeatureCollection
    """
    survey = compute_survey_coordinates(project, solver=solver)
    return survey_to_geojson(
        survey,
        include_stations=include_stations,
        include_legs=include_legs,
        include_passages=include_passages,
        include_anchors=include_anchors,
        color_by_origin=color_by_origin,
    )


def convert_mak_to_geojson(
    mak_path: Path,
    output_path: Path | None = None,
    *,
    include_stations: bool = True,
    include_legs: bool = True,
    include_passages: bool = False,
    include_anchors: bool = False,
    color_by_origin: bool = True,
    solver: SurveyAdjuster | None = None,
    minify: bool = False,
) -> str:
    """Convert a MAK file (with DAT files) to GeoJSON.

    Args:
        mak_path: Path to the MAK file
        output_path: Optional output path (returns string if None)
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines
        include_anchors: Include Point features for anchor stations
        color_by_origin: Color stations and legs by propagation origin
        solver: Optional survey adjuster
        minify: Omit indentation for compact output

    Returns:
        GeoJSON string
    """

    project = load_project(mak_path)
    geojson = project_to_geojson(
        project,
        include_stations=include_stations,
        include_legs=include_legs,
        include_passages=include_passages,
        include_anchors=include_anchors,
        color_by_origin=color_by_origin,
        solver=solver,
    )

    # Use orjson for fast serialization
    opts = 0 if minify else orjson.OPT_INDENT_2
    json_bytes = orjson.dumps(geojson, option=opts)
    json_str = json_bytes.decode(JSON_ENCODING)

    if output_path:
        output_path.write_text(json_str, encoding=JSON_ENCODING)

    return json_str
