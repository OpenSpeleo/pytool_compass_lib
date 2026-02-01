# -*- coding: utf-8 -*-
"""Enumerations for Compass file formats.

This module contains all enumerations used in Compass survey data formats,
including units for measurements, file types, and various classification types.
"""

from enum import Enum
from math import radians
from math import tan

from compass_scratchpad.constants import EXT_DAT
from compass_scratchpad.constants import EXT_GEOJSON
from compass_scratchpad.constants import EXT_JSON
from compass_scratchpad.constants import EXT_MAK
from compass_scratchpad.constants import EXT_PLT
from compass_scratchpad.constants import FEET_TO_METERS


class FileFormat(str, Enum):
    """File format types for conversion operations.

    Attributes:
        COMPASS: Native Compass binary/text format (.dat, .mak, .plt)
        JSON: JSON serialization format
        GEOJSON: GeoJSON geographic format
    """

    COMPASS = "compass"
    JSON = "json"
    GEOJSON = "geojson"


class CompassFileType(str, Enum):
    """Types of Compass files.

    Attributes:
        DAT: Survey data file containing shots
        MAK: Project/make file linking DAT files
        PLT: Plot file with processed survey data
    """

    DAT = "dat"
    MAK = "mak"
    PLT = "plt"

    @property
    def extension(self) -> str:
        """Get the file extension for this type (with dot)."""
        return {
            CompassFileType.DAT: EXT_DAT,
            CompassFileType.MAK: EXT_MAK,
            CompassFileType.PLT: EXT_PLT,
        }[self]

    @classmethod
    def from_extension(cls, ext: str) -> "CompassFileType | None":
        """Get file type from extension.

        Args:
            ext: File extension (with or without dot, case-insensitive)

        Returns:
            CompassFileType or None if not recognized
        """
        ext_lower = ext.lower().lstrip(".")
        mapping = {
            "dat": cls.DAT,
            "mak": cls.MAK,
            "plt": cls.PLT,
        }
        return mapping.get(ext_lower)


class AzimuthUnit(str, Enum):
    """Unit for compass azimuth (bearing) measurements.

    Attributes:
        DEGREES: Standard degrees (0-360)
        QUADS: Quadrant notation
        GRADS: Gradians (400 per circle)
    """

    DEGREES = "D"
    QUADS = "Q"
    GRADS = "R"

    @staticmethod
    def convert(degrees: float | None, to_unit: "AzimuthUnit") -> float | None:
        """Convert degrees to the target unit.

        Args:
            degrees: Value in degrees (or None)
            to_unit: Target unit to convert to

        Returns:
            Converted value or None if input is None
        """
        if degrees is None:
            return None
        if to_unit == AzimuthUnit.GRADS:
            return degrees * 400 / 360
        return degrees


class InclinationUnit(str, Enum):
    """Unit for vertical angle (inclination) measurements.

    Attributes:
        DEGREES: Standard degrees (-90 to +90)
        PERCENT_GRADE: Percentage gradient (tan(angle) * 100)
        DEGREES_AND_MINUTES: Degrees with minutes notation
        GRADS: Gradians
        DEPTH_GAUGE: Depth gauge reading
    """

    DEGREES = "D"
    PERCENT_GRADE = "G"
    DEGREES_AND_MINUTES = "M"
    GRADS = "R"
    DEPTH_GAUGE = "W"

    @staticmethod
    def convert(value: float | None, to_unit: "InclinationUnit") -> float | None:
        """Convert degrees to the target unit.

        Args:
            value: Value in degrees (or None)
            to_unit: Target unit to convert to

        Returns:
            Converted value or None if input is None
        """
        if value is None:
            return None
        if to_unit == InclinationUnit.PERCENT_GRADE:
            return tan(radians(value)) * 100
        if to_unit == InclinationUnit.GRADS:
            return value * 200 / 180
        return value


class LengthUnit(str, Enum):
    """Unit for distance measurements.

    Attributes:
        DECIMAL_FEET: Standard feet with decimals
        FEET_AND_INCHES: Feet and inches notation
        METERS: Metric meters
    """

    DECIMAL_FEET = "D"
    FEET_AND_INCHES = "I"
    METERS = "M"

    @staticmethod
    def convert(feet: float | None, to_unit: "LengthUnit") -> float | None:
        """Convert feet to the target unit.

        Args:
            feet: Value in feet (or None)
            to_unit: Target unit to convert to

        Returns:
            Converted value or None if input is None
        """
        if feet is None:
            return None
        if to_unit == LengthUnit.METERS:
            return feet * FEET_TO_METERS
        return feet


class LrudAssociation(str, Enum):
    """Indicates which station LRUD measurements are associated with.

    Attributes:
        FROM: LRUD measured at the FROM station
        TO: LRUD measured at the TO station
    """

    FROM = "F"
    TO = "T"


class LrudItem(str, Enum):
    """Individual LRUD dimension identifiers.

    Attributes:
        LEFT: Distance to left wall
        RIGHT: Distance to right wall
        UP: Distance to ceiling
        DOWN: Distance to floor
    """

    LEFT = "L"
    RIGHT = "R"
    UP = "U"
    DOWN = "D"


class ShotItem(str, Enum):
    """Components of a shot measurement for format ordering.

    Attributes:
        LENGTH: Distance between stations
        FRONTSIGHT_AZIMUTH: Compass bearing forward
        FRONTSIGHT_INCLINATION: Vertical angle forward
        BACKSIGHT_AZIMUTH: Compass bearing backward
        BACKSIGHT_INCLINATION: Vertical angle backward
    """

    LENGTH = "L"
    FRONTSIGHT_AZIMUTH = "A"
    FRONTSIGHT_INCLINATION = "D"
    BACKSIGHT_AZIMUTH = "a"
    BACKSIGHT_INCLINATION = "d"


class Severity(str, Enum):
    """Severity level for parse errors.

    Attributes:
        ERROR: Critical parsing error
        WARNING: Non-fatal warning
    """

    ERROR = "error"
    WARNING = "warning"


class DrawOperation(str, Enum):
    """Drawing operations for plot commands.

    Attributes:
        MOVE_TO: Move to location without drawing
        LINE_TO: Draw line to location
    """

    MOVE_TO = "M"
    LINE_TO = "D"
