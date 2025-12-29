from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any
from typing import Literal
from typing import Self

import pyIGRF14 as pyIGRF
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PastDate
from pydantic import field_validator

from compass_lib.constants import COMPASS_END_OF_FILE
from compass_lib.constants import COMPASS_SECTION_SEPARATOR
from compass_lib.encoding import EnhancedJSONEncoder
from compass_lib.enums import LRUD
from compass_lib.enums import Backsight
from compass_lib.enums import BearingUnits
from compass_lib.enums import InclinationUnits
from compass_lib.enums import LengthUnits
from compass_lib.enums import LRUDAssociation
from compass_lib.enums import ShotFlag
from compass_lib.enums import ShotItem
from compass_lib.utils import decimal_year

if TYPE_CHECKING:
    from io import TextIOWrapper
    from typing import Any


# from compass_lib.errors import DuplicateValueError
class DeclinationObj(BaseModel):
    survey_date: PastDate
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    @property
    def declination(self) -> float:
        declination: float = pyIGRF.igrf_value(  # type: ignore[attr-defined,no-untyped-call]
            self.latitude,
            self.longitude,
            alt=0.0,
            year=decimal_year(
                datetime.datetime.combine(
                    self.survey_date,
                    datetime.datetime.min.time(),
                )
            ),
        )[0]
        return round(declination, 2)


