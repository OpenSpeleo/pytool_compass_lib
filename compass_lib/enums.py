"""
For more details, refer to:
https://fountainware.com/compass/HTML_Help/Compass_Editor/surveyfileformat.htm
"""

from __future__ import annotations

import math
from enum import Enum
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Any
    from typing_extensions import Self


class CustomEnum(Enum):
    @classmethod
    def reverse(cls, name: Any) -> Enum:
        return cls._value2member_map_[name]


class CompassFileType(IntEnum):
    DAT = 0
    MAK = 1
    PLT = 2

    @classmethod
    def from_str(cls, value: str) -> Self:
        try:
            return cls[value.upper()]
        except KeyError as e:
            raise ValueError(f"Unknown value: {value.upper()}") from e

    @classmethod
    def from_path(cls, filepath: str | Path) -> Self:
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        return cls.from_str(filepath.suffix.upper()[1:])  # Remove the leading `.`


# ============================== Bearing ============================== #

# I.	Bearing Units: D = Degrees, Q = quads, R = Grads


class BearingUnits(CustomEnum):
    DEGREES = "D"
    QUADS = "Q"
    GRADIANS = "R"

    def normalize(self, value: float) -> float:
        "Normalize the unit to `degrees`"
        match self:
            case BearingUnits.DEGREES:
                return value
            case BearingUnits.GRADIANS:
                # 1 grad = 0.9 degrees
                return value * 0.9
            case BearingUnits.QUADS:
                raise NotImplementedError("BearingUnits.QUADS not supported")
            case _:
                raise ValueError(f"Unknown value received: `{value}`")


# ============================== Length Unit ============================== #

# Length Units: D = Decimal Feet, I = Feet and Inches M = Meters


class LengthUnits(CustomEnum):
    DECIMAL_FEET = "D"
    FEET_AND_INCHES = "I"
    METERS = "M"

    def normalize(self, value: float) -> float:
        "Normalize the unit to `feet` or `meters`"
        match self:
            case LengthUnits.DECIMAL_FEET | LengthUnits.METERS:
                return value
            case LengthUnits.FEET_AND_INCHES:
                raise NotImplementedError("LengthUnits.FEET_AND_INCHES not supported")
            case _:
                raise ValueError(f"Unknown value received: `{value}`")


# ============================== Inclination Unit ============================== #

# 	Inclination Units: D = Degrees, G = Percent Grade M = Degrees and Minutes, R = Grads W = Depth Gauge  # noqa: E501


class InclinationUnits(CustomEnum):
    DEGREES = "D"
    PERCENT_GRADE = "G"
    DEGREES_AND_MINUTES = "M"
    GRADIANS = "R"
    DEPTH_GAUGE = "W"

    def normalize(self, value: float) -> float:
        "Normalize the unit to `degrees`"
        match self:
            case InclinationUnits.DEGREES:
                return value
            case InclinationUnits.PERCENT_GRADE:
                # degrees = arctan(percent_grade​ / 100) * (180/pi)​
                return math.degrees(math.atan(value / 100))
            case InclinationUnits.DEGREES_AND_MINUTES:
                raise NotImplementedError(
                    "InclinationUnits.DEGREES_AND_MINUTES not supported"
                )
                return value
            case InclinationUnits.GRADIANS:
                # 1 grad = 0.9 degrees
                return value * 0.9
            case InclinationUnits.DEPTH_GAUGE:
                # Delta or Absolute Depth - Not sure, probably absolute
                raise NotImplementedError("InclinationUnits.DEPTH_GAUGE not supported")
            case _:
                raise ValueError(f"Unknown value received: `{value}`")


# ============================== LRUD ============================== #

# LRUD: L = Left, R = Right, U = Up, D = Down


class LRUD(CustomEnum):
    LEFT = "L"
    RIGHT = "R"
    UP = "U"
    DOWN = "D"


# ============================== ShotItem ============================== #

# Shot Item Order: L = Length, A = Azimuth, D = Inclination, a = Back Azimuth, d = Back Inclination  # noqa: E501


class ShotItem(CustomEnum):
    LENGTH = "L"
    FRONTSIGHT_AZIMUTH = "A"
    FRONTSIGHT_INCLINATION = "D"
    BACKSIGHT_AZIMUTH = "a"
    BACKSIGHT_INCLINATION = "d"


# ============================== ShotItem ============================== #

# Backsight: B=Redundant, N or empty=No Redundant Backsights.


class Backsight(CustomEnum):
    REDUNDANT = "B"
    NONE = "N"


# ============================== LRUDAssociation ============================== #

# LRUD Association: F=From Station, T=To Station


class LRUDAssociation(CustomEnum):
    FROM_STATION = "F"
    TO_STATION = "T"


# ============================== ShotFlag ============================== #


class ShotFlag(CustomEnum):
    EXCLUDE_PLOTING = "P"
    EXCLUDE_CLOSURE = "C"
    EXCLUDE_LENGTH = "L"
    TOTAL_EXCLUSION = "X"
    SPLAY = "S"

    __start_token__ = r"#\|"  # noqa: S105
    __end_token__ = r"#"  # noqa: S105
