# -*- coding: utf-8 -*-
"""Constants used throughout the compass_scratchpad library.

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
# File Extensions (lowercase, with dot)
# -----------------------------------------------------------------------------

#: Compass survey data file extension
EXT_DAT: str = ".dat"

#: Compass project/make file extension
EXT_MAK: str = ".mak"

#: Compass plot file extension
EXT_PLT: str = ".plt"

#: JSON file extension
EXT_JSON: str = ".json"

#: GeoJSON file extension
EXT_GEOJSON: str = ".geojson"

# -----------------------------------------------------------------------------
# Format Identifiers (used in JSON files)
# -----------------------------------------------------------------------------

#: Format identifier for DAT files in JSON
FORMAT_COMPASS_DAT: str = "compass_dat"

#: Format identifier for MAK/project files in JSON
FORMAT_COMPASS_MAK: str = "compass_mak"

#: Alternative format identifier for MAK files (legacy)
FORMAT_COMPASS_PROJECT: str = "compass_project"

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

#: Southern hemisphere UTM northing offset
UTM_SOUTHERN_HEMISPHERE_OFFSET: float = 10_000_000.0
