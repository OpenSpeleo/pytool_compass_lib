# -*- coding: utf-8 -*-
"""Tests for survey module."""

from datetime import date
from pathlib import Path

import pytest

from compass_lib.enums import Severity
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader
from compass_lib.survey.parser import CompassSurveyParser


class TestCompassShot:
    """Tests for CompassShot model."""

    def test_basic_creation(self):
        """Test creating a basic shot."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.5,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
        )
        assert shot.from_station_name == "A1"
        assert shot.to_station_name == "A2"
        assert shot.length == 10.5
        assert shot.frontsight_azimuth == 45.0
        assert shot.frontsight_inclination == -5.0

    def test_optional_fields(self):
        """Test that optional fields default to None or False."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
        )
        assert shot.length is None
        assert shot.frontsight_azimuth is None
        assert shot.backsight_azimuth is None
        assert shot.left is None
        assert shot.comment is None
        assert shot.excluded_from_length is False

    def test_length_accepts_negative(self):
        """Test that negative length is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=-5.0,
        )
        assert shot.length == -5.0

    def test_azimuth_accepts_negative(self):
        """Test that negative azimuth is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            frontsight_azimuth=-10.0,
        )
        assert shot.frontsight_azimuth == -10.0

    def test_azimuth_accepts_large(self):
        """Test that azimuth >= 360 is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            frontsight_azimuth=360.0,
        )
        assert shot.frontsight_azimuth == 360.0

    def test_inclination_accepts_out_of_range_low(self):
        """Test that inclination < -90 is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            frontsight_inclination=-91.0,
        )
        assert shot.frontsight_inclination == -91.0

    def test_inclination_accepts_out_of_range_high(self):
        """Test that inclination > 90 is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            frontsight_inclination=91.0,
        )
        assert shot.frontsight_inclination == 91.0

    def test_lrud_accepts_negative(self):
        """Test that negative LRUD is accepted (real-world data tolerance)."""
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            left=-1.0,
        )
        assert shot.left == -1.0


class TestCompassSurveyHeader:
    """Tests for CompassSurveyHeader model."""

    def test_default_values(self):
        """Test default values."""
        header = CompassSurveyHeader()
        assert header.cave_name is None
        assert header.survey_name is None
        assert header.declination == 0.0
        assert header.format_string is None
        assert header.has_backsights is True

    def test_custom_values(self):
        """Test custom values."""
        header = CompassSurveyHeader(
            cave_name="Test Cave",
            survey_name="A",
            date=date(2024, 1, 15),
            declination=5.5,
            format_string="DMMMLRUDLADBF",
        )
        assert header.cave_name == "Test Cave"
        assert header.survey_name == "A"
        assert header.date == date(2024, 1, 15)
        assert header.declination == 5.5
        assert header.format_string == "DMMMLRUDLADBF"


class TestCompassSurvey:
    """Tests for CompassSurvey model."""

    def test_creation(self):
        """Test creating a survey with header and shots."""
        header = CompassSurveyHeader(cave_name="Test Cave")
        shot = CompassShot(from_station_name="A1", to_station_name="A2")
        survey = CompassSurvey(header=header, shots=[shot])

        assert survey.header.cave_name == "Test Cave"
        assert len(survey.shots) == 1


class TestCompassSurveyParser:
    """Tests for CompassSurveyParser."""

    def test_parse_basic_shot(self):
        """Test parsing a basic shot line."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot is not None
        assert shot.from_station_name == "A3"
        assert shot.to_station_name == "A4"
        assert shot.length == pytest.approx(4.25)
        assert shot.frontsight_azimuth == pytest.approx(15.0)
        assert shot.frontsight_inclination == pytest.approx(-85.0)
        assert shot.left == pytest.approx(5.0)
        assert shot.up == pytest.approx(3.5)
        assert shot.down == pytest.approx(0.75)
        assert shot.right == pytest.approx(0.5)

    def test_parse_shot_with_backsights(self):
        """Test parsing a shot with backsights."""
        parser = CompassSurveyParser()
        header = {"has_backsights": True}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 195.0 85.00",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot is not None
        assert shot.backsight_azimuth == pytest.approx(195.0)
        assert shot.backsight_inclination == pytest.approx(85.0)

    def test_parse_shot_with_flags(self):
        """Test parsing shots with various flags."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        # Test L flag
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|L#",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.excluded_from_length is True
        assert shot.excluded_from_plotting is False

        # Test P flag
        parser = CompassSurveyParser()
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|P#",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.excluded_from_plotting is True

        # Test X flag
        parser = CompassSurveyParser()
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|X#",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.excluded_from_all_processing is True

        # Test C flag
        parser = CompassSurveyParser()
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|C#",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.do_not_adjust is True

        # Test combined flags
        parser = CompassSurveyParser()
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|LCP#",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.excluded_from_length is True
        assert shot.excluded_from_plotting is True
        assert shot.do_not_adjust is True

    def test_parse_shot_with_comment(self):
        """Test parsing shot with comment."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 Big Room",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.comment == "Big Room"

    def test_parse_shot_with_flags_and_comment(self):
        """Test parsing shot with both flags and comment."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|LX# blah blah",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)
        assert shot.excluded_from_length is True
        assert shot.excluded_from_all_processing is True
        assert shot.comment == "blah blah"

    def test_parse_invalid_azimuth_generates_error(self):
        """Test that invalid azimuth generates error."""
        parser = CompassSurveyParser()
        header = {"has_backsights": True}

        _ = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 -15.00 -85.00 5.00 3.50 0.75 0.50 360.0 85.0",
            header,
        )

        # Parser generates errors for invalid azimuths
        azimuth_errors = [e for e in parser.errors if "azimuth" in e.message]
        assert len(azimuth_errors) >= 2

    def test_parse_invalid_inclination_generates_error(self):
        """Test that invalid inclination generates error."""
        parser = CompassSurveyParser()
        header = {"has_backsights": True}

        _ = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -91.00 5.00 3.50 0.75 0.50 195.0 92.0",
            header,
        )

        # Errors should be generated for out-of-range inclinations
        inclination_errors = [e for e in parser.errors if "inclination" in e.message]
        assert len(inclination_errors) >= 2

    def test_parse_negative_length_generates_error(self):
        """Test that negative length generates error."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        _ = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 -4.25 15.00 -85.00 5.00 3.50 0.75 0.50",
            header,
        )

        assert any("distance must be >= 0" in e.message for e in parser.errors)

    def test_parse_survey_header(self):
        """Test parsing survey header."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979  COMMENT:Entrance Passage
SURVEY TEAM:
D.SMITH,R.BROWN,S.MURRAY
DECLINATION: 1.00  FORMAT: DDDDLUDRADLBF  CORRECTIONS: 2.00 3.00 4.00 CORRECTIONS2: 5.0 6.0"""  # noqa: E501

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001
        header = CompassSurveyHeader.model_validate(header_dict)

        assert header.cave_name == "SECRET CAVE"
        assert header.survey_name == "A"
        assert header.date == date(1979, 7, 10)
        assert header.team == "D.SMITH,R.BROWN,S.MURRAY"
        assert header.declination == pytest.approx(1.0)
        assert header.format_string == "DDDDLUDRADLBF"
        assert header.has_backsights is True
        assert header.length_correction == pytest.approx(2.0)
        assert header.frontsight_azimuth_correction == pytest.approx(3.0)

    def test_parse_format_with_no_backsights(self):
        """Test parsing format string without backsights."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLUDRADLNT"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001
        header = CompassSurveyHeader.model_validate(header_dict)

        assert header.has_backsights is False
        assert header.format_string == "DDDDLUDRADLNT"

    def test_parse_long_shot_format(self):
        """Test parsing extended 15-character format with backsights."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLUDRADLadBF"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001
        header = CompassSurveyHeader.model_validate(header_dict)

        assert header.format_string == "DDDDLUDRADLadBF"
        assert header.has_backsights is True

    def test_parse_file(self, artifacts_dir: Path):
        """Test parsing a complete file."""
        parser = CompassSurveyParser()
        surveys = parser.parse_file(artifacts_dir / "simple.dat")

        assert len(surveys) == 1
        survey = surveys[0]
        assert survey.header.cave_name == "SECRET CAVE"
        assert survey.header.survey_name == "A"
        assert len(survey.shots) == 4
        assert survey.shots[0].from_station_name == "A2"
        assert survey.shots[0].to_station_name == "A1"

    def test_parse_multi_survey_file(self, artifacts_dir: Path):
        """Test parsing a file with multiple surveys."""
        parser = CompassSurveyParser()
        surveys = parser.parse_file(artifacts_dir / "multi_trip.dat")

        assert len(surveys) == 2
        assert surveys[0].header.survey_name == "A"
        assert surveys[1].header.survey_name == "B"
        assert len(surveys[0].shots) == 4
        assert len(surveys[1].shots) == 4

    def test_parse_date_2_digit_year(self):
        """Test parsing date with 2-digit year."""
        parser = CompassSurveyParser()
        parsed = parser._parse_date("7 10 79")  # noqa: SLF001

        assert parsed == date(1979, 7, 10)

    def test_parse_date_4_digit_year(self):
        """Test parsing date with 4-digit year."""
        parser = CompassSurveyParser()
        parsed = parser._parse_date("7 10 2024")  # noqa: SLF001

        assert parsed == date(2024, 7, 10)

    def test_unrecognized_flag_generates_warning(self):
        """Test that unrecognized flag generates warning."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        _ = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 5.00 3.50 0.75 0.50 #|Q#",
            header,
        )

        assert len(parser.errors) == 1
        assert parser.errors[0].severity == Severity.WARNING
        assert "unrecognized flag: Q" in parser.errors[0].message

    def test_missing_value_threshold(self):
        """Test that values > 990 are treated as missing."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -85.00 999.00 999.00 999.00 999.00",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot.left is None
        assert shot.up is None
        assert shot.down is None
        assert shot.right is None