class SurveyShot(BaseModel):
    from_: Annotated[
        str, Field(serialization_alias="from", min_length=1, max_length=32)
    ]
    to: Annotated[str, Field(min_length=1, max_length=32)]

    azimuth: Annotated[float, Field(ge=0, lt=360)]

    inclination: Annotated[float, Field(ge=-90, le=90)]
    length: Annotated[float, Field(ge=0)]

    # Optional Values
    flags: Annotated[str, Field(max_length=5)] | None = None
    comment: Annotated[str, Field(max_length=256)] | None = None

    azimuth2: Annotated[float, Field(ge=0, lt=360)] | None = None
    inclination2: Annotated[float, Field(ge=-90, le=90)] | None = None

    # LRUD
    left: Annotated[float, Field(ge=0)] | None = None
    right: Annotated[float, Field(ge=0)] | None = None
    up: Annotated[float, Field(ge=0)] | None = None
    down: Annotated[float, Field(ge=0)] | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("azimuth", "inclination", mode="before")
    @classmethod
    def parse_numeric_str(cls, v: Any) -> float | None:
        if v in ("", None):
            return None

        try:
            return float(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Expected numeric or empty value, got {v!r}") from e

    @field_validator(
        "left",
        "right",
        "up",
        "down",
        "azimuth2",
        "inclination2",
        mode="before",
    )
    @classmethod
    def validate_optional(cls, value: Any | None) -> float | None:
        if (value := cls.parse_numeric_str(value)) is None:
            return None

        return value if value > 0 else None

    @field_validator("flags", mode="before")
    @classmethod
    def normalize_flags(cls, v: Any) -> str | None:
        if v is None:
            return v

        if not isinstance(v, str):
            raise TypeError("flags must be a string")

        # Remove Start & Stop Tokens
        v = v.lstrip(ShotFlag.__start_token__)
        v = v.rstrip(ShotFlag.__end_token__)

        # Verify flag validity
        allowed_flags = {flag.value for flag in ShotFlag}
        chars = list(v.strip())

        if not all(c in allowed_flags for c in chars):
            invalid = [c for c in chars if c not in allowed_flags]
            raise ValueError(f"Invalid flag characters: {invalid}")

        # Sort alphabetically & remove duplicates for consistency
        return "".join(sorted(set(chars)))

    def export_to_dat(self, fp: TextIOWrapper) -> None:
        fp.write(f"{self.from_: >12} ")
        fp.write(f"{self.to: >12} ")
        fp.write(f"{self.length:8.2f} ")
        fp.write(f"{self.azimuth:8.2f} ")
        fp.write(f"{self.inclination:8.3f} ")
        fp.write(f"{left if (left := self.left) else -9999.0:8.2f} ")
        fp.write(f"{up if (up := self.up) else -9999.0:8.2f} ")
        fp.write(f"{down if (down := self.down) else -9999.0:8.2f} ")
        fp.write(f"{right if (right := self.right) else -9999.0:8.2f} ")
        fp.write(f"{azm2 if (azm2 := self.azimuth2) else -9999.0:8.2f} ")
        fp.write(f"{inc2 if (inc2 := self.inclination2) else -9999.0:8.2f} ")
        if self.flags is not None and self.flags != "":
            escaped_start_token = str(ShotFlag.__start_token__).replace("\\", "")
            fp.write(f" {escaped_start_token}{self.flags}{ShotFlag.__end_token__}")
        if self.comment is not None:
            fp.write(f" {self.comment}")
        fp.write("\n")

    # ======================== VALIDATOR UTILS ======================== #

    # @classmethod
    # def validate_unique(cls, field: str, values: list) -> list:
    #     vals2check = [getattr(val, field) for val in values]
    #     dupl_vals = list(duplicates(vals2check))
    #     if dupl_vals:
    #         raise DuplicateValueError(
    #             f"[{cls.__name__}] Duplicate value found for `{field}`: "
    #             f"{dupl_vals}"
    #         )
    #     return values

    # @field_validator("to", mode="before")
    # @classmethod
    # def validate_unique_to(cls, value: str | None) -> str:
    #     """Note: Validators are only ran with custom fed values.
    #     Not autogenerated ones. Hence we need to register the name."""

    #     if value is None or value == "":
    #         return cls.to.default_factory()

    #     # 1. Verify the name is only composed of valid chars.
    #     for char in value:
    #         if char.upper() not in [
    #             *UniqueNameGenerator.VOCAB,
    #             *list("_-~:!?.'()[]{}@*&#%|$")
    #         ]:
    #             raise ValueError(f"The character `{char}` is not allowed as `name`.")

    #     if len(value) > COMPASS_MAX_NAME_LENGTH:
    #         raise ValueError(f"Name {value} is too long, maximum allowed: "
    #                          f"{COMPASS_MAX_NAME_LENGTH}")

    #     UniqueNameGenerator.register(value=value)
    #     return value


class CompassFormat(BaseModel):
    """Parses and represents the Compass FORMAT string."""

    bearing_units: BearingUnits
    length_units: LengthUnits
    passage_units: LengthUnits
    inclination_units: InclinationUnits
    lrud_order: list[LRUD]
    shot_order: list[ShotItem]
    backsight: Backsight | None = None
    lrud_association: LRUDAssociation | None = None
    version: Annotated[
        Literal[11, 12, 13, 15],
        Field(exclude=True),
    ]

    @classmethod
    def from_string(cls, fmt: str) -> Self:
        """Create a Format model from a FORMAT string."""
        if not re.match(r"^[A-Za-z]{11,15}$", fmt):
            raise ValueError(
                f"The value received is not a valid Compass Format: `{fmt}`"
            )

        version = 11

        # Assign components
        bearing = BearingUnits(fmt[0])
        length = LengthUnits(fmt[1])
        passage = LengthUnits(fmt[2])
        inclination = InclinationUnits(fmt[3])
        lrud_order = [LRUD(c) for c in fmt[4:8]]
        shot_order = [ShotItem(c) for c in fmt[8:11]]

        backsight = None
        lrud_assoc = None

        match len(fmt):
            case 11:
                pass
            case 12:
                version = 12
                backsight = Backsight(fmt[11])
            case 13:
                version = 13
                backsight = Backsight(fmt[11])
                lrud_assoc = LRUDAssociation(fmt[12])
            case 15:
                version = 15
                shot_order.extend([ShotItem(fmt[idx]) for idx in [11, 12]])
                backsight = Backsight(fmt[13])
                lrud_assoc = LRUDAssociation(fmt[14])
            case _:
                raise ValueError(f"Invalid format length received: {len(fmt)}")

        return cls(
            bearing_units=bearing,
            length_units=length,
            passage_units=passage,
            inclination_units=inclination,
            lrud_order=lrud_order,
            shot_order=shot_order,
            backsight=backsight,
            lrud_association=lrud_assoc,
            version=version,
        )


class SurveySection(BaseModel):
    cave_name: str
    name: Annotated[str, Field(min_length=1, max_length=256)]
    comment: Annotated[str, Field(max_length=512)] = ""
    correction: Annotated[list[float], Field(min_length=3, max_length=3)] = [
        0.0,
        0.0,
        0.0,
    ]
    correction2: Annotated[list[float], Field(min_length=2, max_length=2)] = [0.0, 0.0]
    survey_date: PastDate
    discovery_date: PastDate | None = None
    declination: Annotated[float, Field(..., ge=-90.0, le=90.0)]

    format: Annotated[CompassFormat | None, Field(exclude=True)] = None
    unit: Literal["feet", "meters"]

    survey_team: Annotated[list[str], Field(min_length=0)]

    shots: Annotated[list[SurveyShot], Field(min_length=1)]

    model_config = ConfigDict(extra="forbid")

    @field_validator("format", mode="before")
    @classmethod
    def parse_format(cls, v: Any) -> CompassFormat | Any:
        if isinstance(v, str):
            return CompassFormat.from_string(v)
        return v

    @field_validator("survey_team", mode="before")
    @classmethod
    def strip_team_names(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v = v.split(",")

        return [name.strip() for name in v if name.strip()]

    @property
    def survey_format(self) -> str:
        # File Format (Line 5). For backward compatibility, this item is optional.
        # This field specifies the format of the original survey notebook. Since Compass
        # converts the file to fixed format, this information is used by programs like
        # the editor to display and edit the data in original form. The field begins
        # with the string: "FORMAT: " followed by 11, 12 or 13 upper case alphabetic
        # characters. Each character specifies a particular part of the format.

        # Compatibility Issues. Over time, the Compass Format string has changed to
        # accommodate more format information. For backward compatibility, Compass can
        # read all previous versions of the format. Here is detailed information about
        # different versions of the Format strings:

        # (U = Units, D = Dimension Order, S = Shot Order, B = Backsight Info, L = LRUD association)  # noqa: E501

        # 11-Character Format. The earliest version of the string had 11 characters
        # like this: UUUUDDDDSSS

        # 12-Character Format. The next version had 12 characters, adding Backsight
        # information: UUUUDDDDSSSB

        # 13-Character Format. The next version had 13 characters, adding information
        # about the LRUD associations: UUUUDDDDSSSBL

        # 15-Character Format. Finally, the current version has 15 characters, adding
        # backsights to order information: UUUUDDDDSSSSSBL

        # ---------------------------------------------------------------------------- #
        #
        # Here is a list of the format items:

        # XIV.	Backsight: B=Redundant, N or empty=No Redundant Backsights.
        # XV.	LRUD Association: F=From Station, T=To Station

        cformat = ""

        # I.	Bearing Units: D = Degrees, Q = quads, R = Grads
        cformat += "D"

        # II.	Length Units: D = Decimal Feet, I = Feet and Inches M = Meters
        cformat += "D" if self.unit == "feet" else "M"

        # III.	Passage Units: Same as length
        cformat += "D" if self.unit == "feet" else "M"

        # IV.	Inclination Units:
        #         - D = Degrees
        #         - G = Percent Grade
        #         - M = Degrees and Minutes
        #         - R = Grads
        #         - W = Depth Gauge
        cformat += "D"

        # V.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        cformat += "L"
        # VI.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        # cformat += "R"
        cformat += "U"
        # VII.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        # cformat += "U"
        cformat += "D"
        # VIII.	Passage Dimension Order: U = Up, D = Down, R = Right L = Left
        # cformat += "D"
        cformat += "R"

        # IX.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "L"

        # X.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "A"

        # XI.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "D"

        # XII.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        cformat += "a"

        # XIII.	Shot Item Order:
        #         - L = Length
        #         - A = Azimuth
        #         - D = Inclination
        #         - a = Back Azimuth
        #         - d = Back Inclination
        #         - B = Redundant
        #         - N or empty = No Redundant Backsights
        cformat += "d"

        # XIV.	Backsight: B=Redundant, N or empty=No Redundant Backsights.
        cformat += "N"

        # XV.	LRUD Association: F=From Station, T=To Station
        cformat += "F"

        return cformat

    def export_to_dat(self, fp: TextIOWrapper) -> None:
        fp.write(f"{self.cave_name}\n")
        fp.write(f"SURVEY NAME: {self.name}\n")
        fp.write(
            "".join(
                (
                    "SURVEY DATE: ",
                    self.survey_date.strftime("%m %-d %Y")
                    if self.survey_date
                    else "None",
                    " ",
                )
            )
        )
        fp.write(f"COMMENT:{self.comment}\n")
        fp.write(f"SURVEY TEAM:\n{', '.join(self.survey_team)}\n")
        fp.write(f"DECLINATION: {self.declination:>7.02f}  ")
        fp.write(f"FORMAT: {self.survey_format}  ")
        fp.write(
            f"CORRECTIONS:  {' '.join(f'{nbr:.02f}' for nbr in self.correction)}  "
        )
        fp.write(
            f"CORRECTIONS2:  {' '.join(f'{nbr:.02f}' for nbr in self.correction2)}  "
        )
        fp.write(
            "".join(
                (
                    "DISCOVERY: ",
                    self.discovery_date.strftime("%m %-d %Y")
                    if self.discovery_date
                    else "None",
                    "\n\n",
                )
            )
        )

        # Shots - Header
        fp.write("        FROM           TO   LENGTH  BEARING      INC")
        fp.write("     LEFT       UP     DOWN    RIGHT")
        fp.write("     AZM2     INC2   FLAGS  COMMENTS\n\n")

        for shot in self.shots:
            shot.export_to_dat(fp)

        # End of Section - Form_feed: https://www.ascii-code.com/12
        fp.write(f"{COMPASS_SECTION_SEPARATOR}\n")


class Survey(BaseModel):
    sections: Annotated[list[SurveySection], Field(min_length=1)]

    model_config = ConfigDict(extra="forbid")

    def to_json(self, filepath: str | Path | None = None) -> str:
        filepath = Path(filepath) if filepath else None
        data = self.model_dump(by_alias=True)

        json_str = json.dumps(data, indent=4, sort_keys=True, cls=EnhancedJSONEncoder)

        if filepath is not None:
            with filepath.open(mode="w") as file:
                file.write(json_str)

        return json_str

    def export_to_dat(self, fp: TextIOWrapper) -> None:
        for section in self.sections:
            section.export_to_dat(fp)

        # End of File - Substitute: https://www.ascii-code.com/26
        fp.write(f"{COMPASS_END_OF_FILE}\n")
