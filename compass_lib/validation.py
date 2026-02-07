# -*- coding: utf-8 -*-
"""Validation utilities for Compass data.

This module provides validation functions for station names, depth gauge
conversions, and other data elements based on Compass format specifications.
"""

import calendar
import math
import re
from re import Pattern

# Station name pattern: printable ASCII characters (0x21-0x7F), no spaces
# The original Compass spec limited to 12 chars, but modern files often exceed this
# We allow any length but still require valid printable ASCII
STATION_NAME_PATTERN: Pattern[str] = re.compile(r"^[\x21-\x7f]+$")


def is_valid_station_name(name: str) -> bool:
    """Check if a station name is valid.

    Valid station names:
    - 1 or more characters (no upper limit enforced)
    - Printable ASCII only (0x21-0x7F)
    - No spaces or control characters

    Note: The original Compass format limited station names to 12 characters,
    but many modern Compass files use longer names. This validation accepts
    any length to ensure compatibility with real-world data.

    Args:
        name: Station name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name:
        return False
    return bool(STATION_NAME_PATTERN.match(name))


def validate_station_name(name: str) -> None:
    """Validate a station name, raising an error if invalid.

    Args:
        name: Station name to validate

    Raises:
        ValueError: If the station name is invalid
    """
    if not is_valid_station_name(name):
        # Escape non-printable characters for error message
        escaped = ""
        for char in name:
            if ord(char) < 0x20 or ord(char) > 0x7F:
                escaped += f"\\x{ord(char):02x}"
            else:
                escaped += char
        msg = f"Invalid station name: {escaped}"
        raise ValueError(msg)


def days_in_month(month: int, year: int) -> int:
    """Get the number of days in a month, accounting for leap years.

    Args:
        month: Month (1-12)
        year: Year

    Returns:
        Number of days in the month
    """
    # monthrange returns (weekday_of_first_day, num_days_in_month)
    _, num_days = calendar.monthrange(year, month)
    return num_days


# =============================================================================
# Depth Gauge Utilities
# =============================================================================
#
# Depth Gauge Mode (Inclination Unit "W")
# ---------------------------------------
#
# In underwater cave surveying, divers use a scuba diver's water depth gauge
# instead of an inclinometer. The depth gauge measures the instrument's depth
# below the water surface.
#
# Key Concepts:
#
# 1. **Delta Depth**: Compass requires depth gauge data to be entered as the
#    DIFFERENCE between the From and To station depths:
#
#        depth_delta = From_depth - To_depth
#
# 2. **Sign Convention**:
#    - Negative depth_delta = going DEEPER (descending)
#    - Positive depth_delta = going SHALLOWER (ascending)
#
# 3. **Conversion to Inclination**: To convert depth gauge readings to an
#    equivalent inclination angle:
#
#        inclination = arcsin(depth_delta / shot_length) * (180 / π)
#
# 4. **Validation**: The absolute depth delta cannot exceed the shot length:
#
#        |depth_delta| <= shot_length
#
# 5. **Backsight Incompatibility**: Depth gauge mode and redundant backsights
#    cannot be enabled simultaneously (they don't make logical sense together).
#
# 6. **Units**: Depth gauge uses the same units as length measurements.
#
# =============================================================================


def depth_gauge_to_inclination(
    depth_delta: float,
    shot_length: float,
) -> float:
    """Convert a depth gauge reading (delta depth) to an inclination angle.

    Depth gauge measurements represent the difference between the From and To
    station depths (From_depth - To_depth). This function converts that delta
    to an equivalent inclination angle in degrees.

    The formula used is:
        inclination = arcsin(depth_delta / shot_length) * (180 / π)

    Args:
        depth_delta: Depth difference (From_depth - To_depth) in length units.
                     Negative values indicate descending (going deeper),
                     positive values indicate ascending (going shallower).
        shot_length: The horizontal distance of the shot in the same units.

    Returns:
        Inclination angle in degrees (-90 to +90).
        - Negative angles indicate descending (going deeper)
        - Positive angles indicate ascending (going shallower)

    Raises:
        ValueError: If shot_length is zero or negative, or if |depth_delta|
                    exceeds shot_length.

    Examples:
        >>> depth_gauge_to_inclination(-5.0, 10.0)  # Going 5m deeper over 10m
        -30.0

        >>> depth_gauge_to_inclination(5.0, 10.0)   # Going 5m shallower over 10m
        30.0

        >>> depth_gauge_to_inclination(0.0, 10.0)   # Level shot
        0.0
    """
    if shot_length <= 0:
        raise ValueError(f"shot_length must be positive, got {shot_length}")

    # Clamp the ratio to [-1, 1] to handle floating point precision issues
    # and shots where depth equals length (vertical shots)
    ratio = depth_delta / shot_length

    if abs(ratio) > 1.0:
        # Allow small tolerance for floating point errors
        if abs(ratio) > 1.0001:
            raise ValueError(
                f"Depth delta ({depth_delta}) cannot exceed shot length ({shot_length})"
            )
        # Clamp to valid range
        ratio = max(-1.0, min(1.0, ratio))

    inclination_radians = math.asin(ratio)
    return math.degrees(inclination_radians)


def inclination_to_depth_gauge(
    inclination: float,
    shot_length: float,
) -> float:
    """Convert an inclination angle to a depth gauge reading (delta depth).

    This is the inverse of depth_gauge_to_inclination(). Given an inclination
    angle and shot length, calculates the equivalent depth difference.

    The formula used is:
        depth_delta = shot_length * sin(inclination * π / 180)

    Args:
        inclination: Inclination angle in degrees (-90 to +90).
        shot_length: The horizontal distance of the shot in length units.

    Returns:
        Depth difference (From_depth - To_depth) in the same units as shot_length.
        - Negative values indicate descending (going deeper)
        - Positive values indicate ascending (going shallower)

    Examples:
        >>> inclination_to_depth_gauge(-30.0, 10.0)  # 30° descent over 10m
        -5.0

        >>> inclination_to_depth_gauge(30.0, 10.0)   # 30° ascent over 10m
        5.0
    """
    inclination_radians = math.radians(inclination)
    return shot_length * math.sin(inclination_radians)


def validate_depth_gauge(
    depth_delta: float,
    shot_length: float,
) -> tuple[bool, str | None]:
    """Validate a depth gauge measurement against the shot length.

    Depth gauge measurements are geometrically limited: the absolute depth
    difference cannot exceed the shot length (you can't go down further than
    the total distance traveled).

    Args:
        depth_delta: Depth difference (From_depth - To_depth)
        shot_length: Shot length in the same units

    Returns:
        Tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, error_description).

    Examples:
        >>> validate_depth_gauge(-5.0, 10.0)
        (True, None)

        >>> validate_depth_gauge(-15.0, 10.0)
        (False, 'Depth delta (15.0) exceeds shot length (10.0)')
    """
    if shot_length <= 0:
        return False, f"Shot length must be positive, got {shot_length}"

    if abs(depth_delta) > shot_length:
        return False, (
            f"Depth delta ({abs(depth_delta)}) exceeds shot length ({shot_length})"
        )

    return True, None