class TestLrudOrderParsing:
    """Tests for LRUD order parsing in shots.

    Compass .DAT files have FIXED column positions regardless of the
    FORMAT string. Columns are always:
    FROM TO LENGTH AZIMUTH INCLINATION LEFT UP DOWN RIGHT [BS_AZ BS_INC]
    """

    def test_default_lrud_order(self):
        """Test parsing with default LRUD order (LUDR - standard Compass format)."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -5.00 1.0 2.0 3.0 4.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        # Standard Compass .DAT file order is: Left, Up, Down, Right
        # So 1.0=Left, 2.0=Up, 3.0=Down, 4.0=Right
        assert shot.left == pytest.approx(1.0)
        assert shot.up == pytest.approx(2.0)
        assert shot.down == pytest.approx(3.0)
        assert shot.right == pytest.approx(4.0)

    def test_extra_header_keys_are_ignored(self):
        """Test that extra keys in header dict are ignored during parsing.

        The parser only uses ``has_backsights`` from the header dict.
        Any other keys are silently ignored.
        """
        parser = CompassSurveyParser()
        header = {
            "has_backsights": False,
            # Extra keys should be harmlessly ignored
            "some_extra_key": "some_value",
        }

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 4.25 15.00 -5.00 1.0 2.0 3.0 4.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        # Columns are ALWAYS in fixed order: Left, Up, Down, Right
        assert shot.left == pytest.approx(1.0)
        assert shot.up == pytest.approx(2.0)
        assert shot.down == pytest.approx(3.0)
        assert shot.right == pytest.approx(4.0)


class TestShotMeasurementOrderParsing:
    """Tests for shot measurement order parsing.

    IMPORTANT: Compass .DAT files have FIXED column positions regardless
    of the FORMAT string. Columns are always:
    FROM TO LENGTH AZIMUTH INCLINATION LEFT UP DOWN RIGHT [BS_AZ BS_INC]
    """

    def test_default_shot_order_lad(self):
        """Test parsing with fixed shot order (Length, Azimuth, Inclination).

        This is always the column order in .DAT files, regardless of FORMAT.
        """
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 10.0 45.0 -5.0 1.0 2.0 3.0 4.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot.length == pytest.approx(10.0)
        assert shot.frontsight_azimuth == pytest.approx(45.0)
        assert shot.frontsight_inclination == pytest.approx(-5.0)

    def test_backsights_follow_fixed_positions(self):
        """Test that backsights are parsed from fixed positions after LRUD."""
        parser = CompassSurveyParser()
        header = {"has_backsights": True}

        # Fixed order: FROM TO LENGTH AZ INC LEFT UP DOWN RIGHT BS_AZ BS_INC
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A3 A4 10.0 45.0 -5.0 1.0 2.0 3.0 4.0 225.0 5.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot.length == pytest.approx(10.0)
        assert shot.frontsight_azimuth == pytest.approx(45.0)
        assert shot.frontsight_inclination == pytest.approx(-5.0)
        assert shot.left == pytest.approx(1.0)
        assert shot.up == pytest.approx(2.0)
        assert shot.down == pytest.approx(3.0)
        assert shot.right == pytest.approx(4.0)
        assert shot.backsight_azimuth == pytest.approx(225.0)
        assert shot.backsight_inclination == pytest.approx(5.0)


class TestFormatStringParsing:
    """Tests for FORMAT string parsing in the survey header.

    The FORMAT string is stored as a raw string. The only structural
    information extracted is ``has_backsights``, which determines
    whether backsight columns are present in the shot data.
    """

    def test_11_char_format_no_backsights(self):
        """Test that 11-character format has no backsight flag (defaults False)."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLRUDLAD"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDLRUDLAD"
        assert header_dict["has_backsights"] is False

    def test_12_char_format_with_backsights(self):
        """Test that 12-character format extracts backsight flag."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLRUDLADB"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDLRUDLADB"
        assert header_dict["has_backsights"] is True

    def test_13_char_format_with_backsights(self):
        """Test that 13-character format extracts backsight flag."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLRUDLADBF"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDLRUDLADBF"
        assert header_dict["has_backsights"] is True

    def test_13_char_format_without_backsights(self):
        """Test that 13-character format with N flag means no backsights."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLRUDLADNT"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDLRUDLADNT"
        assert header_dict["has_backsights"] is False

    def test_15_char_format_with_backsights(self):
        """Test that 15-character format extracts backsight flag at position 13."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLRUDLADadBF"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDLRUDLADadBF"
        assert header_dict["has_backsights"] is True

    def test_format_string_is_stored_verbatim(self):
        """Test that the raw FORMAT string is stored as-is."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDUDLRLADBF"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDDUDLRLADBF"
