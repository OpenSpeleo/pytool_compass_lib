# -*- coding: utf-8 -*-
"""Formatting (serialization) for Compass .DAT survey files.

This module provides functions to convert survey data models back to
the Compass .DAT file format string representation.

All data is written in Compass's fixed internal units (feet, degrees)
and fixed column order. The FORMAT string is purely display metadata
for the Compass editor and is stored/output as a raw string.
"""

from collections.abc import Callable

from compass_lib.constants import FLAG_CHARS
from compass_lib.constants import MISSING_VALUE_STRING
from compass_lib.constants import NUMBER_WIDTH
from compass_lib.constants import STATION_NAME_WIDTH
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader
from compass_lib.validation import validate_station_name

# Default FORMAT strings used when no format_string is stored on the header.
# These use degrees for all angles, decimal feet for lengths, standard LRUD
# order (LUDR), and standard shot order (LAD).
_DEFAULT_FORMAT_WITH_BACKSIGHTS = "DDDDLUDRLADadBF"
_DEFAULT_FORMAT_WITHOUT_BACKSIGHTS = "DDDDLUDRLAD"


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


def format_shot(shot: CompassShot, header: CompassSurveyHeader) -> str:
    """Format a single shot as a line of text.

    All values are output in Compass's fixed internal units (feet, degrees)
    in fixed column order:
    FROM TO LENGTH AZIMUTH INCLINATION LEFT UP DOWN RIGHT [BS_AZ BS_INC] [FLAGS] [COMMENT]

    Args:
        shot: Shot data
        header: Survey header (for has_backsights flag)

    Returns:
        Formatted shot line with CRLF
    """  # noqa: E501
    # Validate station names
    validate_station_name(shot.from_station_name)
    validate_station_name(shot.to_station_name)

    columns = [
        _cell(shot.from_station_name, STATION_NAME_WIDTH),
        _cell(shot.to_station_name, STATION_NAME_WIDTH),
    ]

    # Shot measurements in FIXED order: LENGTH, AZIMUTH, INCLINATION
    columns.append(_format_number(shot.length))
    columns.append(_format_number(shot.frontsight_azimuth))
    columns.append(_format_number(shot.frontsight_inclination))

    # LRUD values in FIXED order: LEFT, UP, DOWN, RIGHT
    columns.append(_format_number(shot.left))
    columns.append(_format_number(shot.up))
    columns.append(_format_number(shot.down))
    columns.append(_format_number(shot.right))

    # Add backsights if present (always after LRUD, before flags)
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


def format_survey_header(
    header: CompassSurveyHeader,
    *,
    include_column_headers: bool = True,
) -> str:
    """Format a survey header as text.

    Args:
        header: Survey header data
        include_column_headers: Whether to include column header line

    Returns:
        Formatted header text with CRLF
    """
    lines = []

    # Cave name (no truncation to preserve data)
    lines.append(header.cave_name or "")

    # Survey name (preserve full name for round-trip, Compass may use longer names)
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

    # FORMAT string -- use stored value or generate a sensible default
    if header.format_string:
        format_str = header.format_string
    elif header.has_backsights:
        format_str = _DEFAULT_FORMAT_WITH_BACKSIGHTS
    else:
        format_str = _DEFAULT_FORMAT_WITHOUT_BACKSIGHTS

    declination = header.declination
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


def format_survey(survey: CompassSurvey, *, include_column_headers: bool = True) -> str:
    """Format a complete survey (header + shots).

    Args:
        survey: Survey data
        include_column_headers: Whether to include column headers

    Returns:
        Formatted survey text
    """
    parts = [
        format_survey_header(
            survey.header, include_column_headers=include_column_headers
        )
    ]

    parts.extend(format_shot(shot, survey.header) for shot in survey.shots)

    return "".join(parts)


def format_dat_file(
    surveys: list[CompassSurvey],
    *,
    write: Callable[[str], None] | None = None,
) -> str | None:
    """Format a complete DAT file from surveys.

    Args:
        surveys: List of surveys
        write: Optional callback for streaming output. If provided,
               chunks are written via this callback and None is returned.

    Returns:
        Formatted file content as string (if write is None),
        or None (if write callback is provided)
    """
    if write is not None:
        # Streaming mode
        for survey in surveys:
            write(format_survey(survey))
            write("\f\r\n")
        return None

    # Return mode
    chunks: list[str] = []
    format_dat_file(surveys, write=chunks.append)
    return "".join(chunks)
