# -*- coding: utf-8 -*-
"""Parser for Compass .PLT plot files.

This module implements the parser for reading Compass plot files,
which contain computed 3D coordinates for cave visualization.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from compass_lib.constants import ASCII_ENCODING
from compass_lib.constants import NULL_LRUD_VALUES
from compass_lib.enums import DrawOperation
from compass_lib.enums import Severity
from compass_lib.errors import CompassParseError
from compass_lib.errors import SourceLocation
from compass_lib.models import Bounds
from compass_lib.models import Location
from compass_lib.plot.models import BeginFeatureCommand
from compass_lib.plot.models import BeginSectionCommand
from compass_lib.plot.models import BeginSurveyCommand
from compass_lib.plot.models import CaveBoundsCommand
from compass_lib.plot.models import CompassPlotCommand
from compass_lib.plot.models import DatumCommand
from compass_lib.plot.models import DrawSurveyCommand
from compass_lib.plot.models import FeatureCommand
from compass_lib.plot.models import SurveyBoundsCommand
from compass_lib.plot.models import UtmZoneCommand


class CompassPlotParser:
    """Parser for Compass .PLT plot files.

    This parser reads Compass plot files and returns a list of
    CompassPlotCommand objects. Errors are collected rather than thrown,
    allowing partial parsing of malformed files.

    Attributes:
        errors: List of parsing errors and warnings encountered
        commands: List of successfully parsed commands
    """

    # Regex patterns
    UINT_PATTERN = re.compile(r"[1-9]\d*")
    NUMBER_PATTERN = re.compile(r"[-+]?\d+\.?\d*(?:[eE][-+]?\d+)?")
    NON_WHITESPACE = re.compile(r"\S+")

    def __init__(self) -> None:
        """Initialize the parser."""
        self.errors: list[CompassParseError] = []
        self.commands: list[CompassPlotCommand] = []
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

    def parse_file(self, path: Path) -> list[CompassPlotCommand]:
        """Parse a plot file.

        Args:
            path: Path to the .PLT file

        Returns:
            List of parsed commands
        """
        self._source = str(path)
        with path.open(mode="r", encoding=ASCII_ENCODING, errors="replace") as f:
            return self.parse_lines(f, str(path))

    def parse_string(
        self,
        data: str,
        source: str = "<string>",
    ) -> list[CompassPlotCommand]:
        """Parse plot data from a string.

        Args:
            data: Plot file content
            source: Source identifier for error messages

        Returns:
            List of parsed commands
        """
        self._source = source
        lines = data.split("\n")
        return self._parse_lines_list(lines, source)

    def parse_lines(
        self,
        file_obj,
        source: str = "<string>",
    ) -> list[CompassPlotCommand]:
        """Parse plot data from a file object.

        Args:
            file_obj: File-like object to read from
            source: Source identifier for error messages

        Returns:
            List of parsed commands
        """
        self._source = source
        commands: list[CompassPlotCommand] = []

        for line_num, line in enumerate(file_obj):
            _line = line.strip()
            if not _line:
                continue

            try:
                command = self._parse_command(_line, line_num)
                if command:
                    commands.append(command)
            except Exception as e:  # noqa: BLE001
                self._add_error(str(e), _line, line_num)

        self.commands.extend(commands)
        return commands

    def _parse_lines_list(
        self,
        lines: list[str],
        source: str,
    ) -> list[CompassPlotCommand]:
        """Parse lines from a list."""
        self._source = source
        commands: list[CompassPlotCommand] = []

        for line_num, line in enumerate(lines):
            _line = line.strip()
            if not _line:
                continue

            try:
                command = self._parse_command(_line, line_num)
                if command:
                    commands.append(command)
            except Exception as e:  # noqa: BLE001
                self._add_error(str(e), _line, line_num)

        self.commands.extend(commands)
        return commands

    def _parse_command(  # noqa: PLR0911
        self,
        line: str,
        line_num: int,
    ) -> CompassPlotCommand | None:
        """Parse a single command line.

        Args:
            line: Command line text
            line_num: Line number for error reporting

        Returns:
            Parsed command or None if unknown/invalid
        """
        if not line:
            return None

        cmd = line[0]
        rest = line[1:]

        if cmd in ("M", "D"):
            return self._parse_draw_command(cmd, rest, line_num)
        if cmd == "N":
            return self._parse_begin_survey(rest, line_num)
        if cmd == "F":
            return self._parse_begin_feature(rest, line_num)
        if cmd == "S":
            return self._parse_begin_section(rest, line_num)
        if cmd == "L":
            return self._parse_feature_command(rest, line_num)
        if cmd == "X":
            return self._parse_survey_bounds(rest, line_num)
        if cmd == "Z":
            return self._parse_cave_bounds(rest, line_num)
        if cmd == "O":
            return self._parse_datum(rest, line_num)
        if cmd == "G":
            return self._parse_utm_zone(rest, line_num)

        # Unknown command - ignore silently (many undocumented commands exist)
        return None

    def _parse_number(
        self,
        text: str,
        line_num: int,
        field_name: str,
    ) -> float | None:
        """Parse a number, returning None on failure."""
        text = text.strip()
        try:
            return float(text)
        except ValueError:
            self._add_error(f"invalid {field_name}: {text}", text, line_num)
            return None

    def _parse_lrud(
        self,
        text: str,
        line_num: int,
        field_name: str,
    ) -> float | None:
        """Parse LRUD measurement.

        Returns None for missing data indicators (negative or 999/999.9).
        """
        value = self._parse_number(text, line_num, field_name)
        if value is None:
            return None

        # Null indicators
        if value < 0 or value in NULL_LRUD_VALUES:
            return None

        return value

    def _parse_date(
        self,
        parts: list[str],
        start_idx: int,
        line_num: int,
    ) -> tuple[date | None, int]:
        """Parse date from parts (month day year).

        Returns (date, new_index) tuple.
        """
        if start_idx + 2 >= len(parts):
            self._add_error("incomplete date", "", line_num)
            return None, start_idx

        try:
            month = int(parts[start_idx])
            day = int(parts[start_idx + 1])
            year = int(parts[start_idx + 2])

            if month < 1 or month > 12:
                self._add_error(
                    f"month must be between 1 and 12: {month}", "", line_num
                )
                return None, start_idx + 3

            if day < 1 or day > 31:
                self._add_error(f"day must be between 1 and 31: {day}", "", line_num)
                return None, start_idx + 3

            return date(year, month, day), start_idx + 3
        except ValueError as e:
            self._add_error(f"invalid date: {e}", "", line_num)
            return None, start_idx + 3

    def _parse_draw_command(
        self,
        cmd: str,
        rest: str,
        line_num: int,
    ) -> DrawSurveyCommand | None:
        """Parse M (move) or D (draw) command."""
        operation = DrawOperation.MOVE_TO if cmd == "M" else DrawOperation.LINE_TO
        parts = rest.split()

        if len(parts) < 3:
            self._add_error(
                "draw command requires at least 3 coordinates",
                rest,
                line_num,
            )
            return None

        northing = self._parse_number(parts[0], line_num, "northing")
        easting = self._parse_number(parts[1], line_num, "easting")
        vertical = self._parse_number(parts[2], line_num, "vertical")

        command = DrawSurveyCommand(
            operation=operation,
            location=Location(
                northing=northing,
                easting=easting,
                vertical=vertical,
            ),
        )

        # Parse subcommands
        idx = 3
        while idx < len(parts):
            subcmd = parts[idx]
            idx += 1

            if subcmd.startswith("S"):
                # Station name
                command.station_name = subcmd[1:] if len(subcmd) > 1 else None
                if not command.station_name and idx < len(parts):
                    command.station_name = parts[idx]
                    idx += 1

            elif subcmd == "P":
                # LRUD: left, up, down, right (in this order for draw commands)
                if idx + 3 < len(parts):
                    command.left = self._parse_lrud(parts[idx], line_num, "left")
                    idx += 1
                    command.up = self._parse_lrud(parts[idx], line_num, "up")
                    idx += 1
                    command.down = self._parse_lrud(parts[idx], line_num, "down")
                    idx += 1
                    command.right = self._parse_lrud(parts[idx], line_num, "right")
                    idx += 1

            elif subcmd == "I":
                # Distance from entrance
                if idx < len(parts):
                    dist = self._parse_number(
                        parts[idx],
                        line_num,
                        "distance from entrance",
                    )
                    if dist is not None:
                        if dist < 0:
                            self._add_warning(
                                "distance from entrance is negative",
                                parts[idx],
                                line_num,
                            )
                        command.distance_from_entrance = dist
                    idx += 1
                # Stop parsing after I (undocumented commands may follow)
                break

        return command

    def _parse_feature_command(
        self,
        rest: str,
        line_num: int,
    ) -> FeatureCommand | None:
        """Parse L (feature) command."""
        parts = rest.split()

        if len(parts) < 3:
            self._add_error(
                "feature command requires at least 3 coordinates",
                rest,
                line_num,
            )
            return None

        northing = self._parse_number(parts[0], line_num, "northing")
        easting = self._parse_number(parts[1], line_num, "easting")
        vertical = self._parse_number(parts[2], line_num, "vertical")

        command = FeatureCommand(
            location=Location(
                northing=northing,
                easting=easting,
                vertical=vertical,
            ),
        )

        # Parse subcommands
        idx = 3
        while idx < len(parts):
            subcmd = parts[idx]
            idx += 1

            if subcmd.startswith("S"):
                # Station name
                command.station_name = subcmd[1:] if len(subcmd) > 1 else None
                if not command.station_name and idx < len(parts):
                    command.station_name = parts[idx]
                    idx += 1

            elif subcmd == "P":
                # LRUD: left, right, up, down (different order than draw!)
                if idx + 3 < len(parts):
                    command.left = self._parse_lrud(parts[idx], line_num, "left")
                    idx += 1
                    command.right = self._parse_lrud(parts[idx], line_num, "right")
                    idx += 1
                    command.up = self._parse_lrud(parts[idx], line_num, "up")
                    idx += 1
                    command.down = self._parse_lrud(parts[idx], line_num, "down")
                    idx += 1

            elif subcmd == "V":
                # Feature value
                if idx < len(parts):
                    try:
                        command.value = Decimal(parts[idx])
                    except Exception:  # noqa: BLE001
                        self._add_error(
                            f"invalid value: {parts[idx]}",
                            parts[idx],
                            line_num,
                        )
                    idx += 1

        return command

    def _parse_begin_survey(
        self,
        rest: str,
        line_num: int,
    ) -> BeginSurveyCommand:
        """Parse N (begin survey) command."""
        parts = rest.split()

        if not parts:
            self._add_error("missing survey name", rest, line_num)
            return BeginSurveyCommand(survey_name="")

        survey_name = parts[0]
        command = BeginSurveyCommand(survey_name=survey_name)

        # Parse subcommands
        idx = 1
        while idx < len(parts):
            subcmd = parts[idx]
            idx += 1

            if subcmd == "D":
                # Date
                parsed_date, idx = self._parse_date(parts, idx, line_num)
                command.date = parsed_date

            elif subcmd == "C" or subcmd.startswith("C"):
                # Comment (rest of line)
                if subcmd == "C":
                    command.comment = " ".join(parts[idx:]).strip()
                else:
                    command.comment = (subcmd[1:] + " " + " ".join(parts[idx:])).strip()
                break

        return command

    def _parse_begin_section(
        self,
        rest: str,
        line_num: int,
    ) -> BeginSectionCommand:
        """Parse S (begin section) command."""
        # Section name is the rest of the line
        return BeginSectionCommand(section_name=rest.strip())

    def _parse_begin_feature(
        self,
        rest: str,
        line_num: int,
    ) -> BeginFeatureCommand:
        """Parse F (begin feature) command."""
        parts = rest.split()

        if not parts:
            self._add_error("missing feature name", rest, line_num)
            return BeginFeatureCommand(feature_name="")

        feature_name = parts[0]
        command = BeginFeatureCommand(feature_name=feature_name)

        # Look for R min max
        idx = 1
        while idx < len(parts):
            if parts[idx] == "R" and idx + 2 < len(parts):
                idx += 1
                try:
                    command.min_value = Decimal(parts[idx])
                    idx += 1
                    command.max_value = Decimal(parts[idx])
                    idx += 1
                except Exception:  # noqa: BLE001
                    self._add_error("invalid feature range", rest, line_num)
            else:
                idx += 1

        return command

    def _parse_bounds(
        self,
        parts: list[str],
        start_idx: int,
        line_num: int,
    ) -> tuple[Bounds, int]:
        """Parse bounds (minN maxN minE maxE minV maxV).

        Returns (Bounds, new_index) tuple.
        """
        bounds = Bounds()
        idx = start_idx

        if idx + 5 < len(parts):
            min_n = self._parse_number(parts[idx], line_num, "min northing")
            idx += 1
            max_n = self._parse_number(parts[idx], line_num, "max northing")
            idx += 1
            min_e = self._parse_number(parts[idx], line_num, "min easting")
            idx += 1
            max_e = self._parse_number(parts[idx], line_num, "max easting")
            idx += 1
            min_v = self._parse_number(parts[idx], line_num, "min vertical")
            idx += 1
            max_v = self._parse_number(parts[idx], line_num, "max vertical")
            idx += 1

            bounds.lower = Location(northing=min_n, easting=min_e, vertical=min_v)
            bounds.upper = Location(northing=max_n, easting=max_e, vertical=max_v)

        return bounds, idx

    def _parse_survey_bounds(
        self,
        rest: str,
        line_num: int,
    ) -> SurveyBoundsCommand:
        """Parse X (survey bounds) command."""
        parts = rest.split()
        bounds, _ = self._parse_bounds(parts, 0, line_num)
        return SurveyBoundsCommand(bounds=bounds)

    def _parse_cave_bounds(
        self,
        rest: str,
        line_num: int,
    ) -> CaveBoundsCommand:
        """Parse Z (cave bounds) command."""
        parts = rest.split()
        bounds, idx = self._parse_bounds(parts, 0, line_num)

        command = CaveBoundsCommand(bounds=bounds)

        # Look for I (distance to farthest station)
        while idx < len(parts):
            if parts[idx] == "I" and idx + 1 < len(parts):
                idx += 1
                dist = self._parse_number(
                    parts[idx],
                    line_num,
                    "distance to farthest station",
                )
                if dist is not None:
                    if dist < 0:
                        self._add_warning(
                            "distance to farthest station is negative",
                            parts[idx],
                            line_num,
                        )
                    command.distance_to_farthest_station = dist
                idx += 1
            else:
                idx += 1

        return command

    def _parse_datum(
        self,
        rest: str,
        line_num: int,
    ) -> DatumCommand:
        """Parse O (datum) command."""
        datum = rest.split(maxsplit=1)[0] if rest.split() else rest.strip()
        return DatumCommand(datum=datum)

    def _parse_utm_zone(
        self,
        rest: str,
        line_num: int,
    ) -> UtmZoneCommand:
        """Parse G (UTM zone) command."""
        utm_zone = rest.split(maxsplit=1)[0] if rest.split() else rest.strip()
        return UtmZoneCommand(utm_zone=utm_zone)
