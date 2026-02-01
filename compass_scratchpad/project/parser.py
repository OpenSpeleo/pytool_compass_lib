# -*- coding: utf-8 -*-
"""Parser for Compass .MAK project files.

This module implements the parser for reading Compass project files,
which define project structure, geographic settings, and data file references.

Architecture: The parser produces dictionaries (like loading JSON) which are
then fed to Pydantic models via a single `model_validate()` call. This keeps
parsing logic separate from model construction.
"""

import re
from pathlib import Path
from typing import Any

from compass_scratchpad.constants import ASCII_ENCODING
from compass_scratchpad.constants import FORMAT_COMPASS_MAK
from compass_scratchpad.errors import CompassParseException
from compass_scratchpad.errors import SourceLocation


class CompassProjectParser:
    """Parser for Compass .MAK project files.

    This parser reads Compass project files and produces dictionaries
    (like loading JSON from disk). The dictionaries can then be fed to
    Pydantic models via a single `model_validate()` call.

    The parser is strict - it raises CompassParseException on errors.
    """

    # Regex patterns
    EOL_PATTERN = re.compile(r"\r\n?|\n")
    FILE_NAME_PATTERN = re.compile(r"[^,;/]+")
    DATUM_PATTERN = re.compile(r"[^;/]+")
    LINK_STATION_PATTERN = re.compile(r"[^,;/\[]+")
    NUMBER_PATTERN = re.compile(r"[-+]?\d+(\.\d*)?|\.\d+")

    def __init__(self) -> None:
        """Initialize the parser."""
        self._data: str = ""
        self._pos: int = 0
        self._source: str = "<string>"
        self._line: int = 0

    # -------------------------------------------------------------------------
    # Dictionary-returning methods (primary API)
    # -------------------------------------------------------------------------

    def parse_file_to_dict(self, path: Path) -> dict[str, Any]:
        """Parse a project file to dictionary.

        This is the primary parsing method. It returns a dictionary that
        can be directly fed to `CompassMakFile.model_validate()`.

        Args:
            path: Path to the .MAK file

        Returns:
            Dictionary with directives list

        Raises:
            CompassParseException: On parse errors
        """
        with open(path, encoding=ASCII_ENCODING, errors="replace") as f:
            data = f.read()
        return self.parse_string_to_dict(data, str(path))

    def parse_string_to_dict(
        self,
        data: str,
        source: str = "<string>",
    ) -> dict[str, Any]:
        """Parse project data from a string to dictionary.

        Args:
            data: Project file content
            source: Source identifier for error messages

        Returns:
            Dictionary with directives list

        Raises:
            CompassParseException: On parse errors
        """
        self._data = data
        self._pos = 0
        self._source = source
        self._line = 0

        directives: list[dict[str, Any]] = []

        while self._pos < len(self._data):
            self._skip_whitespace()
            if self._pos >= len(self._data):
                break

            char = self._data[self._pos]
            self._pos += 1

            if char == "#":
                directives.append(self._parse_survey_file_to_dict())
            elif char == "@":
                directives.append(self._parse_location_to_dict())
            elif char == "&":
                directives.append(self._parse_datum_to_dict())
            elif char == "%":
                directives.append(self._parse_utm_convergence_to_dict(enabled=True))
            elif char == "*":
                directives.append(self._parse_utm_convergence_to_dict(enabled=False))
            elif char == "$":
                directives.append(self._parse_utm_zone_to_dict())
            elif char == "!":
                directives.append(self._parse_flags_to_dict())
            elif char == "[":
                directives.append(self._parse_folder_start_to_dict())
            elif char == "]":
                directives.append(self._parse_folder_end_to_dict())
            elif char == "/":
                directives.append(self._parse_comment_to_dict())
            elif ord(char) >= 0x20:
                # Unknown directive - parse to semicolon for roundtrip fidelity
                directives.append(self._parse_unknown_directive_to_dict(char))

        return {
            "version": "1.0",
            "format": FORMAT_COMPASS_MAK,
            "directives": directives,
        }

    # -------------------------------------------------------------------------
    # Legacy model-returning methods (thin wrappers for backwards compat)
    # -------------------------------------------------------------------------

    def parse_file(self, path: Path) -> list["CompassProjectDirective"]:  # noqa: F821
        """Parse a project file.

        DEPRECATED: Use parse_file_to_dict() for new code.

        Args:
            path: Path to the .MAK file

        Returns:
            List of parsed directives

        Raises:
            CompassParseException: On parse errors
        """
        from compass_scratchpad.project.models import CompassMakFile

        data = self.parse_file_to_dict(path)
        mak_file = CompassMakFile.model_validate(data)
        return mak_file.directives

    def parse_string(
        self,
        data: str,
        source: str = "<string>",
    ) -> list["CompassProjectDirective"]:  # noqa: F821
        """Parse project data from a string.

        DEPRECATED: Use parse_string_to_dict() for new code.

        Args:
            data: Project file content
            source: Source identifier for error messages

        Returns:
            List of parsed directives

        Raises:
            CompassParseException: On parse errors
        """
        from compass_scratchpad.project.models import CompassMakFile

        parsed = self.parse_string_to_dict(data, source)
        mak_file = CompassMakFile.model_validate(parsed)
        return mak_file.directives

    def _location(self, text: str = "") -> SourceLocation:
        """Create a SourceLocation at current position."""
        return SourceLocation(
            source=self._source,
            line=self._line,
            column=self._pos - 1,
            text=text,
        )

    def _skip_whitespace(self) -> None:
        """Skip whitespace characters, tracking line numbers."""
        while self._pos < len(self._data):
            char = self._data[self._pos]
            if char == "\n":
                self._line += 1
                self._pos += 1
            elif char == "\r":
                self._line += 1
                self._pos += 1
                if self._pos < len(self._data) and self._data[self._pos] == "\n":
                    self._pos += 1
            elif char.isspace():
                self._pos += 1
            else:
                break

    def _skip_whitespace_and_comments(self) -> None:
        """Skip whitespace and inline comments."""
        self._skip_whitespace()
        while self._pos < len(self._data) and self._data[self._pos] == "/":
            self._pos += 1
            self._skip_to_end_of_line()
            self._skip_whitespace()

    def _skip_to_end_of_line(self) -> None:
        """Skip to end of current line."""
        while self._pos < len(self._data):
            char = self._data[self._pos]
            if char == "\n":
                self._line += 1
                self._pos += 1
                break
            if char == "\r":
                self._line += 1
                self._pos += 1
                if self._pos < len(self._data) and self._data[self._pos] == "\n":
                    self._pos += 1
                break
            self._pos += 1

    def _expect(self, char: str) -> None:
        """Expect a specific character.

        Raises:
            CompassParseError: If character doesn't match
        """
        if self._pos >= len(self._data):
            raise CompassParseException(
                f"expected {char}, got end of file",
                self._location(),
            )
        if self._data[self._pos] != char:
            raise CompassParseException(
                f"expected {char}, got {self._data[self._pos]}",
                self._location(self._data[self._pos]),
            )
        self._pos += 1

    def _expect_match(
        self,
        pattern: re.Pattern[str],
        error_msg: str,
    ) -> str:
        """Match a pattern at current position.

        Args:
            pattern: Regex pattern to match
            error_msg: Error message if no match

        Returns:
            Matched text

        Raises:
            CompassParseError: If no match
        """
        match = pattern.match(self._data, self._pos)
        if not match or match.start() != self._pos:
            raise CompassParseException(error_msg, self._location())
        self._pos = match.end()
        return match.group()

    def _expect_number(self, error_msg: str) -> float:
        """Parse a number at current position.

        Args:
            error_msg: Error message if no number

        Returns:
            Parsed number

        Raises:
            CompassParseError: If no valid number
        """
        text = self._expect_match(self.NUMBER_PATTERN, error_msg)
        return float(text)

    def _expect_utm_zone(self, *, allow_zero: bool = False) -> int:
        """Parse UTM zone (integer 1-60, or 0 if allow_zero).

        Args:
            allow_zero: If True, allows zone 0 (meaning "not specified")

        Returns:
            UTM zone number

        Raises:
            CompassParseError: If invalid zone
        """
        text = self._expect_match(self.NUMBER_PATTERN, "missing UTM zone")

        if "." in text:
            raise CompassParseException(
                "invalid UTM zone (not an integer)", self._location(text)
            )

        zone = int(text)
        min_zone = 0 if allow_zero else 1
        if zone < min_zone or zone > 60:
            raise CompassParseException(
                f"UTM zone must be between {min_zone} and 60, got {zone}",
                self._location(text),
            )
        return zone

    def _parse_length_unit(self) -> str:
        """Parse length unit (f or m).

        Returns:
            'f' for feet, 'm' for meters

        Raises:
            CompassParseError: If invalid unit
        """
        if self._pos >= len(self._data):
            raise CompassParseException("missing length unit", self._location())

        char = self._data[self._pos].lower()
        if char not in ("f", "m"):
            raise CompassParseException(
                f"invalid length unit: {char}",
                self._location(char),
            )
        self._pos += 1
        return char

    def _parse_survey_file_to_dict(self) -> dict[str, Any]:
        """Parse #filename,station[location],...; to dictionary."""
        file_name = self._expect_match(
            self.FILE_NAME_PATTERN,
            "missing file name",
        ).strip()

        link_stations: list[dict[str, Any]] = []

        while True:
            self._skip_whitespace_and_comments()

            if self._pos >= len(self._data):
                raise CompassParseException(
                    "missing ; at end of file line",
                    self._location(),
                )

            char = self._data[self._pos]
            self._pos += 1

            if char == ";":
                return {
                    "type": "file",
                    "file": file_name,
                    "link_stations": link_stations,
                }

            if char == ",":
                self._skip_whitespace_and_comments()
                station_name = self._expect_match(
                    self.LINK_STATION_PATTERN,
                    "missing station name",
                ).strip()

                location = None
                self._skip_whitespace_and_comments()

                if self._pos < len(self._data) and self._data[self._pos] == "[":
                    self._pos += 1
                    self._skip_whitespace_and_comments()

                    unit = self._parse_length_unit()
                    self._skip_whitespace_and_comments()
                    self._expect(",")
                    self._skip_whitespace_and_comments()

                    easting = self._expect_number("missing easting")
                    self._skip_whitespace_and_comments()
                    self._expect(",")
                    self._skip_whitespace_and_comments()

                    northing = self._expect_number("missing northing")
                    self._skip_whitespace_and_comments()
                    self._expect(",")
                    self._skip_whitespace_and_comments()

                    elevation = self._expect_number("missing elevation")
                    self._skip_whitespace_and_comments()
                    self._expect("]")

                    location = {
                        "easting": easting,
                        "northing": northing,
                        "elevation": elevation,
                        "unit": unit,
                    }

                link_stations.append({"name": station_name, "location": location})
            else:
                raise CompassParseException(
                    f"unexpected character: {char}",
                    self._location(char),
                )

    def _parse_location_to_dict(self) -> dict[str, Any]:
        """Parse @easting,northing,elevation,zone,convergence; to dictionary.

        Note: UTM zone of 0 is allowed here, meaning "no location specified"
        (commonly used when only declination information is needed).
        """
        self._skip_whitespace()
        easting = self._expect_number("missing easting")
        self._skip_whitespace()
        self._expect(",")
        self._skip_whitespace()
        northing = self._expect_number("missing northing")
        self._skip_whitespace()
        self._expect(",")
        self._skip_whitespace()
        elevation = self._expect_number("missing elevation")
        self._skip_whitespace()
        self._expect(",")
        self._skip_whitespace()
        utm_zone = self._expect_utm_zone(allow_zero=True)
        self._skip_whitespace()
        self._expect(",")
        self._skip_whitespace()
        convergence = self._expect_number("missing UTM convergence")
        self._expect(";")

        return {
            "type": "location",
            "easting": easting,
            "northing": northing,
            "elevation": elevation,
            "utm_zone": utm_zone,
            "utm_convergence": convergence,
        }

    def _parse_datum_to_dict(self) -> dict[str, Any]:
        """Parse &datum_name; to dictionary."""
        datum = self._expect_match(self.DATUM_PATTERN, "missing datum").strip()
        self._expect(";")
        return {"type": "datum", "datum": datum}

    def _parse_utm_convergence_to_dict(self, *, enabled: bool) -> dict[str, Any]:
        """Parse %convergence; or *convergence; to dictionary.

        Args:
            enabled: True if parsed from %, False if parsed from *
        """
        self._skip_whitespace()
        convergence = self._expect_number("missing UTM convergence")
        self._expect(";")
        return {
            "type": "utm_convergence",
            "utm_convergence": convergence,
            "enabled": enabled,
        }

    def _parse_utm_zone_to_dict(self) -> dict[str, Any]:
        """Parse $zone; to dictionary."""
        self._skip_whitespace()
        zone = self._expect_utm_zone()
        self._expect(";")
        return {"type": "utm_zone", "utm_zone": zone}

    def _parse_flags_to_dict(self) -> dict[str, Any]:
        """Parse !flags; to dictionary.

        Parses all 10 documented Compass project flags:
        1. G/g - Global override settings enabled/disabled
        2. I/E/A - Declination mode (Ignore/Entered/Auto)
        3. V/v - Apply UTM convergence enabled/disabled
        4. O/o - Override LRUD associations enabled/disabled
        5. T/t - LRUDs at To/From station
        6. S/s - Apply shot flags enabled/disabled
        7. X/x - Apply total exclusion flags enabled/disabled
        8. P/p - Apply plotting exclusion flags enabled/disabled
        9. L/l - Apply length exclusion flags enabled/disabled
        10. C/c - Apply close exclusion flags enabled/disabled
        """
        start_pos = self._pos

        # Initialize all flags
        result: dict[str, Any] = {
            "type": "flags",
            "global_override": False,
            "declination_mode": None,
            "apply_utm_convergence": False,
            "override_lruds": False,
            "lruds_at_to_station": False,
            "apply_shot_flags": False,
            "apply_total_exclusion": False,
            "apply_plotting_exclusion": False,
            "apply_length_exclusion": False,
            "apply_close_exclusion": False,
        }

        while self._pos < len(self._data):
            char = self._data[self._pos]
            self._pos += 1

            if char == ";":
                result["raw_flags"] = self._data[start_pos : self._pos - 1]
                return result

            # Flag 1: G/g - Global override
            if char == "G":
                result["global_override"] = True
            elif char == "g":
                result["global_override"] = False

            # Flag 2: I/E/A - Declination mode
            elif char == "I":
                result["declination_mode"] = "I"
            elif char == "E":
                result["declination_mode"] = "E"
            elif char == "A":
                result["declination_mode"] = "A"

            # Flag 3: V/v - Apply UTM convergence
            elif char == "V":
                result["apply_utm_convergence"] = True
            elif char == "v":
                result["apply_utm_convergence"] = False

            # Flag 4: O/o - Override LRUD associations
            elif char == "O":
                result["override_lruds"] = True
            elif char == "o":
                result["override_lruds"] = False

            # Flag 5: T/t - LRUDs at To station
            elif char == "T":
                result["lruds_at_to_station"] = True
            elif char == "t":
                result["lruds_at_to_station"] = False

            # Flag 6: S/s - Apply shot flags
            elif char == "S":
                result["apply_shot_flags"] = True
            elif char == "s":
                result["apply_shot_flags"] = False

            # Flag 7: X/x - Apply total exclusion flags
            elif char == "X":
                result["apply_total_exclusion"] = True
            elif char == "x":
                result["apply_total_exclusion"] = False

            # Flag 8: P/p - Apply plotting exclusion flags
            elif char == "P":
                result["apply_plotting_exclusion"] = True
            elif char == "p":
                result["apply_plotting_exclusion"] = False

            # Flag 9: L/l - Apply length exclusion flags
            elif char == "L":
                result["apply_length_exclusion"] = True
            elif char == "l":
                result["apply_length_exclusion"] = False

            # Flag 10: C/c - Apply close exclusion flags
            elif char == "C":
                result["apply_close_exclusion"] = True
            elif char == "c":
                result["apply_close_exclusion"] = False

            # Silently skip unknown characters for lenient parsing

        raise CompassParseException(
            "missing or incomplete flags",
            self._location(),
        )

    def _parse_folder_start_to_dict(self) -> dict[str, Any]:
        """Parse [FolderName; to dictionary."""
        self._skip_whitespace()
        # Read until semicolon
        start = self._pos
        while self._pos < len(self._data) and self._data[self._pos] != ";":
            self._pos += 1
        name = self._data[start : self._pos].strip()
        self._expect(";")
        return {"type": "folder_start", "name": name}

    def _parse_folder_end_to_dict(self) -> dict[str, Any]:
        """Parse ]; to dictionary."""
        self._skip_whitespace()
        self._expect(";")
        return {"type": "folder_end"}

    def _parse_comment_to_dict(self) -> dict[str, Any]:
        """Parse / comment (to end of line) to dictionary."""
        start = self._pos
        self._skip_to_end_of_line()
        comment = self._data[start : self._pos].strip()
        return {"type": "comment", "comment": comment}

    def _parse_unknown_directive_to_dict(self, directive_type: str) -> dict[str, Any]:
        """Parse unknown directive to semicolon for roundtrip fidelity."""
        start = self._pos

        while self._pos < len(self._data):
            char = self._data[self._pos]
            if char == ";":
                content = self._data[start : self._pos]
                self._pos += 1  # Skip the semicolon
                return {
                    "type": "unknown",
                    "directive_type": directive_type,
                    "content": content,
                }
            self._pos += 1

        # No semicolon found - use rest of data
        content = self._data[start : self._pos]
        return {
            "type": "unknown",
            "directive_type": directive_type,
            "content": content,
        }
