from enum import Enum
from enum import IntEnum
from pathlib import Path
from typing import Self


class CustomEnum(Enum):
    @classmethod
    def reverse(cls, name):
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
    def from_path(cls, filepath: str | Path):
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        return cls.from_str(filepath.suffix.upper()[1:])  # Remove the leading `.`


# ============================== Azimuth ============================== #

# export const azimuthUnits: { [string]: DisplayAzimuthUnit } = {
#   D: 'degrees',
#   Q: 'quads',
#   G: 'gradians',
# }


class AzimuthUnits(CustomEnum):
    DEGREES = "D"
    QUADS = "Q"
    GRADIANS = "G"


# ============================== Inclination Unit ============================== #

# export const inclinationUnits: { [string]: DisplayInclinationUnit } = {
#   D: 'degrees',
#   G: 'percentGrade',
#   M: 'degreesAndMinutes',
#   R: 'gradians',
#   W: 'depthGauge',
# }


class InclinationUnits(CustomEnum):
    DEGREES = "D"
    PERCENT_GRADE = "G"
    DEGREES_AND_MINUTES = "M"
    GRADIANS = "R"
    DEPTH_GAUGE = "W"


# ============================== Length Unit ============================== #


# export const lengthUnits: { [string]: DisplayLengthUnit } = {
#   D: 'decimalFeet',
#   I: 'feetAndInches',
#   M: 'meters',
# }


class LengthUnits(CustomEnum):
    DECIMAL_FEET = "D"
    FEET_AND_INCHES = "I"
    METERS = "M"


# ============================== LRUD ============================== #

# export const lrudItems: { [string]: LrudItem } = {
#   L: 'left',
#   R: 'right',
#   U: 'up',
#   D: 'down',
# }


class LRUD(CustomEnum):
    LEFT = "L"
    RIGHT = "R"
    UP = "U"
    DOWN = "D"


# ============================== ShotItem ============================== #

# export const shotMeasurementItems: { [string]: ShotMeasurementItem } = {
#   L: 'length',
#   A: 'frontsightAzimuth',
#   D: 'frontsightInclination',
#   a: 'backsightAzimuth',
#   d: 'backsightInclination',
# }


class ShotItem(CustomEnum):
    LENGTH = "L"
    FRONTSIGHT_AZIMUTH = "A"
    FRONTSIGHT_INCLINATION = "D"
    BACKSIGHT_AZIMUTH = "a"
    BACKSIGHT_INCLINATION = "d"


# ============================== StationSide ============================== #

# export const stationSides: { [string]: StationSide } = {
#   F: 'from',
#   T: 'to',
# }


class StationSide(CustomEnum):
    FROM = "F"
    TO = "T"


# ============================== ShotFlag ============================== #


class ShotFlag(CustomEnum):
    EXCLUDE_PLOTING = "P"
    EXCLUDE_CLOSURE = "C"
    EXCLUDE_LENGTH = "L"
    TOTAL_EXCLUSION = "X"
    SPLAY = "S"

    __start_token__ = r"#\|"  # noqa: S105
    __end_token__ = r"#"  # noqa: S105
