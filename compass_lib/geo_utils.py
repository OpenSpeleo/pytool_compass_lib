from __future__ import annotations

import datetime

import pyIGRF14 as pyIGRF
from compass_lib.constants import GEOJSON_COORDINATE_PRECISION
from pydantic import BaseModel
from pydantic_extra_types.coordinate import Latitude  # noqa: TC002
from pydantic_extra_types.coordinate import Longitude  # noqa: TC002


class GeoLocation(BaseModel):
    latitude: Latitude
    longitude: Longitude

    def as_tuple(self) -> tuple[float, float]:
        """Return the latitude and longitude as a tuple.
        # RFC 7946: (longitude, latitude)
        """
        return (
            round(self.longitude, GEOJSON_COORDINATE_PRECISION),
            round(self.latitude, GEOJSON_COORDINATE_PRECISION),
        )


def decimal_year(dt: datetime.datetime) -> float:
    dt_start = datetime.datetime(  # noqa: DTZ001
        year=dt.year, month=1, day=1, hour=0, minute=0, second=0
    )
    dt_end = datetime.datetime(  # noqa: DTZ001
        year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0
    )
    return round(
        dt.year + (dt - dt_start).total_seconds() / (dt_end - dt_start).total_seconds(),
        ndigits=2,
    )


def get_declination(location: GeoLocation, dt: datetime.datetime) -> float:
    declination, _, _, _, _, _, _ = pyIGRF.igrf_value(
        location.latitude,
        location.longitude,
        alt=0.0,
        year=decimal_year(dt),
    )
    return round(declination, 2)
