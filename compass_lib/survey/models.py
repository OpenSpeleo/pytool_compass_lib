# -*- coding: utf-8 -*-
"""Survey data models for Compass .DAT files.

This module contains Pydantic models for representing survey data:
- CompassShot: A single shot between two stations
- CompassSurveyHeader: Metadata and settings for a survey
- CompassSurvey: A complete survey with header and shots
- CompassDatFile: A DAT file containing one or more surveys

All measurements are stored in Compass's fixed internal units:
- Length/LRUD: decimal feet
- Bearing/Inclination/Backsights: degrees

The FORMAT string from the DAT file is purely display metadata for the
Compass editor and is stored as a raw string on the header.
"""

from __future__ import annotations

import datetime  # noqa: TC003

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_serializer


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


class CompassSurveyHeader(BaseModel):
    """Metadata and settings for a survey.

    The FORMAT string is stored as a raw string (``format_string``).
    It is purely display metadata for the Compass editor -- it does NOT
    affect how shot data is parsed or stored. All data in a .DAT file
    uses fixed internal units (feet, degrees) and fixed column order.

    The only structural information extracted from the FORMAT string is
    ``has_backsights``, which determines whether backsight columns are
    present in the shot data.
    """

    model_config = ConfigDict(populate_by_name=True)

    cave_name: str | None = None
    survey_name: str | None = None
    date: datetime.date | None = None
    comment: str | None = None
    team: str | None = None
    declination: float = 0.0
    format_string: str | None = None
    has_backsights: bool = True
    length_correction: float = 0.0
    frontsight_azimuth_correction: float = 0.0
    frontsight_inclination_correction: float = 0.0
    backsight_azimuth_correction: float = 0.0
    backsight_inclination_correction: float = 0.0

    @field_serializer("comment", "team")
    @classmethod
    def serialize_empty_as_none(cls, v: str | None) -> str | None:
        return None if v == "" else v


class CompassSurvey(BaseModel):
    """A complete survey with header and shots."""

    model_config = ConfigDict(populate_by_name=True)

    header: CompassSurveyHeader
    shots: list[CompassShot] = Field(default_factory=list)


class CompassDatFile(BaseModel):
    """A Compass .DAT file containing one or more surveys."""

    model_config = ConfigDict(populate_by_name=True)

    surveys: list[CompassSurvey] = Field(default_factory=list)

    @property
    def total_shots(self) -> int:
        return sum(len(survey.shots) for survey in self.surveys)

    @property
    def survey_names(self) -> list[str]:
        return [survey.header.survey_name or "<unnamed>" for survey in self.surveys]

    def get_all_stations(self) -> set[str]:
        stations: set[str] = set()
        for survey in self.surveys:
            for shot in survey.shots:
                stations.add(shot.from_station_name)
                stations.add(shot.to_station_name)
        return stations
