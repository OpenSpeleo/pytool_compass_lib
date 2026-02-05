# -*- coding: utf-8 -*-
"""Formatting (serialization) for Compass .DAT survey files.

This module provides functions to convert survey data models back to
the Compass .DAT file format string representation.
"""

from collections.abc import Callable

from compass_lib.constants import FLAG_CHARS
from compass_lib.constants import MISSING_VALUE_STRING
from compass_lib.constants import NUMBER_WIDTH
from compass_lib.constants import STATION_NAME_WIDTH
from compass_lib.enums import LrudAssociation
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassTrip
from compass_lib.survey.models import CompassTripHeader
from compass_lib.validation import validate_station_name


def _cell(value: str, width: int) -> str:
    """Format a value as a right-aligned cell.

    Args:
        value: String value
        width: Minimum width (actual width may be larger if value is longer)

    Returns:
        Right-aligned, space-padded string (never truncated to preserve data)
    """
    # Never truncate - the parser is whitespace-delimited so longer values work fine
    # Always ensure at least one leading space to separate from previous column
    if len(value) >= width:
        return " " + value
    return value.rjust(width)


def _format_number(value: float | None, width: int = NUMBER_WIDTH) -> str:
    """Format a number for output.

    Args:
        value: Numeric value (None for missing)
        width: Column width

    Returns:
        Formatted string representation
    """
    if value is None:
        return _cell(MISSING_VALUE_STRING, width)
    # Check if value has more than 2 decimal places of precision
    # by comparing rounded vs original
    rounded_2 = round(value, 2)
    if abs(value - rounded_2) > 1e-9:
        # Value has more precision, use 3 decimal places
        return _cell(f"{value:.3f}", width)
    return _cell(f"{value:.2f}", width)


def format_shot(shot: CompassShot, header: CompassTripHeader) -> str:
    """Format a single shot as a line of text.

    Args:
        shot: Shot data
        header: Trip header (for format settings)

    Returns:
        Formatted shot line with CRLF
    """
    # Validate station names
    validate_station_name(shot.from_station_name)
    validate_station_name(shot.to_station_name)

    # Handle depth gauge inclination unit
    # (would need Length unit instead of Angle, but we store as float)

    columns = [
        _cell(shot.from_station_name, STATION_NAME_WIDTH),
        _cell(shot.to_station_name, STATION_NAME_WIDTH),
        _format_number(shot.length),
        _format_number(shot.frontsight_azimuth),
        _format_number(shot.frontsight_inclination),
        _format_number(shot.left),
        _format_number(shot.up),
        _format_number(shot.down),
        _format_number(shot.right),
    ]

    # Add backsights if present
    if header.has_backsights:
        columns.append(_format_number(shot.backsight_azimuth))
        columns.append(_format_number(shot.backsight_inclination))

    # Build flags
    flags = ""
    if shot.excluded_from_length:
        flags += FLAG_CHARS["exclude_distance"]
    if shot.excluded_from_plotting:
        flags += FLAG_CHARS["exclude_from_plotting"]
    if shot.excluded_from_all_processing:
        flags += FLAG_CHARS["exclude_from_all_processing"]
    if shot.do_not_adjust:
        flags += FLAG_CHARS["do_not_adjust"]

    if flags:
        columns.append(f" #|{flags}#")

    # Add comment
    if shot.comment:
        # Clean comment: replace newlines with space (no truncation to preserve data)
        clean_comment = shot.comment.replace("\r\n", " ").replace("\n", " ")
        clean_comment = clean_comment.strip()
        columns.append(" " + clean_comment)

    columns.append("\r\n")
    return "".join(columns)


