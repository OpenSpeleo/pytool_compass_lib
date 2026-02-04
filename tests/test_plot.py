# -*- coding: utf-8 -*-
"""Tests for plot module."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from compass_scratchpad.enums import Datum
from compass_scratchpad.enums import DrawOperation
from compass_scratchpad.enums import Severity
from compass_scratchpad.plot.models import BeginFeatureCommand
from compass_scratchpad.plot.models import BeginSectionCommand
from compass_scratchpad.plot.models import BeginSurveyCommand
from compass_scratchpad.plot.models import CaveBoundsCommand
from compass_scratchpad.plot.models import DatumCommand
from compass_scratchpad.plot.models import DrawSurveyCommand
from compass_scratchpad.plot.models import FeatureCommand
from compass_scratchpad.plot.models import SurveyBoundsCommand
from compass_scratchpad.plot.models import UtmZoneCommand
from compass_scratchpad.plot.parser import CompassPlotParser


class TestBeginSurveyCommand:
    """Tests for BeginSurveyCommand model."""

    def test_creation(self):
        """Test creating a begin survey command."""
        cmd = BeginSurveyCommand(
            survey_name="Z+",
            date=date(1994, 6, 29),
            comment="Stream Passage",
        )
        assert cmd.survey_name == "Z+"
        assert cmd.date == date(1994, 6, 29)
        assert cmd.comment == "Stream Passage"

    def test_str_with_date(self):
        """Test string representation with date."""
        cmd = BeginSurveyCommand(
            survey_name="Z+",
            date=date(1994, 6, 29),
            comment="Stream Passage",
        )
        result = str(cmd)
        assert result.startswith("NZ+")
        assert "D 6 29 1994" in result
        assert "CStream Passage" in result

    def test_str_without_date(self):
        """Test string representation without date."""
        cmd = BeginSurveyCommand(survey_name="TEST")
        result = str(cmd)
        assert "D 1 1 1" in result


class TestBeginSectionCommand:
    """Tests for BeginSectionCommand model."""

    def test_creation(self):
        """Test creating a begin section command."""
        cmd = BeginSectionCommand(section_name="FULFORD CAVE")
        assert cmd.section_name == "FULFORD CAVE"

    def test_str(self):
        """Test string representation."""
        cmd = BeginSectionCommand(section_name="FULFORD CAVE")
        assert str(cmd) == "SFULFORD CAVE"


class TestBeginFeatureCommand:
    """Tests for BeginFeatureCommand model."""

    def test_creation(self):
        """Test creating a begin feature command."""
        cmd = BeginFeatureCommand(feature_name="INSECTS")
        assert cmd.feature_name == "INSECTS"
        assert cmd.min_value is None
        assert cmd.max_value is None

    def test_creation_with_range(self):
        """Test creating a begin feature command with range."""
        cmd = BeginFeatureCommand(
            feature_name="WATER",
            min_value=Decimal("551.234"),
            max_value=Decimal("812.341"),
        )
        assert cmd.feature_name == "WATER"
        assert cmd.min_value == Decimal("551.234")
        assert cmd.max_value == Decimal("812.341")

    def test_str_without_range(self):
        """Test string representation without range."""
        cmd = BeginFeatureCommand(feature_name="INSECTS")
        assert str(cmd) == "FINSECTS"

    def test_str_with_range(self):
        """Test string representation with range."""
        cmd = BeginFeatureCommand(
            feature_name="WATER",
            min_value=Decimal("100"),
            max_value=Decimal("200"),
        )
        result = str(cmd)
        assert "FWATER" in result
        assert "R" in result


class TestDrawSurveyCommand:
    """Tests for DrawSurveyCommand model."""

    def test_creation_move(self):
        """Test creating a move command."""
        cmd = DrawSurveyCommand(operation=DrawOperation.MOVE_TO)
        assert cmd.operation == DrawOperation.MOVE_TO

    def test_creation_draw(self):
        """Test creating a draw command."""
        cmd = DrawSurveyCommand(operation=DrawOperation.LINE_TO)
        assert cmd.operation == DrawOperation.LINE_TO

    def test_str_move(self):
        """Test string representation of move command."""
        cmd = DrawSurveyCommand(operation=DrawOperation.MOVE_TO)
        assert str(cmd).startswith("M")

    def test_str_draw(self):
        """Test string representation of draw command."""
        cmd = DrawSurveyCommand(operation=DrawOperation.LINE_TO)
        assert str(cmd).startswith("D")


class TestFeatureCommand:
    """Tests for FeatureCommand model."""

    def test_creation(self):
        """Test creating a feature command."""
        cmd = FeatureCommand()
        assert cmd.station_name is None
        assert cmd.value is None

    def test_str(self):
        """Test string representation."""
        cmd = FeatureCommand(value=Decimal("551.234"))
        result = str(cmd)
        assert result.startswith("L")
        assert "V" in result


class TestSurveyBoundsCommand:
    """Tests for SurveyBoundsCommand model."""

    def test_creation(self):
        """Test creating a survey bounds command."""
        cmd = SurveyBoundsCommand()
        assert cmd.bounds.lower.northing is None

    def test_str(self):
        """Test string representation."""
        cmd = SurveyBoundsCommand()
        cmd.bounds.lower.northing = 100.0
        cmd.bounds.upper.northing = 200.0
        result = str(cmd)
        assert result.startswith("X")


class TestCaveBoundsCommand:
    """Tests for CaveBoundsCommand model."""

    def test_creation(self):
        """Test creating a cave bounds command."""
        cmd = CaveBoundsCommand()
        assert cmd.distance_to_farthest_station is None

    def test_str_with_distance(self):
        """Test string representation with distance."""
        cmd = CaveBoundsCommand(distance_to_farthest_station=1357.3)
        result = str(cmd)
        assert result.startswith("Z")
        assert "I" in result


class TestDatumCommand:
    """Tests for DatumCommand model."""

    def test_creation(self):
        """Test creating a datum command."""
        cmd = DatumCommand(datum="WGS 1984")
        assert cmd.datum == Datum.WGS_1984
        assert isinstance(cmd.datum, Datum)

    def test_str(self):
        """Test string representation."""
        cmd = DatumCommand(datum="WGS 1984")
        assert str(cmd) == "OWGS 1984"


class TestUtmZoneCommand:
    """Tests for UtmZoneCommand model."""

    def test_creation(self):
        """Test creating a UTM zone command."""
        cmd = UtmZoneCommand(utm_zone="13")
        assert cmd.utm_zone == "13"

    def test_str(self):
        """Test string representation."""
        cmd = UtmZoneCommand(utm_zone="13")
        assert str(cmd) == "G13"


class TestCompassPlotParser:
    """Tests for CompassPlotParser."""

    def test_parse_draw_command(self):
        """Test parsing M/D commands."""
        parser = CompassPlotParser()
        line = "D   128.2   -65.9   -86.8  SZ7  P    0.0    3.0    1.0    2.0  I   21.8"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, DrawSurveyCommand)
        assert cmd.operation == DrawOperation.LINE_TO
        assert cmd.location.northing == pytest.approx(128.2)
        assert cmd.location.easting == pytest.approx(-65.9)
        assert cmd.location.vertical == pytest.approx(-86.8)
        assert cmd.station_name == "Z7"
        assert cmd.left == pytest.approx(0.0)
        assert cmd.up == pytest.approx(3.0)
        assert cmd.down == pytest.approx(1.0)
        assert cmd.right == pytest.approx(2.0)
        assert cmd.distance_from_entrance == pytest.approx(21.8)

    def test_parse_move_command(self):
        """Test parsing M command."""
        parser = CompassPlotParser()
        line = "M   123.5   -70.2   -87.1  SZ6  P    1.5    1.0    0.5    0.5  I    0.0"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, DrawSurveyCommand)
        assert cmd.operation == DrawOperation.MOVE_TO

    def test_parse_begin_survey(self):
        """Test parsing N command."""
        parser = CompassPlotParser()
        line = "NZ+ D 6 29 1994 CStream Passage"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, BeginSurveyCommand)
        assert cmd.survey_name == "Z+"
        assert cmd.date == date(1994, 6, 29)
        assert cmd.comment == "Stream Passage"

    def test_parse_begin_section(self):
        """Test parsing S command."""
        parser = CompassPlotParser()
        line = "SFULFORD CAVE"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, BeginSectionCommand)
        assert cmd.section_name == "FULFORD CAVE"

    def test_parse_begin_feature(self):
        """Test parsing F command."""
        parser = CompassPlotParser()
        line = "FINSECTS"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, BeginFeatureCommand)
        assert cmd.feature_name == "INSECTS"

    def test_parse_begin_feature_with_range(self):
        """Test parsing F command with range."""
        parser = CompassPlotParser()
        line = "FWATER R 5.51234E2  8.12341E2"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, BeginFeatureCommand)
        assert cmd.feature_name == "WATER"
        assert cmd.min_value == Decimal("5.51234E2")
        assert cmd.max_value == Decimal("8.12341E2")

    def test_parse_feature_command(self):
        """Test parsing L command."""
        parser = CompassPlotParser()
        line = "L     0.0     0.0     0.0  SA1 P -9.0 -9.0 -9.0 -9.0"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, FeatureCommand)
        assert cmd.location.northing == pytest.approx(0.0)
        assert cmd.station_name == "A1"
        # Negative values indicate missing data
        assert cmd.left is None
        assert cmd.right is None

    def test_parse_feature_command_with_value(self):
        """Test parsing L command with value."""
        parser = CompassPlotParser()
        line = "L     0.0     0.0     0.0  SA1 P -9.0 -9.0 -9.0 -9.0 V 5.51234E2"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, FeatureCommand)
        assert cmd.value == Decimal("5.51234E2")

    def test_parse_survey_bounds(self):
        """Test parsing X command."""
        parser = CompassPlotParser()
        line = "X     118.78    138.22    -82.94    -63.34   -101.90    -82.53"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, SurveyBoundsCommand)
        assert cmd.bounds.lower.northing == pytest.approx(118.78)
        assert cmd.bounds.upper.northing == pytest.approx(138.22)

    def test_parse_cave_bounds(self):
        """Test parsing Z command."""
        parser = CompassPlotParser()
        line = "Z    -129.26    319.44    -94.30    439.00   -130.05    126.30  I 1357.3"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, CaveBoundsCommand)
        assert cmd.bounds.lower.northing == pytest.approx(-129.26)
        assert cmd.bounds.upper.northing == pytest.approx(319.44)
        assert cmd.distance_to_farthest_station == pytest.approx(1357.3)

    def test_parse_datum(self):
        """Test parsing O command."""
        parser = CompassPlotParser()
        line = "OAdindan"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, DatumCommand)
        assert cmd.datum == Datum.ADINDAN
        assert isinstance(cmd.datum, Datum)

    def test_parse_utm_zone(self):
        """Test parsing G command."""
        parser = CompassPlotParser()
        line = "G13"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, UtmZoneCommand)
        assert cmd.utm_zone == "13"

    def test_parse_file(self, artifacts_dir: Path):
        """Test parsing a complete PLT file."""
        parser = CompassPlotParser()
        commands = parser.parse_file(artifacts_dir / "simple.plt")

        assert len(commands) > 0
        assert len(parser.errors) == 0

        # Check for expected command types
        assert any(isinstance(c, CaveBoundsCommand) for c in commands)
        assert any(isinstance(c, BeginSectionCommand) for c in commands)
        assert any(isinstance(c, BeginSurveyCommand) for c in commands)
        assert any(isinstance(c, DrawSurveyCommand) for c in commands)
        assert any(isinstance(c, SurveyBoundsCommand) for c in commands)
        assert any(isinstance(c, BeginFeatureCommand) for c in commands)
        assert any(isinstance(c, FeatureCommand) for c in commands)

    def test_parse_blank_lines(self):
        """Test that blank lines are skipped."""
        parser = CompassPlotParser()
        data = """Z    -129.26    319.44    -94.30    439.00   -130.05    126.30  I 1357.3

