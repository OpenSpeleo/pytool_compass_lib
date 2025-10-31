from __future__ import annotations

import datetime
import math
from collections import OrderedDict
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from typing import Any


class OrderedQueue(OrderedDict):  # pyright: ignore[reportMissingTypeArgument]
    def add(self, key: Any, value: Any, fail_if_present: bool = False) -> None:
        if key in self and fail_if_present:
            raise KeyError(f"The key `{key}` is already present: {self[key]=}")

        self[key] = value

    def remove(self, key: Any) -> None:
        del self[key]


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


def calc_inclination(length: float, delta_depth: float) -> float:
    """
    Calculate inclination (in degrees) given shot length and delta depth.

    Compass Convention:
    - Positive: Going Up/Shallower (delta_depth < 0)
    - Negative: Going Down/Deeper (delta_depth > 0)
    """
    if abs(delta_depth) > length:
        raise ValueError("Delta depth cannot be greater than shot length.")

    if length == 0.0:
        raise ValueError("Impossible to calculate inclination of a zero-length shot.")

    # Calculate inclination in radians
    theta_rad = math.asin(delta_depth / length)

    # Convert to degrees
    return -round(math.degrees(theta_rad), 2)
