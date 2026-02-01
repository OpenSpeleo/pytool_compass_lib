# -*- coding: utf-8 -*-
"""Validation utilities for Compass data.

This module provides validation functions for station names and other
data elements based on Compass format specifications.
"""

import calendar
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

