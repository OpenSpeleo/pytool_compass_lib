# -*- coding: utf-8 -*-
"""Enumerations for Compass file formats.

This module contains all enumerations used in Compass survey data formats,
including units for measurements, file types, and various classification types.
"""

from enum import Enum
from math import radians
from math import tan

from compass_lib.constants import FEET_TO_METERS


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
            CompassFileType.DAT: FileExtension.DAT.value,
            CompassFileType.MAK: FileExtension.MAK.value,
            CompassFileType.PLT: FileExtension.PLT.value,
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


class FileExtension(str, Enum):
    """File extensions for various file formats (with dot).

    Attributes:
        DAT: Compass survey data file extension
        MAK: Compass project/make file extension
        PLT: Compass plot file extension
        JSON: JSON file extension
        GEOJSON: GeoJSON file extension
    """

    DAT = ".dat"
    MAK = ".mak"
    PLT = ".plt"
    JSON = ".json"
    GEOJSON = ".geojson"


class FormatIdentifier(str, Enum):
    """Format identifiers used in JSON files.

    Attributes:
        COMPASS_DAT: Format identifier for DAT files in JSON
        COMPASS_MAK: Format identifier for MAK/project files in JSON
    """

    COMPASS_DAT = "compass_dat"
    COMPASS_MAK = "compass_mak"


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
        DEPTH_GAUGE: Delta depth (From_depth - To_depth) for underwater surveys.
            Negative = descending (going deeper), positive = ascending.
            Uses the same units as length measurements.
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


class Datum(str, Enum):
    """Geodetic datum values supported by Compass.

    These are the standard datum values that can be used in MAK project files.
    The enum values match the exact strings used in Compass MAK files.

    Attributes:
        ADINDAN: Adindan datum
        ARC_1950: Arc 1950 datum
        ARC_1960: Arc 1960 datum
        AUSTRALIAN_1966: Australian 1966 datum
        AUSTRALIAN_1984: Australian 1984 datum
        CAMP_AREA_ASTRO: Camp Area Astro datum
        CAPE: Cape datum
        EUROPEAN_1950: European 1950 datum
        EUROPEAN_1979: European 1979 datum
        GEODETIC_1949: Geodetic 1949 datum
        HONG_KONG_1963: Hong Kong 1963 datum
        HU_TZU_SHAN: Hu Tzu Shan datum
        INDIAN: Indian datum
        NORTH_AMERICAN_1927: North American 1927 datum (NAD27)
        NORTH_AMERICAN_1983: North American 1983 datum (NAD83)
        OMAN: Oman datum
        ORDNANCE_SURVEY_1936: Ordnance Survey 1936 datum
        PULKOVO_1942: Pulkovo 1942 datum
        SOUTH_AMERICAN_1956: South American 1956 datum
        SOUTH_AMERICAN_1969: South American 1969 datum
        TOKYO: Tokyo datum
        WGS_1972: WGS 1972 datum
        WGS_1984: WGS 1984 datum
    """

    ADINDAN = "Adindan"
    ARC_1950 = "Arc 1950"
    ARC_1960 = "Arc 1960"
    AUSTRALIAN_1966 = "Australian 1966"
    AUSTRALIAN_1984 = "Australian 1984"
    CAMP_AREA_ASTRO = "Camp Area Astro"
    CAPE = "Cape"
    EUROPEAN_1950 = "European 1950"
    EUROPEAN_1979 = "European 1979"
    GEODETIC_1949 = "Geodetic 1949"
    HONG_KONG_1963 = "Hong Kong 1963"
    HU_TZU_SHAN = "Hu Tzu Shan"
    INDIAN = "Indian"
    NORTH_AMERICAN_1927 = "North American 1927"
    NORTH_AMERICAN_1983 = "North American 1983"
    OMAN = "Oman"
    ORDNANCE_SURVEY_1936 = "Ordnance Survey 1936"
    PULKOVO_1942 = "Pulkovo 1942"
    SOUTH_AMERICAN_1956 = "South American 1956"
    SOUTH_AMERICAN_1969 = "South American 1969"
    TOKYO = "Tokyo"
    WGS_1972 = "WGS 1972"
    WGS_1984 = "WGS 1984"

    @classmethod
    def normalize(cls, value: str | None) -> "Datum | None":
        """Normalize and validate a datum string to a Datum enum value.

        Performs case-insensitive matching with whitespace normalization.

        Args:
            value: The datum string to normalize (case-insensitive)

        Returns:
            The corresponding Datum enum value, or None if value is None

        Raises:
            ValueError: If the datum string is not recognized
        """
        if value is None:
            return None

        # Normalize: lowercase, strip whitespace, collapse multiple spaces
        normalized = " ".join(value.strip().lower().split())

        # Match against enum values (case-insensitive)
        for datum in cls:
            if datum.value.lower() == normalized:
                return datum

        raise ValueError(f"Unknown datum: {value!r}")

    @classmethod
    def from_string(cls, value: str | None) -> "Datum | None":
        """Alias for normalize() for backwards compatibility."""
        return cls.normalize(value)
