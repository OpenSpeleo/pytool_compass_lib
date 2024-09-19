from enum import Enum


class CustomEnum(Enum):
    @classmethod
    def reverse(cls, name):
        return cls._value2member_map_[name]

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

    __start_token__ = r"#\|"
    __end_token__ = r"#"



if __name__ == "__main__":
    print(StationSide.FROM.value)
    print(StationSide.reverse("F"))
