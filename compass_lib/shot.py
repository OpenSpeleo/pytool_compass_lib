#!/usr/bin/env python

from dataclasses import dataclass

from compass_lib.enums import ShotFlag


@dataclass
class SurveyShot:
    #        FROM           TO   LENGTH  BEARING      INC     LEFT       UP     DOWN    RIGHT     AZM2     INC2   FLAGS  COMMENTS  # noqa: E501
    #       toc11       toc11a   165.00  -999.00    90.00     0.00     0.00     0.00     0.00     0.00  -999.00  #|X#  Shot up     # noqa: E501
    from_id: str
    to_id: str
    length: float
    bearing: float
    inclination: float
    left: float
    up: float
    down: float
    right: float
    # Optional Data
    azimuth2: float
    inclination2: float
    flags: list[ShotFlag]
    comment: str
    # Not saved data
    depth: float | None = None
