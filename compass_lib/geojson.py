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
- C (close exclusion): Ignored (only affects loop closure)
"""

from __future__ import annotations

import datetime
import logging
import math
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

import orjson
import utm
from compass_lib.constants import FEET_TO_METERS
from compass_lib.constants import GEOJSON_COORDINATE_PRECISION
from compass_lib.constants import JSON_ENCODING
from compass_lib.enums import Datum
from compass_lib.geo_utils import GeoLocation
from compass_lib.geo_utils import get_declination
from compass_lib.io import load_project
from geojson import Feature
from geojson import FeatureCollection
from geojson import LineString
from geojson import Point
from geojson import Polygon

if TYPE_CHECKING:
    from pathlib import Path

    from compass_lib.project.models import CompassMakFile
    from compass_lib.survey.models import CompassShot
    from compass_lib.survey.models import CompassTrip

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
    trip: str = ""


@dataclass
class SurveyLeg:
    """A survey leg (shot) between two stations."""

    from_station: Station
    to_station: Station
    distance: float
    azimuth: float | None
    inclination: float | None
    file: str = ""
    trip: str = ""
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None
    lruds_at_to_station: bool = (
        False  # Controls which station LRUDs are associated with
    )


@dataclass
class ComputedSurvey:
    """Computed survey with station coordinates."""

    stations: dict[str, Station] = field(default_factory=dict)
    legs: list[SurveyLeg] = field(default_factory=list)
    utm_zone: int | None = None
    utm_northern: bool = True
    datum: Datum | None = None


# -----------------------------------------------------------------------------
# Coordinate Utilities
# -----------------------------------------------------------------------------


def length_to_meters(length_ft: float) -> float:
    """Convert length from feet to meters."""
    return length_ft * FEET_TO_METERS


def utm_to_wgs84(
    easting: float,
    northing: float,
    zone: int,
    northern: bool = True,
) -> tuple[float, float]:
    """Convert UTM coordinates to WGS84 (longitude, latitude).

    Args:
        easting: UTM easting in meters
        northing: UTM northing in meters
        zone: UTM zone number (1-60 north, -1 to -60 south; absolute value used)
        northern: True if northern hemisphere

    Returns:
        Tuple of (longitude, latitude) in degrees (GeoJSON order)

    Raises:
        InvalidCoordinateError: If conversion fails
    """
    try:
        # utm.to_latlon requires positive zone number
        lat, lon = utm.to_latlon(easting, northing, abs(zone), northern=northern)
        return (
            round(float(lon), GEOJSON_COORDINATE_PRECISION),
            round(float(lat), GEOJSON_COORDINATE_PRECISION),
        )
    except Exception as e:
        raise InvalidCoordinateError(
            f"Failed to convert UTM ({easting}, {northing}) zone {zone}: {e}"
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
) -> GeoLocation:
    """Convert a station's UTM coordinates to WGS84 lat/lon for declination calculation.

    IMPORTANT: Compass stores ALL UTM coordinates in northern hemisphere format,
    regardless of the zone sign. The zone sign only indicates which hemisphere
    the cave is in for grid orientation purposes (convergence corrections).

    Therefore, we ALWAYS use northern=True when converting coordinates to get
    the actual geographic location for declination calculation.

    Args:
        station: Station with UTM coordinates
        utm_zone: UTM zone number (can be negative for southern hemisphere)
        utm_northern: Hemisphere flag (parameter kept for API consistency but not used)

    Returns:
        GeoLocation with actual WGS84 lat/lon coordinates

    Raises:
        InvalidCoordinateError: If conversion fails
    """
    # Always use northern=True because Compass stores all coordinates in northern format
    # The zone sign is only used for convergence/grid orientation, not coordinate storage
    lon, lat = utm_to_wgs84(station.easting, station.northing, utm_zone, northern=True)
    return GeoLocation(latitude=lat, longitude=lon)


def calculate_trip_declination(
    station_location: GeoLocation,
    trip_date: datetime.date | None,
) -> float:
    """Calculate magnetic declination for a survey trip.

    Uses a station location from the trip and the survey date to calculate
    the magnetic declination using the IGRF model. The station location should
    be from an anchor station in the trip's file, or from the current station
    being processed.

    Args:
        station_location: Location of a station from the trip in WGS84
        trip_date: Date of the survey trip

    Returns:
        Declination in degrees (positive = east, negative = west)

    Raises:
        Exception: If declination calculation fails
    """
    try:
        if trip_date is None:
            raise ValueError("Impossible to determine the trip date")  # noqa: TRY301

        # Convert date to datetime for the IGRF calculation
        dt = datetime.datetime(trip_date.year, trip_date.month, trip_date.day)  # noqa: DTZ001
        return get_declination(station_location, dt)

    except Exception:
        logger.exception(
            "Failed to calculate declination for date %s at location (%.4f, %.4f)",
            trip_date,
            station_location.latitude,
            station_location.longitude,
        )
        raise


# -----------------------------------------------------------------------------
# Graph Building
# -----------------------------------------------------------------------------


def build_station_graph(
    project: CompassMakFile,
) -> tuple[
    dict[str, list[tuple[CompassShot, str, str, CompassTrip, bool]]],
    list[tuple[CompassShot, str, str, CompassTrip]],
]:
    """Build adjacency graph from all shots in project.

    Excludes shots that are marked as:
    - excluded_from_all_processing (X flag)
    - excluded_from_plotting (P flag)

    Returns:
        Tuple of (adjacency_dict, all_shots_list)
    """
    all_shots: list[tuple[CompassShot, str, str, CompassTrip]] = []
    adjacency: dict[str, list[tuple[CompassShot, str, str, CompassTrip, bool]]] = {}

    for file_dir in project.file_directives:
        if not file_dir.data:
            continue

        for trip in file_dir.data.trips:
            trip_name = trip.header.survey_name or "unnamed"
            for shot in trip.shots:
                # Skip shots excluded from processing or plotting
                if shot.excluded_from_all_processing:
                    continue
                if shot.excluded_from_plotting:
                    continue

                all_shots.append((shot, file_dir.file, trip_name, trip))

                from_name = shot.from_station_name
                to_name = shot.to_station_name

                if from_name not in adjacency:
                    adjacency[from_name] = []
                if to_name not in adjacency:
                    adjacency[to_name] = []

                # Add forward and reverse connections
                adjacency[from_name].append(
                    (shot, file_dir.file, trip_name, trip, False)
                )
                adjacency[to_name].append((shot, file_dir.file, trip_name, trip, True))

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
    """
    distance = shot.length or 0.0

    # Get azimuth/inclination based on direction
    if is_reverse:
        azimuth = shot.backsight_azimuth
        inclination = shot.backsight_inclination

        if azimuth is not None:
            azimuth = (azimuth + 180.0) % 360.0
        elif shot.frontsight_azimuth is not None:
            azimuth = (shot.frontsight_azimuth + 180.0) % 360.0

        if inclination is not None:
            inclination = -inclination
        elif shot.frontsight_inclination is not None:
            inclination = -shot.frontsight_inclination
    else:
        azimuth = shot.frontsight_azimuth
        inclination = shot.frontsight_inclination

    # Default values
    azimuth = azimuth if azimuth is not None else 0.0
    inclination = inclination if inclination is not None else 0.0

    # Apply declination and convergence
    # Declination: converts magnetic north to true north
    # Convergence: converts true north to UTM grid north
    azimuth_corrected = azimuth + declination - convergence

    # Convert to radians
    azimuth_rad = math.radians(azimuth_corrected)
    inclination_rad = math.radians(inclination)

    # Compute deltas (convert feet to meters)
    distance_m = length_to_meters(distance)
    horizontal_distance = distance_m * math.cos(inclination_rad)
    vertical_distance = distance_m * math.sin(inclination_rad)

    delta_easting = horizontal_distance * math.sin(azimuth_rad)
    delta_northing = horizontal_distance * math.cos(azimuth_rad)

    return Station(
        name=to_name,
        easting=from_station.easting + delta_easting,
        northing=from_station.northing + delta_northing,
        elevation=from_station.elevation + vertical_distance,
    )


