# -*- coding: utf-8 -*-
"""Tests for survey module."""

from datetime import date
from pathlib import Path

import pytest

from compass_lib.enums import AzimuthUnit
from compass_lib.enums import LengthUnit
from compass_lib.enums import LrudAssociation
from compass_lib.enums import Severity
from compass_lib.enums import ShotItem
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassTrip
from compass_lib.survey.models import CompassTripHeader
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


class TestCompassTripHeader:
    """Tests for CompassTripHeader model."""

    def test_default_values(self):
        """Test default values."""
        header = CompassTripHeader()
        assert header.cave_name is None
        assert header.survey_name is None
        assert header.declination == 0.0
        assert header.length_unit == LengthUnit.DECIMAL_FEET
        assert header.azimuth_unit == AzimuthUnit.DEGREES
        assert header.has_backsights is True
        assert header.lrud_association == LrudAssociation.FROM

    def test_custom_values(self):
        """Test custom values."""
        header = CompassTripHeader(
            cave_name="Test Cave",
            survey_name="A",
            date=date(2024, 1, 15),
            declination=5.5,
            length_unit=LengthUnit.METERS,
        )
        assert header.cave_name == "Test Cave"
        assert header.survey_name == "A"
        assert header.date == date(2024, 1, 15)
        assert header.declination == 5.5
        assert header.length_unit == LengthUnit.METERS


class TestCompassTrip:
    """Tests for CompassTrip model."""

    def test_creation(self):
        """Test creating a trip with header and shots."""
        header = CompassTripHeader(cave_name="Test Cave")
        shot = CompassShot(from_station_name="A1", to_station_name="A2")
        trip = CompassTrip(header=header, shots=[shot])

        assert trip.header.cave_name == "Test Cave"
        assert len(trip.shots) == 1


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
        """Test that invalid azimuth generates error.

        Note: Invalid values are still passed to the model, which may reject them
        with additional validation errors.
        """
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
        """Test that invalid inclination generates error.

        Note: Invalid values are still passed to the model, which may reject them
        with additional validation errors.
        """
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

    def test_parse_trip_header(self):
        """Test parsing trip header."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979  COMMENT:Entrance Passage
SURVEY TEAM:
D.SMITH,R.BROWN,S.MURRAY
DECLINATION: 1.00  FORMAT: DDDDLUDRADLBF  CORRECTIONS: 2.00 3.00 4.00 CORRECTIONS2: 5.0 6.0"""  # noqa: E501

        header_dict = parser._parse_trip_header_to_dict(header_text)  # noqa: SLF001
        header = CompassTripHeader.model_validate(header_dict)

        assert header.cave_name == "SECRET CAVE"
        assert header.survey_name == "A"
        assert header.date == date(1979, 7, 10)
        assert header.team == "D.SMITH,R.BROWN,S.MURRAY"
        assert header.declination == pytest.approx(1.0)
        assert header.azimuth_unit == AzimuthUnit.DEGREES
        assert header.length_unit == LengthUnit.DECIMAL_FEET
        assert header.has_backsights is True
        assert header.lrud_association == LrudAssociation.FROM
        assert header.length_correction == pytest.approx(2.0)
        assert header.frontsight_azimuth_correction == pytest.approx(3.0)

    def test_parse_format_with_no_backsights(self):
        """Test parsing format string without backsights."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLUDRADLNT"""

        header_dict = parser._parse_trip_header_to_dict(header_text)  # noqa: SLF001
        header = CompassTripHeader.model_validate(header_dict)

        assert header.has_backsights is False
        assert header.lrud_association == LrudAssociation.TO

    def test_parse_long_shot_format(self):
        """Test parsing extended 5-item shot format."""
        parser = CompassSurveyParser()
        header_text = """SECRET CAVE
SURVEY NAME: A
SURVEY DATE: 7 10 1979
DECLINATION: 1.00  FORMAT: DDDDLUDRADLadBF"""

        header_dict = parser._parse_trip_header_to_dict(header_text)  # noqa: SLF001
        header = CompassTripHeader.model_validate(header_dict)

        assert len(header.shot_measurement_order) == 5
        assert ShotItem.BACKSIGHT_AZIMUTH in header.shot_measurement_order
        assert ShotItem.BACKSIGHT_INCLINATION in header.shot_measurement_order
        assert header.has_backsights is True

    def test_parse_file(self, artifacts_dir: Path):
        """Test parsing a complete file."""
        parser = CompassSurveyParser()
        trips = parser.parse_file(artifacts_dir / "simple.dat")

        assert len(trips) == 1
        trip = trips[0]
        assert trip.header.cave_name == "SECRET CAVE"
        assert trip.header.survey_name == "A"
        assert len(trip.shots) == 4
        assert trip.shots[0].from_station_name == "A2"
        assert trip.shots[0].to_station_name == "A1"

    def test_parse_multi_trip_file(self, artifacts_dir: Path):
        """Test parsing a file with multiple trips."""
        parser = CompassSurveyParser()
        trips = parser.parse_file(artifacts_dir / "multi_trip.dat")

        assert len(trips) == 2
        assert trips[0].header.survey_name == "A"
        assert trips[1].header.survey_name == "B"
        assert len(trips[0].shots) == 4
        assert len(trips[1].shots) == 4

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
