from __future__ import annotations

import datetime

import pyIGRF14 as pyIGRF
from pydantic import BaseModel
from pydantic_extra_types.coordinate import Latitude  # noqa: TC002
from pydantic_extra_types.coordinate import Longitude  # noqa: TC002

from compass_scratchpad.constants import GEOJSON_COORDINATE_PRECISION

# ruff: noqa: T201


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
    dt_start = datetime.datetime(
        year=dt.year, month=1, day=1, hour=0, minute=0, second=0
    )
    dt_end = datetime.datetime(
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


if __name__ == "__main__":
    dt = datetime.datetime(2025, 7, 1)

    d1 = get_declination(GeoLocation(latitude=20.6296, longitude=-87.0739), dt)

    print(f"pyIGRF declination : {d1:.6f}°")
