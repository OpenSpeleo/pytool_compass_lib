#!/usr/bin/env python

from dataclasses import dataclass

from compass_lib.enums import ShotFlag


@dataclass
class SurveyShot:
    #         FROM           TO   LENGTH  BEARING      INC     LEFT       UP     DOWN    RIGHT   FLAGS  COMMENTS  # noqa: E501
    #           A1           A2    21.75    63.50   -28.00     2.60     2.60     2.60     2.60#  # noqa: E501
    from_id: str
    to_id: str
    length: float
    bearing: float
    inclination: float
    left: float
    up: float
    down: float
    right: float
    flags: list[ShotFlag]
    comment: str
    depth: float | None = None