def format_trip_header(
    header: CompassTripHeader,
    *,
    include_column_headers: bool = True,
) -> str:
    """Format a trip header as text.

    Args:
        header: Trip header data
        include_column_headers: Whether to include column header line

    Returns:
        Formatted header text with CRLF
    """
    lines = []

    # Cave name (no truncation to preserve data)
    lines.append(header.cave_name or "")

    # Survey name (preserve full name for roundtrip, Compass may use longer names)
    survey_name = header.survey_name or ""
    lines.append(f"SURVEY NAME: {survey_name}")

    # Survey date and comment
    if header.date:
        date_str = f"{header.date.month} {header.date.day} {header.date.year}"
    else:
        date_str = "1 1 1"

    date_line = f"SURVEY DATE: {date_str}"
    if header.comment:
        date_line += f"  COMMENT:{header.comment}"
    lines.append(date_line)

    # Team (no truncation to preserve data)
    lines.append("SURVEY TEAM:")
    lines.append(header.team or "")

    # Declination and format
    declination = header.declination
    format_items = [
        header.azimuth_unit.value,
        header.length_unit.value,
        header.lrud_unit.value,
        header.inclination_unit.value,
    ]
    format_items.extend(item.value for item in header.lrud_order)
    format_items.extend(item.value for item in header.shot_measurement_order)

    # Backsight indicator
    if header.has_backsights or header.lrud_association:
        format_items.append("B" if header.has_backsights else "N")
        assoc = header.lrud_association or LrudAssociation.FROM
        format_items.append(assoc.value)

    format_str = "".join(format_items)
    decl_line = f"DECLINATION: {declination:.2f}  FORMAT: {format_str}"

    # Corrections
    has_corrections = any(
        [
            header.length_correction,
            header.frontsight_azimuth_correction,
            header.frontsight_inclination_correction,
        ]
    )

    if has_corrections:
        corr_values = [
            header.length_correction or 0.0,
            header.frontsight_azimuth_correction or 0.0,
            header.frontsight_inclination_correction or 0.0,
        ]
        corr_str = " ".join(f"{v:.2f}" for v in corr_values)
        decl_line += f"  CORRECTIONS: {corr_str}"

        # Backsight corrections
        has_bs_corrections = any(
            [
                header.backsight_azimuth_correction,
                header.backsight_inclination_correction,
            ]
        )
        if has_bs_corrections:
            bs_values = [
                header.backsight_azimuth_correction or 0.0,
                header.backsight_inclination_correction or 0.0,
            ]
            bs_str = " ".join(f"{v:.2f}" for v in bs_values)
            decl_line += f" CORRECTIONS2: {bs_str}"

    lines.append(decl_line)

    # Column headers
    if include_column_headers:
        lines.append("")  # Blank line

        col_headers = [
            "FROM         ",
            "TO           ",
            "LEN     ",
            "BEAR    ",
            "INC     ",
            "LEFT    ",
            "UP      ",
            "DOWN    ",
            "RIGHT   ",
        ]
        if header.has_backsights:
            col_headers.append("AZM2    ")
            col_headers.append("INC2    ")
        col_headers.append("FLAGS ")
        col_headers.append("COMMENTS")

        lines.append("".join(col_headers))
        lines.append("")  # Blank line before data

    # Join with CRLF
    return "\r\n".join(lines) + "\r\n"


def format_trip(trip: CompassTrip, *, include_column_headers: bool = True) -> str:
    """Format a complete trip (header + shots).

    Args:
        trip: Trip data
        include_column_headers: Whether to include column headers

    Returns:
        Formatted trip text
    """
    parts = [
        format_trip_header(trip.header, include_column_headers=include_column_headers)
    ]

    parts.extend(format_shot(shot, trip.header) for shot in trip.shots)

    return "".join(parts)


def format_dat_file(
    trips: list[CompassTrip],
    *,
    write: Callable[[str], None] | None = None,
) -> str | None:
    """Format a complete DAT file from trips.

    Args:
        trips: List of trips
        write: Optional callback for streaming output. If provided,
               chunks are written via this callback and None is returned.

    Returns:
        Formatted file content as string (if write is None),
        or None (if write callback is provided)
    """
    if write is not None:
        # Streaming mode
        for trip in trips:
            write(format_trip(trip))
            write("\f\r\n")
        return None

    # Return mode
    chunks: list[str] = []
    format_dat_file(trips, write=chunks.append)
    return "".join(chunks)
