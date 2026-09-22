# -*- coding: utf-8 -*-
"""Constants used throughout the compass_lib library.

This module centralizes all constant values to ensure consistency
and avoid magic numbers/strings scattered across the codebase.
"""

# -----------------------------------------------------------------------------
# File Encodings
# -----------------------------------------------------------------------------

#: Default encoding for Compass files (Windows-1252 / CP1252)
COMPASS_ENCODING = "cp1252"

#: Encoding used for JSON files
JSON_ENCODING = "utf-8"

#: Bright, saturated palette shared by section colors and origin debug styling.
#: No black, white, gray, brown, or muted shades.
SURVEY_COLORS: tuple[str, ...] = (
    "#ff1744",  # vivid red
    "#ff6d00",  # bright orange
    "#ffea00",  # electric yellow
    "#aaff00",  # lime
    "#00e676",  # spring green
    "#00ffb3",  # bright mint
    "#00e5ff",  # cyan
    "#2979ff",  # electric blue
    "#d500f9",  # purple
    "#ff00a8",  # hot pink
)

#: HSV bounds also enforced when crowded junctions require additional colors.
SURVEY_COLOR_MIN_SATURATION: float = 0.8
SURVEY_COLOR_MIN_VALUE: float = 0.9

#: Encoding used when reading raw Compass files (ASCII with replacements)
ASCII_ENCODING = "ascii"

# -----------------------------------------------------------------------------
# Unit Conversions
# -----------------------------------------------------------------------------

#: Conversion factor from feet to meters
FEET_TO_METERS: float = 0.3048

#: Conversion factor from meters to feet
METERS_TO_FEET: float = 1.0 / FEET_TO_METERS

# -----------------------------------------------------------------------------
# Missing Data Indicators
# -----------------------------------------------------------------------------

#: Values >= this threshold indicate missing data for distances/measurements
MISSING_VALUE_THRESHOLD: float = 990.0

#: Values <= this threshold indicate missing data for angles
MISSING_ANGLE_THRESHOLD: float = -900.0

#: String representation of missing value in formatted output
MISSING_VALUE_STRING: str = "-999.00"

#: Null LRUD values used in PLT files (either 999.0 or 999.9 indicates missing)
NULL_LRUD_VALUES: tuple[float, float] = (999.0, 999.9)

# -----------------------------------------------------------------------------
# Formatting Constants
# -----------------------------------------------------------------------------

#: Width of station name column in DAT files
STATION_NAME_WIDTH: int = 13

#: Width of numeric columns in DAT files
NUMBER_WIDTH: int = 8

#: Decimal precision for GeoJSON coordinates (WGS84)
GEOJSON_COORDINATE_PRECISION: int = 7

#: Decimal precision for elevation values in GeoJSON
GEOJSON_ELEVATION_PRECISION: int = 2

# -----------------------------------------------------------------------------
# Shot Flag Characters
# -----------------------------------------------------------------------------

#: Mapping of shot flags to their character representations
FLAG_CHARS: dict[str, str] = {
    "exclude_distance": "L",
    "exclude_from_plotting": "P",
    "exclude_from_all_processing": "X",
    "do_not_adjust": "C",
}

# -----------------------------------------------------------------------------
# UTM Constants
# -----------------------------------------------------------------------------

#: Southern hemisphere UTM northing offset (10 million meters)
#: Note: This constant represents the false northing added to southern hemisphere
#: UTM coordinates. However, in Compass, hemisphere is determined by the ZONE SIGN
#: (positive = north, negative = south), NOT by comparing northing to this threshold.
#: This constant is kept for reference and potential future use.
UTM_SOUTHERN_HEMISPHERE_OFFSET: float = 10_000_000.0

# -----------------------------------------------------------------------------
# Solver Constraints
# -----------------------------------------------------------------------------

#: Maximum relative change to a shot's tape length during traverse adjustment
#: (0.05 = 5 %).  The solver will never stretch or shrink a shot by more than
#: this fraction of the original survey measurement.
SOLVER_MAX_LENGTH_CHANGE: float = 0.15

#: Maximum relative change to a shot's compass heading during traverse
#: adjustment (0.15 = 15 %).  The solver will never rotate a shot's bearing
#: or inclination by more than this fraction of the original survey reading.
SOLVER_MAX_HEADING_CHANGE: float = 0.15