SFULFORD CAVE

NZ+ D 6 29 1994
"""
        commands = parser.parse_string(data)

        assert len(commands) == 3
        assert len(parser.errors) == 0

    def test_parse_invalid_lrud_generates_error(self):
        """Test that invalid LRUD values generate errors."""
        parser = CompassPlotParser()
        line = "D   128.2   -65.9   -86.8  SZ7  P    abc    3.0    1.0    2.0  I   21.8"
        cmd = parser._parse_command(line, 0)

        assert cmd is not None
        assert len(parser.errors) >= 1
        assert any(Severity.ERROR == e.severity for e in parser.errors)

    def test_parse_negative_distance_generates_warning(self):
        """Test that negative distance from entrance generates warning."""
        parser = CompassPlotParser()
        line = "D   128.2   -65.9   -86.8  SZ7  P    0.0    3.0    1.0    2.0  I   -21.8"
        cmd = parser._parse_command(line, 0)

        assert cmd is not None
        # Should have a warning about negative distance
        assert any(
            Severity.WARNING == e.severity and "negative" in e.message.lower()
            for e in parser.errors
        )

    def test_null_lrud_values(self):
        """Test that 999 and 999.9 are treated as null LRUD values."""
        parser = CompassPlotParser()
        line = "D   128.2   -65.9   -86.8  SZ7  P    999    999.9    0.0    0.0  I   21.8"
        cmd = parser._parse_command(line, 0)

        assert isinstance(cmd, DrawSurveyCommand)
        assert cmd.left is None  # 999 is null
        assert cmd.up is None  # 999.9 is null
        assert cmd.down == pytest.approx(0.0)
        assert cmd.right == pytest.approx(0.0)

    def test_lrud_order_draw_vs_feature(self):
        """Test that LRUD order differs between draw and feature commands.

        Draw commands: left, up, down, right
        Feature commands: left, right, up, down
        """
        parser = CompassPlotParser()

        # Draw command: P <left> <up> <down> <right>
        draw_line = "D   0   0   0  SA1  P    1.0    2.0    3.0    4.0  I   0"
        draw_cmd = parser._parse_command(draw_line, 0)

        assert isinstance(draw_cmd, DrawSurveyCommand)
        assert draw_cmd.left == pytest.approx(1.0)
        assert draw_cmd.up == pytest.approx(2.0)
        assert draw_cmd.down == pytest.approx(3.0)
        assert draw_cmd.right == pytest.approx(4.0)

        # Feature command: P <left> <right> <up> <down>
        feature_line = "L   0   0   0  SA1  P    1.0    2.0    3.0    4.0"
        parser2 = CompassPlotParser()
        feature_cmd = parser2._parse_command(feature_line, 0)

        assert isinstance(feature_cmd, FeatureCommand)
        assert feature_cmd.left == pytest.approx(1.0)
        assert feature_cmd.right == pytest.approx(2.0)
        assert feature_cmd.up == pytest.approx(3.0)
        assert feature_cmd.down == pytest.approx(4.0)

    def test_unknown_command_ignored(self):
        """Test that unknown commands are silently ignored."""
        parser = CompassPlotParser()
        cmd = parser._parse_command("UNKNOWN COMMAND", 0)

        assert cmd is None
        assert len(parser.errors) == 0