def propagate_coordinates(
    project: CompassMakFile,
    anchors: dict[str, Station],
    adjacency: dict[str, list[tuple[CompassShot, str, str, CompassTrip, bool]]],
) -> ComputedSurvey:
    """Propagate coordinates from anchor stations via BFS.

    Declination is calculated per trip using:
    - Project anchor location (from @ directive)
    - Survey date from trip header

    UTM convergence is always applied from the project settings.

    Args:
        project: The Compass project
        anchors: Dictionary of anchor stations with known coordinates
        adjacency: Station adjacency graph

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

    # Cache for trip declinations (calculated once per trip)
    trip_declinations: dict[str, float] = {}

    # Initialize with anchors
    result.stations = dict(anchors)

    if not result.stations:
        # No anchors - use project location or origin for first station
        loc = project.location
        if loc and loc.has_location:
            origin = Station(
                name="__ORIGIN__",
                easting=loc.easting,
                northing=loc.northing,
                elevation=loc.elevation,
            )
        else:
            origin = Station(
                name="__ORIGIN__",
                easting=0.0,
                northing=0.0,
                elevation=0.0,
            )

        # Find first station and place at origin
        if adjacency:
            first_station_name = next(iter(adjacency.keys()))
            result.stations[first_station_name] = Station(
                name=first_station_name,
                easting=origin.easting,
                northing=origin.northing,
                elevation=origin.elevation,
            )

    if not result.stations:
        raise NoKnownAnchorError("No anchor stations found and no shots available")

    logger.info(
        "Starting coordinate propagation from %d anchor(s)", len(result.stations)
    )

    # BFS from anchor stations
    queue: deque[str] = deque(result.stations.keys())
    visited_stations: set[str] = set(result.stations.keys())
    visited_shots: set[tuple[str, str]] = set()

    while queue:
        current_name = queue.popleft()
        current_station = result.stations.get(current_name)
        if not current_station:
            continue

        for shot, file_name, trip_name, trip, is_reverse in adjacency.get(
            current_name, []
        ):
            # Determine direction
            if is_reverse:
                from_name = shot.to_station_name
                to_name = shot.from_station_name
            else:
                from_name = shot.from_station_name
                to_name = shot.to_station_name

            # Skip already processed shots
            shot_key = (min(from_name, to_name), max(from_name, to_name))
            if shot_key in visited_shots:
                continue
            visited_shots.add(shot_key)

            # Calculate declination for this trip (cached)
            trip_key = f"{file_name}:{trip_name}"
            if trip_key not in trip_declinations:
                # Find anchor station for this trip's file (priority 1)
                trip_anchor = None
                for anchor_name, anchor_station in anchors.items():
                    if anchor_station.file == file_name:
                        trip_anchor = anchor_station
                        break

                # Use trip anchor if found, otherwise use current station (priority 2)
                location_station = trip_anchor if trip_anchor else current_station

                # Convert station to WGS84 for declination calculation
                station_wgs84 = get_station_location_wgs84(
                    location_station, result.utm_zone, result.utm_northern
                )

                logger.debug(
                    "Trip %s: using station %s at UTM(%.1f, %.1f) zone=%d northern=%s -> WGS84(%.4f, %.4f)",
                    trip_key,
                    location_station.name,
                    location_station.easting,
                    location_station.northing,
                    result.utm_zone,
                    result.utm_northern,
                    station_wgs84.latitude,
                    station_wgs84.longitude,
                )

                declination = calculate_trip_declination(
                    station_wgs84, trip.header.date
                )
                trip_declinations[trip_key] = declination
                logger.debug(
                    "Trip %s declination: %.2f° (date: %s, station: %s)",
                    trip_key,
                    declination,
                    trip.header.date,
                    location_station.name,
                )
            else:
                declination = trip_declinations[trip_key]

            # Compute new station if needed
            if to_name not in result.stations:
                new_station = compute_next_station(
                    current_station,
                    shot,
                    to_name,
                    is_reverse,
                    declination,
                    convergence,
                )
                new_station.file = file_name
                new_station.trip = trip_name
                result.stations[to_name] = new_station

                if to_name not in visited_stations:
                    visited_stations.add(to_name)
                    queue.append(to_name)

            # Create leg
            from_station = result.stations.get(from_name)
            to_station = result.stations.get(to_name)

            if from_station and to_station:
                # LRUD association based on O/T flags
                # If lruds_at_to_station is True, associate LRUDs with TO station
                # Otherwise (default), associate with FROM station
                leg = SurveyLeg(
                    from_station=from_station,
                    to_station=to_station,
                    distance=shot.length or 0.0,
                    azimuth=shot.frontsight_azimuth,
                    inclination=shot.frontsight_inclination,
                    file=file_name,
                    trip=trip_name,
                    left=shot.left,
                    right=shot.right,
                    up=shot.up,
                    down=shot.down,
                    lruds_at_to_station=lruds_at_to_station,
                )
                result.legs.append(leg)

    logger.info(
        "Computed %d stations and %d legs",
        len(result.stations),
        len(result.legs),
    )

    return result


def compute_survey_coordinates(project: CompassMakFile) -> ComputedSurvey:
    """Compute station coordinates from survey data.

    This is the main entry point for coordinate computation.

    Args:
        project: Loaded CompassMakFile with DAT data

    Returns:
        ComputedSurvey with station coordinates and legs
    """
    adjacency, _ = build_station_graph(project)
    anchors = find_anchor_stations(project)
    return propagate_coordinates(project, anchors, adjacency)


# -----------------------------------------------------------------------------
# GeoJSON Feature Creation
# -----------------------------------------------------------------------------


def station_to_feature(
    station: Station,
    zone: int,
    northern: bool,
) -> Feature:
    """Convert a station to a GeoJSON Point Feature.

    Args:
        station: Station with coordinates
        zone: UTM zone number
        northern: True if northern hemisphere

    Returns:
        GeoJSON Feature with Point geometry
    """
    lon, lat = utm_to_wgs84(station.easting, station.northing, zone, northern)

    return Feature(
        geometry=Point((lon, lat, round(station.elevation, 2))),
        properties={
            "type": "station",
            "name": station.name,
            "file": station.file,
            "trip": station.trip,
            "elevation_m": round(station.elevation, 2),
        },
    )


def leg_to_feature(
    leg: SurveyLeg,
    zone: int,
    northern: bool,
) -> Feature:
    """Convert a survey leg to a GeoJSON LineString Feature.

    Args:
        leg: Survey leg with from/to stations
        zone: UTM zone number
        northern: True if northern hemisphere

    Returns:
        GeoJSON Feature with LineString geometry
    """
    from_lon, from_lat = utm_to_wgs84(
        leg.from_station.easting, leg.from_station.northing, zone, northern
    )
    to_lon, to_lat = utm_to_wgs84(
        leg.to_station.easting, leg.to_station.northing, zone, northern
    )

    return Feature(
        geometry=LineString(
            [
                (from_lon, from_lat, round(leg.from_station.elevation, 2)),
                (to_lon, to_lat, round(leg.to_station.elevation, 2)),
            ]
        ),
        properties={
            "type": "leg",
            "from": leg.from_station.name,
            "to": leg.to_station.name,
            "distance_ft": leg.distance,
            "distance_m": round(length_to_meters(leg.distance), 2)
            if leg.distance
            else None,
            "azimuth": leg.azimuth,
            "inclination": leg.inclination,
            "file": leg.file,
            "trip": leg.trip,
        },
    )


def passage_to_feature(
    leg: SurveyLeg,
    zone: int,
    northern: bool,
) -> Feature | None:
    """Convert LRUD data to a passage polygon Feature.

    The LRUD values are applied at either the FROM or TO station based on
    the lruds_at_to_station flag (controlled by O/T project flags).

    Args:
        leg: Survey leg with LRUD data
        zone: UTM zone number
        northern: True if northern hemisphere

    Returns:
        GeoJSON Feature with Polygon geometry, or None if no LRUD data
    """
    if leg.left is None and leg.right is None:
        return None

    if leg.azimuth is None:
        return None

    left_m = length_to_meters(leg.left or 0.0)
    right_m = length_to_meters(leg.right or 0.0)

    # Perpendicular direction
    azimuth_rad = math.radians(leg.azimuth)
    perp_rad = azimuth_rad + math.pi / 2

    # Determine which station the LRUDs are associated with
    if leg.lruds_at_to_station:
        # LRUDs are at the TO station - apply full LRUD width at TO,
        # and taper to zero at FROM
        from_left_e = leg.from_station.easting
        from_left_n = leg.from_station.northing
        from_right_e = leg.from_station.easting
        from_right_n = leg.from_station.northing

        to_left_e = leg.to_station.easting + left_m * math.sin(perp_rad)
        to_left_n = leg.to_station.northing + left_m * math.cos(perp_rad)
        to_right_e = leg.to_station.easting - right_m * math.sin(perp_rad)
        to_right_n = leg.to_station.northing - right_m * math.cos(perp_rad)
    else:
        # LRUDs are at the FROM station (default) - apply full LRUD width at FROM,
        # and taper to zero at TO
        from_left_e = leg.from_station.easting + left_m * math.sin(perp_rad)
        from_left_n = leg.from_station.northing + left_m * math.cos(perp_rad)
        from_right_e = leg.from_station.easting - right_m * math.sin(perp_rad)
        from_right_n = leg.from_station.northing - right_m * math.cos(perp_rad)

        to_left_e = leg.to_station.easting
        to_left_n = leg.to_station.northing
        to_right_e = leg.to_station.easting
        to_right_n = leg.to_station.northing

    try:
        from_left = utm_to_wgs84(from_left_e, from_left_n, zone, northern)
        from_right = utm_to_wgs84(from_right_e, from_right_n, zone, northern)
        to_left = utm_to_wgs84(to_left_e, to_left_n, zone, northern)
        to_right = utm_to_wgs84(to_right_e, to_right_n, zone, northern)
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
    properties: dict[str, Any] | None = None,
) -> FeatureCollection:
    """Convert computed survey to GeoJSON FeatureCollection.

    Args:
        survey: Computed survey with coordinates
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines

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
    features: list[Feature] = []

    # Add station points
    if include_stations:
        for name, station in survey.stations.items():
            if name.startswith("__"):
                continue  # Skip internal markers

            try:
                features.append(station_to_feature(station, zone, northern))
            except InvalidCoordinateError:
                logger.warning("Skipping station %s: invalid coordinates", name)

    # Add survey legs
    if include_legs:
        try:
            features.extend(leg_to_feature(leg, zone, northern) for leg in survey.legs)
        except InvalidCoordinateError:
            logger.exception("Invalid leg coordinates")
            raise

    # Add passage polygons
    if include_passages:
        for leg in survey.legs:
            passage = passage_to_feature(leg, zone, northern)
            if passage:
                features.append(passage)

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
) -> FeatureCollection:
    """Convert a Compass project to GeoJSON.

    This is the high-level function that computes coordinates and generates
    GeoJSON in one step.

    Args:
        project: Loaded CompassMakFile with DAT data
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines

    Returns:
        GeoJSON FeatureCollection
    """
    survey = compute_survey_coordinates(project)
    return survey_to_geojson(
        survey,
        include_stations=include_stations,
        include_legs=include_legs,
        include_passages=include_passages,
    )


def convert_mak_to_geojson(
    mak_path: Path,
    output_path: Path | None = None,
    *,
    include_stations: bool = True,
    include_legs: bool = True,
    include_passages: bool = False,
) -> str:
    """Convert a MAK file (with DAT files) to GeoJSON.

    Args:
        mak_path: Path to the MAK file
        output_path: Optional output path (returns string if None)
        include_stations: Include Point features for stations
        include_legs: Include LineString features for survey legs
        include_passages: Include Polygon features for passage outlines

    Returns:
        GeoJSON string
    """

    project = load_project(mak_path)
    geojson = project_to_geojson(
        project,
        include_stations=include_stations,
        include_legs=include_legs,
        include_passages=include_passages,
    )

    # Use orjson for fast serialization
    json_bytes = orjson.dumps(geojson, option=orjson.OPT_INDENT_2)
    json_str = json_bytes.decode(JSON_ENCODING)

    if output_path:
        output_path.write_text(json_str, encoding=JSON_ENCODING)

    return json_str
