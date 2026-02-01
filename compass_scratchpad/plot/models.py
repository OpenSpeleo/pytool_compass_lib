# -*- coding: utf-8 -*-
"""Plot data models for Compass .PLT files.

This module contains Pydantic models for representing plot commands
found in Compass .PLT plot files.
"""

import datetime
from decimal import Decimal

from pydantic import BaseModel
from pydantic import Field

from compass_scratchpad.enums import DrawOperation
from compass_scratchpad.models import Bounds
from compass_scratchpad.models import Location


class CompassPlotCommand(BaseModel):
    """Base class for all plot commands."""


class BeginSurveyCommand(CompassPlotCommand):
    """Begin survey command (N).

    Marks the start of a new survey section.

    Attributes:
        survey_name: Survey identifier (max 12 chars)
        date: Survey date
        comment: Optional comment (max 80 chars)
    """

    survey_name: str
    date: datetime.date | None = None
    comment: str | None = None

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        result = f"N{self.survey_name[:12]}"
        if self.date:
            result += f"\tD {self.date.month} {self.date.day} {self.date.year}"
        else:
            result += "\tD 1 1 1"
        if self.comment:
            result += f"\tC{self.comment[:80]}"
        return result


class BeginSectionCommand(CompassPlotCommand):
    """Begin section command (S).

    Marks the start of a new section.

    Attributes:
        section_name: Section name (max 20 chars)
    """

    section_name: str

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        return f"S{self.section_name[:20]}"


class BeginFeatureCommand(CompassPlotCommand):
    """Begin feature command (F).

    Marks the start of a feature definition with optional range.

    Attributes:
        feature_name: Feature name (max 12 chars)
        min_value: Optional minimum value for range
        max_value: Optional maximum value for range
    """

    feature_name: str
    min_value: Decimal | None = None
    max_value: Decimal | None = None

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        result = f"F{self.feature_name[:12]}"
        if self.min_value is not None and self.max_value is not None:
            result += f"\tR\t{float(self.min_value)}\t{float(self.max_value)}"
        return result


class DrawSurveyCommand(CompassPlotCommand):
    """Draw survey command (M or D).

    Represents a move-to or draw-to operation with station data.

    Attributes:
        operation: MOVE_TO (M) or LINE_TO (D)
        location: 3D coordinates
        station_name: Station identifier
        left: Distance to left wall (feet, None if missing)
        right: Distance to right wall (feet, None if missing)
        up: Distance to ceiling (feet, None if missing)
        down: Distance to floor (feet, None if missing)
        distance_from_entrance: Distance from cave entrance (feet)
    """

    operation: DrawOperation
    location: Location = Field(default_factory=Location)
    station_name: str | None = None
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None
    distance_from_entrance: float = 0.0

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        cmd = "M" if self.operation == DrawOperation.MOVE_TO else "D"
        result = f"{cmd}\t{self.location.northing}\t{self.location.easting}"
        result += f"\t{self.location.vertical}"
        if self.station_name:
            result += f"\tS{self.station_name[:12]}"
        result += "\tP"
        result += f"\t{self.left if self.left is not None else -9.0}"
        result += f"\t{self.up if self.up is not None else -9.0}"
        result += f"\t{self.down if self.down is not None else -9.0}"
        result += f"\t{self.right if self.right is not None else -9.0}"
        result += f"\tI\t{self.distance_from_entrance}"
        return result


class FeatureCommand(CompassPlotCommand):
    """Feature point command (L).

    Represents a feature location with optional value.

    Attributes:
        location: 3D coordinates
        station_name: Station identifier
        left: Distance to left wall (feet, None if missing)
        right: Distance to right wall (feet, None if missing)
        up: Distance to ceiling (feet, None if missing)
        down: Distance to floor (feet, None if missing)
        value: Feature value
    """

    location: Location = Field(default_factory=Location)
    station_name: str | None = None
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None
    value: Decimal | None = None

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        result = f"L\t{self.location.northing}\t{self.location.easting}"
        result += f"\t{self.location.vertical}"
        if self.station_name:
            result += f"\tS{self.station_name[:12]}"
        result += "\tP"
        result += f"\t{self.left if self.left is not None else -9.0}"
        result += f"\t{self.right if self.right is not None else -9.0}"
        result += f"\t{self.up if self.up is not None else -9.0}"
        result += f"\t{self.down if self.down is not None else -9.0}"
        if self.value is not None:
            result += f"\tV\t{self.value}"
        return result


class SurveyBoundsCommand(CompassPlotCommand):
    """Survey bounds command (X).

    Defines the bounding box for the current survey.

    Attributes:
        bounds: Lower and upper bound locations
    """

    bounds: Bounds = Field(default_factory=Bounds)

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        lb = self.bounds.lower
        ub = self.bounds.upper
        return (
            f"X\t{lb.northing}\t{ub.northing}\t{lb.easting}"
            f"\t{ub.easting}\t{lb.vertical}\t{ub.vertical}"
        )


class CaveBoundsCommand(CompassPlotCommand):
    """Cave bounds command (Z).

    Defines the overall bounding box for the cave.

    Attributes:
        bounds: Lower and upper bound locations
        distance_to_farthest_station: Distance to farthest station from entrance
    """

    bounds: Bounds = Field(default_factory=Bounds)
    distance_to_farthest_station: float | None = None

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        lb = self.bounds.lower
        ub = self.bounds.upper
        result = (
            f"Z\t{lb.northing}\t{ub.northing}\t{lb.easting}"
            f"\t{ub.easting}\t{lb.vertical}\t{ub.vertical}"
        )
        if self.distance_to_farthest_station is not None:
            result += f"\tI\t{self.distance_to_farthest_station}"
        return result


class DatumCommand(CompassPlotCommand):
    """Datum command (O).

    Specifies the geodetic datum.

    Attributes:
        datum: Datum identifier
    """

    datum: str

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        return f"O{self.datum}"


class UtmZoneCommand(CompassPlotCommand):
    """UTM zone command (G).

    Specifies the UTM zone.

    Attributes:
        utm_zone: UTM zone identifier (stored as string)
    """

    utm_zone: str

    def __str__(self) -> str:
        """Format as PLT file syntax."""
        return f"G{self.utm_zone}"
