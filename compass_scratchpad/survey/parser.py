# -*- coding: utf-8 -*-
"""Parser for Compass .DAT survey data files.

This module implements the parser for reading Compass survey data files,
which contain cave survey measurements organized into trips.

Architecture: The parser produces dictionaries (like loading JSON) which are
then fed to Pydantic models via a single `model_validate()` call. This keeps
parsing logic separate from model construction.
"""

import re
from datetime import date
from pathlib import Path
from typing import Any
from typing import Optional

from compass_scratchpad.constants import ASCII_ENCODING
from compass_scratchpad.constants import MISSING_ANGLE_THRESHOLD
from compass_scratchpad.constants import MISSING_VALUE_THRESHOLD
from compass_scratchpad.enums import AzimuthUnit
from compass_scratchpad.enums import InclinationUnit
from compass_scratchpad.enums import LengthUnit
from compass_scratchpad.enums import LrudAssociation
from compass_scratchpad.enums import LrudItem
from compass_scratchpad.enums import Severity
from compass_scratchpad.enums import ShotItem
from compass_scratchpad.errors import CompassParseError
from compass_scratchpad.errors import SourceLocation
from compass_scratchpad.validation import days_in_month


class CompassSurveyParser:
    """Parser for Compass .DAT survey data files.

    This parser reads Compass survey data files and produces dictionaries
    (like loading JSON from disk). The dictionaries can then be fed to
    Pydantic models via a single `model_validate()` call.

    Errors are collected rather than thrown, allowing partial parsing
    of malformed files.

    Attributes:
        errors: List of parsing errors and warnings encountered
    """

    # Regex patterns
    EOL = re.compile(r"\r\n|\r|\n")
    COLUMN_HEADER = re.compile(
        r"^\s*FROM\s+TO[^\r\n]+(\r\n|\r|\n){2}",
        re.MULTILINE | re.IGNORECASE,
    )
    NON_WHITESPACE = re.compile(r"\S+")
    HEADER_FIELDS = re.compile(
        r"SURVEY (NAME|DATE|TEAM):|COMMENT:|DECLINATION:|FORMAT:|CORRECTIONS2?:|FROM",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        """Initialize a new parser with empty error list."""
        self.errors: list[CompassParseError] = []
        self._source: str = "<string>"

    def _add_error(
        self,
        message: str,
        text: str = "",
        line: int = 0,
        column: int = 0,
    ) -> None:
        """Add an error to the error list."""
        self.errors.append(
            CompassParseError(
                severity=Severity.ERROR,
                message=message,
                location=SourceLocation(
                    source=self._source,
                    line=line,
                    column=column,
                    text=text,
                ),
            )
        )

    def _add_warning(
        self,
        message: str,
        text: str = "",
        line: int = 0,
        column: int = 0,
    ) -> None:
        """Add a warning to the error list."""
        self.errors.append(
            CompassParseError(
                severity=Severity.WARNING,
                message=message,
                location=SourceLocation(
                    source=self._source,
                    line=line,
                    column=column,
                    text=text,
                ),
            )
        )

    # -------------------------------------------------------------------------
    # Dictionary-returning methods (primary API)
    # -------------------------------------------------------------------------

    def parse_file_to_dict(self, path: Path) -> dict[str, Any]:
        """Parse a Compass survey data file to dictionary.

        This is the primary parsing method. It returns a dictionary that
        can be directly fed to `CompassDatFile.model_validate()`.

        Args:
            path: Path to the .DAT file

        Returns:
            Dictionary with "trips" key containing list of trip dicts
        """
        self._source = str(path)
        with open(path, encoding=ASCII_ENCODING, errors="replace") as f:
            data = f.read()
        return self.parse_string_to_dict(data, str(path))

    def parse_string_to_dict(
        self,
        data: str,
        source: str = "<string>",
    ) -> dict[str, Any]:
        """Parse survey data from a string to dictionary.

        Args:
            data: Survey data as string
            source: Source identifier for error messages

        Returns:
            Dictionary with "trips" key containing list of trip dicts
        """
        self._source = source
        trips: list[dict[str, Any]] = []

        # Split on form feed character
        sections = data.split("\f")
        for section in sections:
            section = section.strip()
            if section:
                trip = self._parse_trip_to_dict(section)
                if trip:
                    trips.append(trip)

        return {"trips": trips}

    # -------------------------------------------------------------------------
    # Legacy model-returning methods (thin wrappers for backwards compat)
    # -------------------------------------------------------------------------

    def parse_file(self, path: Path) -> list["CompassTrip"]:  # noqa: F821
        """Parse a Compass survey data file.

        DEPRECATED: Use parse_file_to_dict() for new code.

        Args:
            path: Path to the .DAT file

        Returns:
            List of parsed trips
        """
        from compass_scratchpad.survey.models import CompassDatFile

        data = self.parse_file_to_dict(path)
        dat_file = CompassDatFile.model_validate(data)
        return dat_file.trips

    def parse_string(
        self,
        data: str,
        source: str = "<string>",
    ) -> list["CompassTrip"]:  # noqa: F821
        """Parse survey data from a string.

        DEPRECATED: Use parse_string_to_dict() for new code.

        Args:
            data: Survey data as string
            source: Source identifier for error messages

        Returns:
            List of parsed trips
        """
        from compass_scratchpad.survey.models import CompassDatFile

        parsed = self.parse_string_to_dict(data, source)
        dat_file = CompassDatFile.model_validate(parsed)
        return dat_file.trips

    def _split_header_and_data(self, text: str) -> tuple[str, str]:
        """Split trip text into header and shot data sections.

        Args:
            text: Complete trip text

        Returns:
            Tuple of (header_text, data_text)
        """
        match = self.COLUMN_HEADER.search(text)
        if match:
            header_end = match.end()
            return text[:header_end].strip(), text[header_end:].strip()
        return text.strip(), ""

    def _parse_trip_to_dict(self, text: str) -> Optional[dict[str, Any]]:
        """Parse a single trip from text to dictionary.

        Args:
            text: Trip text (header + shots)

        Returns:
            Dictionary with "header" and "shots" keys, or None if parsing fails
        """
        header_text, data_text = self._split_header_and_data(text)

        header = self._parse_trip_header_to_dict(header_text)
        if header is None:
            return None

        shots: list[dict[str, Any]] = []
        if data_text:
            for line in self.EOL.split(data_text):
                line = line.strip()
                if line:
                    shot = self._parse_shot_to_dict(line, header)
                    if shot:
                        shots.append(shot)

        return {"header": header, "shots": shots}

    def _parse_trip_header_to_dict(self, text: str) -> Optional[dict[str, Any]]:
        """Parse trip header from text to dictionary.

        Args:
            text: Header text

        Returns:
            Dictionary with header fields, or None if parsing fails
        """
        lines = self.EOL.split(text, maxsplit=1)
        if len(lines) < 2:
            return None

        # Build header dictionary
        header: dict[str, Any] = {
            "cave_name": lines[0].strip(),
            "survey_name": None,
            "date": None,
            "comment": None,
            "team": None,
            "declination": 0.0,
            "length_unit": LengthUnit.DECIMAL_FEET.value,
            "lrud_unit": LengthUnit.DECIMAL_FEET.value,
            "azimuth_unit": AzimuthUnit.DEGREES.value,
            "inclination_unit": InclinationUnit.DEGREES.value,
            "lrud_order": [LrudItem.LEFT.value, LrudItem.RIGHT.value, LrudItem.UP.value, LrudItem.DOWN.value],
            "shot_measurement_order": [ShotItem.LENGTH.value, ShotItem.FRONTSIGHT_AZIMUTH.value, ShotItem.FRONTSIGHT_INCLINATION.value],
            "has_backsights": True,
            "lrud_association": LrudAssociation.FROM.value,
            "length_correction": 0.0,
            "frontsight_azimuth_correction": 0.0,
            "frontsight_inclination_correction": 0.0,
            "backsight_azimuth_correction": 0.0,
            "backsight_inclination_correction": 0.0,
        }

        # Extract fields using regex
        rest = lines[1]
        fields = self._extract_fields(rest)

        for field_name, field_value in fields:
            field_upper = field_name.upper()
            value = field_value.strip()

            if field_upper == "SURVEY NAME:":
                match = self.NON_WHITESPACE.search(value)
                if match:
                    header["survey_name"] = match.group()

            elif field_upper == "SURVEY DATE:":
                parsed_date = self._parse_date(value)
                if parsed_date:
                    header["date"] = parsed_date.isoformat()

            elif field_upper == "COMMENT:":
                header["comment"] = value if value else None

            elif field_upper == "SURVEY TEAM:":
                header["team"] = value if value else None

            elif field_upper == "DECLINATION:":
                dec = self._parse_measurement(value)
                if dec is not None:
                    header["declination"] = dec

            elif field_upper == "FORMAT:":
                self._parse_shot_format_to_dict(header, value)

            elif field_upper == "CORRECTIONS:":
                parts = self.NON_WHITESPACE.findall(value)
                if len(parts) >= 1:
                    val = self._parse_measurement(parts[0])
                    if val is not None:
                        header["length_correction"] = val
                if len(parts) >= 2:
                    val = self._parse_measurement(parts[1])
                    if val is not None:
                        header["frontsight_azimuth_correction"] = val
                if len(parts) >= 3:
                    val = self._parse_measurement(parts[2])
                    if val is not None:
                        header["frontsight_inclination_correction"] = val

            elif field_upper == "CORRECTIONS2:":
                parts = self.NON_WHITESPACE.findall(value)
                if len(parts) >= 1:
                    val = self._parse_measurement(parts[0])
                    if val is not None:
                        header["backsight_azimuth_correction"] = val
                if len(parts) >= 2:
                    val = self._parse_measurement(parts[1])
                    if val is not None:
                        header["backsight_inclination_correction"] = val

        return header

    def _extract_fields(self, text: str) -> list[tuple[str, str]]:
        """Extract field name-value pairs from header text.

        Args:
            text: Header text after cave name

        Returns:
            List of (field_name, field_value) tuples
        """
        fields: list[tuple[str, str]] = []
        matches = list(self.HEADER_FIELDS.finditer(text))

        for i, match in enumerate(matches):
            field_name = match.group()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            field_value = text[start:end]
            fields.append((field_name, field_value))

        return fields

    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from text (month day year format).

        Args:
            text: Date text

        Returns:
            Parsed date or None if invalid
        """
        parts = self.NON_WHITESPACE.findall(text)
        if len(parts) < 3:
            self._add_error(f"incomplete date: {text}", text)
            return None

        try:
            month = int(parts[0])
            day = int(parts[1])
            year = int(parts[2])
        except ValueError:
            self._add_error(f"invalid date: {text}", text)
            return None

        # Handle 2-digit years (years < 100 are treated as offset from 1900)
        if year < 100:
            year += 1900

        # Validate ranges with leap year aware day validation
        if not 1 <= month <= 12:
            self._add_error(f"month must be between 1 and 12: {month}", parts[0])
            return None
        if year < 0:
            self._add_error(f"year must be >= 0: {year}", parts[2])
            return None

        max_day = days_in_month(month, year)
        if not 1 <= day <= max_day:
            self._add_error(
                f"day must be between 1 and {max_day} for month {month}: {day}",
                parts[1],
            )
            return None

        try:
            return date(year, month, day)
        except ValueError as e:
            self._add_error(f"invalid date: {e}", text)
            return None

    def _parse_measurement(self, text: str) -> Optional[float]:
        """Parse a numeric measurement from text.

        Values >= 990 indicate missing data.

        Args:
            text: Measurement text

        Returns:
            Parsed value or None if missing/invalid
        """
        try:
            value = float(text)
            if value >= MISSING_VALUE_THRESHOLD:
                return None
            return value
        except ValueError:
            return None

    def _parse_angle_measurement(self, text: str) -> Optional[float]:
        """Parse an angle measurement from text.

        Values < -900 or >= 990 indicate missing data.

        Args:
            text: Measurement text

        Returns:
            Parsed value or None if missing/invalid
        """
        try:
            value = float(text)
            if value < MISSING_ANGLE_THRESHOLD:
                return None
            if value >= MISSING_VALUE_THRESHOLD:
                return None
            return value
        except ValueError:
            return None

    def _parse_azimuth(self, text: str) -> Optional[float]:
        """Parse azimuth measurement with validation.

        Args:
            text: Azimuth text

        Returns:
            Parsed value or None if invalid
        """
        value = self._parse_angle_measurement(text)
        if value is None:
            return None
        if value < 0 or value >= 360:
            self._add_error(
                f"azimuth must be >= 0 and < 360, got {value}",
                text,
            )
            # Still return the value for continued parsing
        return value

    def _parse_inclination(self, text: str) -> Optional[float]:
        """Parse inclination measurement with validation.

        Args:
            text: Inclination text

        Returns:
            Parsed value or None if invalid
        """
        value = self._parse_angle_measurement(text)
        if value is None:
            return None
        if value < -90 or value > 90:
            self._add_error(
                f"inclination must be between -90 and 90, got {value}",
                text,
            )
            # Still return the value for continued parsing
        return value

    def _parse_distance(self, text: str) -> Optional[float]:
        """Parse distance measurement with validation (must be >= 0).

        Args:
            text: Distance text

        Returns:
            Parsed value or None if invalid
        """
        value = self._parse_measurement(text)
        if value is None:
            return None
        if value < 0:
            self._add_error(f"distance must be >= 0, got {value}", text)
        return value

    def _parse_lrud(self, text: str) -> Optional[float]:
        """Parse LRUD measurement with validation.

        Values < -1 or > 990 indicate missing data.
        Values between -1 and 0 generate an error.

        Args:
            text: LRUD text

        Returns:
            Parsed value or None if missing
        """
        try:
            value = float(text)
        except ValueError:
            return None

        # Missing data indicators
        if value < -1 or value > MISSING_VALUE_THRESHOLD:
            return None

        # Values between -1 and 0 are errors but still parse
        if value < 0:
            self._add_error(f"LRUD must be >= 0, got {value}", text)

        return value

    def _parse_shot_format_to_dict(
        self,
        header: dict[str, Any],
        format_str: str,
    ) -> None:
        """Parse the FORMAT string and update header dictionary.

        Format string structure:
        - Position 0: Azimuth unit (D/Q/R)
        - Position 1: Length unit (D/I/M)
        - Position 2: LRUD unit (D/I/M)
        - Position 3: Inclination unit (D/G/M/R/W)
        - Positions 4-7: LRUD order (L/R/U/D)
        - Positions 8-10 or 8-12: Shot order (L/A/D/a/d)
        - Optional B: Has backsights
        - Optional F/T: LRUD association

        Args:
            header: Header dictionary to update
            format_str: Format string
        """
        format_str = format_str.strip()
        if len(format_str) < 11:
            self._add_error(
                f"format must be at least 11 characters, got {len(format_str)}",
                format_str,
            )
            return

        i = 0

        # Azimuth unit
        header["azimuth_unit"] = self._parse_azimuth_unit(format_str[i]).value
        i += 1

        # Length unit
        header["length_unit"] = self._parse_length_unit_char(format_str[i]).value
        i += 1

        # LRUD unit
        header["lrud_unit"] = self._parse_length_unit_char(format_str[i]).value
        i += 1

        # Inclination unit
        header["inclination_unit"] = self._parse_inclination_unit(format_str[i]).value
        i += 1

        # LRUD order (4 characters)
        lrud_order: list[str] = []
        for j in range(4):
            if i + j < len(format_str):
                item = self._parse_lrud_item(format_str[i + j])
                if item:
                    lrud_order.append(item.value)
        if len(lrud_order) == 4:
            header["lrud_order"] = lrud_order
        i += 4

        # Shot measurement order (3 or 5 characters)
        shot_order_len = 5 if len(format_str) >= 15 else 3
        shot_order: list[str] = []
        for j in range(shot_order_len):
            if i + j < len(format_str):
                item = self._parse_shot_item(format_str[i + j])
                if item:
                    shot_order.append(item.value)
        if shot_order:
            header["shot_measurement_order"] = shot_order
        i += shot_order_len

        # Has backsights flag (B = yes, N = no, anything else means check next char)
        if i < len(format_str):
            char = format_str[i].upper()
            if char == "B":
                header["has_backsights"] = True
                i += 1
            elif char == "N":
                header["has_backsights"] = False
                i += 1
            else:
                # Assume no backsights if char is not B or N
                header["has_backsights"] = False

        # LRUD association
        if i < len(format_str):
            assoc = self._parse_lrud_association(format_str[i])
            if assoc:
                header["lrud_association"] = assoc.value

    def _parse_azimuth_unit(self, char: str) -> AzimuthUnit:
        """Parse azimuth unit character."""
        char = char.upper()
        if char == "D":
            return AzimuthUnit.DEGREES
        if char == "Q":
            return AzimuthUnit.QUADS
        if char == "R":
            return AzimuthUnit.GRADS
        self._add_error(f"unrecognized azimuth unit: {char}", char)
        return AzimuthUnit.DEGREES

    def _parse_length_unit_char(self, char: str) -> LengthUnit:
        """Parse length unit character."""
        char = char.upper()
        if char == "D":
            return LengthUnit.DECIMAL_FEET
        if char == "I":
            return LengthUnit.FEET_AND_INCHES
        if char == "M":
            return LengthUnit.METERS
        self._add_error(f"unrecognized length unit: {char}", char)
        return LengthUnit.DECIMAL_FEET

    def _parse_inclination_unit(self, char: str) -> InclinationUnit:
        """Parse inclination unit character."""
        char = char.upper()
        if char == "D":
            return InclinationUnit.DEGREES
        if char == "G":
            return InclinationUnit.PERCENT_GRADE
        if char == "M":
            return InclinationUnit.DEGREES_AND_MINUTES
        if char == "R":
            return InclinationUnit.GRADS
        if char == "W":
            return InclinationUnit.DEPTH_GAUGE
        self._add_error(f"unrecognized inclination unit: {char}", char)
        return InclinationUnit.DEGREES

    def _parse_lrud_item(self, char: str) -> Optional[LrudItem]:
        """Parse LRUD item character."""
        char = char.upper()
        if char == "L":
            return LrudItem.LEFT
        if char == "R":
            return LrudItem.RIGHT
        if char == "U":
            return LrudItem.UP
        if char == "D":
            return LrudItem.DOWN
        self._add_error(f"unrecognized LRUD item: {char}", char)
        return None

    def _parse_shot_item(self, char: str) -> Optional[ShotItem]:
        """Parse shot item character (case-sensitive for backsights)."""
        if char == "L":
            return ShotItem.LENGTH
        if char == "A":
            return ShotItem.FRONTSIGHT_AZIMUTH
        if char == "D":
            return ShotItem.FRONTSIGHT_INCLINATION
        if char == "a":
            return ShotItem.BACKSIGHT_AZIMUTH
        if char == "d":
            return ShotItem.BACKSIGHT_INCLINATION
        self._add_error(f"unrecognized shot item: {char}", char)
        return None

    def _parse_lrud_association(self, char: str) -> Optional[LrudAssociation]:
        """Parse LRUD association character."""
        char = char.upper()
        if char == "F":
            return LrudAssociation.FROM
        if char == "T":
            return LrudAssociation.TO
        self._add_error(f"unrecognized LRUD association: {char}", char)
        return None

    def _parse_shot_to_dict(
        self,
        line: str,
        header: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """Parse a single shot line to dictionary.

        Args:
            line: Shot line text
            header: Trip header dictionary with format information

        Returns:
            Shot dictionary or None if line is invalid
        """
        parts = self.NON_WHITESPACE.findall(line)
        if len(parts) < 2:
            return None

        idx = 0

        # Station names
        from_station = parts[idx]
        idx += 1
        to_station = parts[idx]
        idx += 1

        # Length
        if idx >= len(parts):
            self._add_error("missing length", line)
            return None

        length = self._parse_distance(parts[idx])
        idx += 1

        # If length is None and we've exhausted parts, skip this shot
        if length is None and idx >= len(parts):
            return None

        # Frontsight azimuth
        if idx >= len(parts):
            self._add_error("missing frontsight azimuth", line)
            return None
        fs_azimuth = self._parse_azimuth(parts[idx])
        idx += 1

        # Frontsight inclination
        if idx >= len(parts):
            self._add_error("missing frontsight inclination", line)
            return None
        fs_inclination = self._parse_inclination(parts[idx])
        idx += 1

        # LRUD values (left, up, down, right in file order)
        left = None
        up = None
        down = None
        right = None

        if idx < len(parts):
            left = self._parse_lrud(parts[idx])
            idx += 1
        if idx < len(parts):
            up = self._parse_lrud(parts[idx])
            idx += 1
        if idx < len(parts):
            down = self._parse_lrud(parts[idx])
            idx += 1
        if idx < len(parts):
            right = self._parse_lrud(parts[idx])
            idx += 1

        # Backsight values (if present)
        bs_azimuth = None
        bs_inclination = None
        has_backsights = header.get("has_backsights", True)
        if has_backsights:
            if idx < len(parts):
                bs_azimuth = self._parse_azimuth(parts[idx])
                idx += 1
            if idx < len(parts):
                bs_inclination = self._parse_inclination(parts[idx])
                idx += 1

        # Flags and comment
        excluded_from_length = False
        excluded_from_plotting = False
        excluded_from_all_processing = False
        do_not_adjust = False
        comment = None

        # Look for remaining parts (flags and comments)
        remaining = " ".join(parts[idx:]) if idx < len(parts) else ""

        # Check for flags pattern #|..#
        flag_match = re.search(r"#\|([^#]*?)#", remaining)
        if flag_match:
            flags_str = flag_match.group(1)
            for flag in flags_str:
                flag_upper = flag.upper()
                if flag_upper == "L":
                    excluded_from_length = True
                elif flag_upper == "P":
                    excluded_from_plotting = True
                elif flag_upper == "X":
                    excluded_from_all_processing = True
                elif flag_upper == "C":
                    do_not_adjust = True
                elif flag_upper == " ":
                    pass  # Spaces are allowed
                else:
                    self._add_warning(f"unrecognized flag: {flag}", flag)

            # Comment is after the flags
            comment_start = flag_match.end()
            if comment_start < len(remaining):
                comment = remaining[comment_start:].strip() or None
        else:
            # No flags, remaining is comment
            if remaining.strip():
                comment = remaining.strip()

        # Return dictionary with alias names for Pydantic
        return {
            "from_station": from_station,
            "to_station": to_station,
            "distance": length,
            "frontsight_azimuth": fs_azimuth,
            "frontsight_inclination": fs_inclination,
            "backsight_azimuth": bs_azimuth,
            "backsight_inclination": bs_inclination,
            "left": left,
            "right": right,
            "up": up,
            "down": down,
            "comment": comment,
            "exclude_distance": excluded_from_length,
            "excluded_from_plotting": excluded_from_plotting,
            "excluded_from_all_processing": excluded_from_all_processing,
            "do_not_adjust": do_not_adjust,
        }
