# -*- coding: utf-8 -*-
"""Survey data models for Compass .DAT files.

This module contains Pydantic models for representing survey data:
- CompassShot: A single shot between two stations
- CompassTripHeader: Metadata and settings for a survey trip
- CompassTrip: A complete trip with header and shots
- CompassDatFile: A DAT file containing one or more trips
"""

from __future__ import annotations

import datetime  # noqa: TC003

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_serializer
from pydantic import field_validator

from compass_scratchpad.enums import AzimuthUnit
from compass_scratchpad.enums import InclinationUnit
from compass_scratchpad.enums import LengthUnit
from compass_scratchpad.enums import LrudAssociation
from compass_scratchpad.enums import LrudItem
from compass_scratchpad.enums import ShotItem


class CompassShot(BaseModel):
    """A single survey shot between two stations.

    All measurements are stored in internal units (feet, degrees).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

    from_station_name: str = Field(alias="from_station")
    to_station_name: str = Field(alias="to_station")
    length: float | None = Field(default=None, alias="distance")
    frontsight_azimuth: float | None = None
    frontsight_inclination: float | None = None
    backsight_azimuth: float | None = None
    backsight_inclination: float | None = None
    left: float | None = None
    right: float | None = None
    up: float | None = None
    down: float | None = None
    comment: str | None = None
    excluded_from_length: bool = Field(default=False, alias="exclude_distance")
    excluded_from_plotting: bool = False
    excluded_from_all_processing: bool = False
    do_not_adjust: bool = False

    # NOTE: Validation is relaxed to allow real-world data with out-of-range values.
    # The parser tracks these issues in its errors list.
    # Strict validation can be performed separately if needed.


class CompassTripHeader(BaseModel):
    """Metadata and settings for a survey trip."""

    model_config = ConfigDict(populate_by_name=True)

    cave_name: str | None = None
    survey_name: str | None = None
    date: datetime.date | None = None
    comment: str | None = None
    team: str | None = None
    declination: float = 0.0
    length_unit: LengthUnit = LengthUnit.DECIMAL_FEET
    lrud_unit: LengthUnit = LengthUnit.DECIMAL_FEET
    azimuth_unit: AzimuthUnit = AzimuthUnit.DEGREES
    inclination_unit: InclinationUnit = InclinationUnit.DEGREES
    lrud_order: list[LrudItem] = Field(
        default_factory=lambda: [
            LrudItem.LEFT,
            LrudItem.RIGHT,
            LrudItem.UP,
            LrudItem.DOWN,
        ]
    )
    shot_measurement_order: list[ShotItem] = Field(
        default_factory=lambda: [
            ShotItem.LENGTH,
            ShotItem.FRONTSIGHT_AZIMUTH,
            ShotItem.FRONTSIGHT_INCLINATION,
        ]
    )
    has_backsights: bool = True
    lrud_association: LrudAssociation = LrudAssociation.FROM
    length_correction: float = 0.0
    frontsight_azimuth_correction: float = 0.0
    frontsight_inclination_correction: float = 0.0
    backsight_azimuth_correction: float = 0.0
    backsight_inclination_correction: float = 0.0

    @field_serializer("comment", "team")
    @classmethod
    def serialize_empty_as_none(cls, v: str | None) -> str | None:
        return None if v == "" else v

    @field_serializer("lrud_order")
    @classmethod
    def serialize_lrud_order(cls, v: list[LrudItem]) -> list[str]:
        return [item.value for item in v]

    @field_serializer("shot_measurement_order")
    @classmethod
    def serialize_shot_order(cls, v: list[ShotItem]) -> list[str]:
        return [item.value for item in v]

    @field_validator("lrud_order", mode="before")
    @classmethod
    def parse_lrud_order(cls, v: list) -> list[LrudItem]:
        if v and isinstance(v[0], str):
            return [LrudItem(item) for item in v]
        return v

    @field_validator("shot_measurement_order", mode="before")
    @classmethod
    def parse_shot_order(cls, v: list) -> list[ShotItem]:
        if v and isinstance(v[0], str):
            return [ShotItem(item) for item in v]
        return v


class CompassTrip(BaseModel):
    """A complete survey trip with header and shots."""

    model_config = ConfigDict(populate_by_name=True)

    header: CompassTripHeader
    shots: list[CompassShot] = Field(default_factory=list)


class CompassDatFile(BaseModel):
    """A Compass .DAT file containing one or more survey trips."""

    model_config = ConfigDict(populate_by_name=True)

    trips: list[CompassTrip] = Field(default_factory=list)

    @property
    def total_shots(self) -> int:
        return sum(len(trip.shots) for trip in self.trips)

    @property
    def trip_names(self) -> list[str]:
        return [trip.header.survey_name or "<unnamed>" for trip in self.trips]

    def get_all_stations(self) -> set[str]:
        stations: set[str] = set()
        for trip in self.trips:
            for shot in trip.shots:
                stations.add(shot.from_station_name)
                stations.add(shot.to_station_name)
        return stations
