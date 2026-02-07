# -*- coding: utf-8 -*-
"""Tests for validation module."""

import math

import pytest

from compass_lib.survey.models import CompassShot
from compass_lib.survey.parser import CompassSurveyParser
from compass_lib.validation import days_in_month
from compass_lib.validation import depth_gauge_to_inclination
from compass_lib.validation import inclination_to_depth_gauge
from compass_lib.validation import is_valid_station_name
from compass_lib.validation import validate_depth_gauge
from compass_lib.validation import validate_station_name


class TestIsValidStationName:
    """Tests for is_valid_station_name function."""

    def test_valid_names(self):
        """Test valid station names."""
        assert is_valid_station_name("A1")
        assert is_valid_station_name("A")
        assert is_valid_station_name("STATION1234")  # 12 chars
        assert is_valid_station_name("A-1")
        assert is_valid_station_name("A_1")
        assert is_valid_station_name("A.1")
        assert is_valid_station_name("!@#$%")

    def test_valid_long_names(self):
        """Test that long station names are valid (modern Compass files)."""
        # Modern Compass files often have station names > 12 chars
        assert is_valid_station_name("STATION123456")  # 13 chars
        assert is_valid_station_name("cavern_40_foot")  # 14 chars
        assert is_valid_station_name("SecondTee.Part22")  # 16 chars
        assert is_valid_station_name("PI_MP19PWCH01")  # 13 chars
        assert is_valid_station_name("VeryLongStationNameHere")  # 23 chars

    def test_invalid_empty(self):
        """Test that empty string is invalid."""
        assert not is_valid_station_name("")

    def test_invalid_space(self):
        """Test that names with spaces are invalid."""
        assert not is_valid_station_name("A 1")
        assert not is_valid_station_name(" A1")
        assert not is_valid_station_name("A1 ")

    def test_invalid_control_chars(self):
        """Test that control characters are invalid."""
        assert not is_valid_station_name("A\x00B")
        assert not is_valid_station_name("A\tB")
        assert not is_valid_station_name("A\nB")

    def test_invalid_high_chars(self):
        """Test that non-ASCII chars are invalid."""
        assert not is_valid_station_name("Ä1")
        assert not is_valid_station_name("A\x80B")


class TestValidateStationName:
    """Tests for validate_station_name function."""

    def test_valid_name_no_exception(self):
        """Test that valid names don't raise."""
        validate_station_name("A1")
        validate_station_name("STATION1234")
        validate_station_name("STATION123456")  # 13 chars - now valid
        validate_station_name("VeryLongStationNameHere")  # Long names are valid

    def test_invalid_name_raises(self):
        """Test that invalid names raise ValueError."""
        with pytest.raises(ValueError, match="Invalid station name"):
            validate_station_name("")

        with pytest.raises(ValueError, match="Invalid station name"):
            validate_station_name("A B")  # Space is invalid

    def test_error_message_escapes_control_chars(self):
        """Test that control chars are escaped in error message."""
        with pytest.raises(ValueError, match=r"\\x00"):
            validate_station_name("A\x00B")


class TestDaysInMonth:
    """Tests for days_in_month function."""

    def test_january(self):
        """Test January has 31 days."""
        assert days_in_month(1, 2024) == 31

    def test_february_normal(self):
        """Test February has 28 days in normal years."""
        assert days_in_month(2, 2023) == 28
        assert days_in_month(2, 2100) == 28  # Divisible by 100, not 400

    def test_february_leap_year(self):
        """Test February has 29 days in leap years."""
        assert days_in_month(2, 2024) == 29  # Divisible by 4
        assert days_in_month(2, 2000) == 29  # Divisible by 400

    def test_april(self):
        """Test April has 30 days."""
        assert days_in_month(4, 2024) == 30

    def test_june(self):
        """Test June has 30 days."""
        assert days_in_month(6, 2024) == 30

    def test_september(self):
        """Test September has 30 days."""
        assert days_in_month(9, 2024) == 30

    def test_november(self):
        """Test November has 30 days."""
        assert days_in_month(11, 2024) == 30

    def test_december(self):
        """Test December has 31 days."""
        assert days_in_month(12, 2024) == 31


class TestDepthGaugeToInclination:
    """Tests for depth_gauge_to_inclination function.

    Depth Gauge Mode (Water Depth - "W"):
    In underwater cave surveying, divers use depth gauges instead of inclinometers.
    The depth gauge value represents the difference between From and To station depths:
        depth_delta = From_depth - To_depth

    Sign convention:
        - Negative depth_delta = going DEEPER (descending)
        - Positive depth_delta = going SHALLOWER (ascending)

    Conversion formula:
        inclination = arcsin(depth_delta / shot_length) * (180 / π)
    """

    def test_level_shot(self):
        """Test that zero depth delta gives zero inclination."""
        result = depth_gauge_to_inclination(0.0, 10.0)
        assert result == pytest.approx(0.0)

    def test_descending_30_degrees(self):
        """Test descending shot (going deeper)."""
        # sin(30°) = 0.5, so depth_delta = -5 for length = 10
        result = depth_gauge_to_inclination(-5.0, 10.0)
        assert result == pytest.approx(-30.0, abs=0.01)

    def test_ascending_30_degrees(self):
        """Test ascending shot (going shallower)."""
        # sin(30°) = 0.5, so depth_delta = 5 for length = 10
        result = depth_gauge_to_inclination(5.0, 10.0)
        assert result == pytest.approx(30.0, abs=0.01)

    def test_vertical_down(self):
        """Test perfectly vertical descending shot."""
        # sin(-90°) = -1, so depth_delta = -shot_length
        result = depth_gauge_to_inclination(-10.0, 10.0)
        assert result == pytest.approx(-90.0, abs=0.01)

    def test_vertical_up(self):
        """Test perfectly vertical ascending shot."""
        # sin(90°) = 1, so depth_delta = shot_length
        result = depth_gauge_to_inclination(10.0, 10.0)
        assert result == pytest.approx(90.0, abs=0.01)

    def test_45_degree_descent(self):
        """Test 45-degree descending shot."""
        # sin(45°) ≈ 0.707
        depth_delta = -10.0 * math.sin(math.radians(45))
        result = depth_gauge_to_inclination(depth_delta, 10.0)
        assert result == pytest.approx(-45.0, abs=0.01)

    def test_small_angle(self):
        """Test small inclination angle."""
        # sin(5°) ≈ 0.0872
        depth_delta = -10.0 * math.sin(math.radians(5))
        result = depth_gauge_to_inclination(depth_delta, 10.0)
        assert result == pytest.approx(-5.0, abs=0.01)

    def test_depth_exceeds_length_raises(self):
        """Test that depth exceeding shot length raises error."""
        with pytest.raises(ValueError, match="cannot exceed shot length"):
            depth_gauge_to_inclination(-15.0, 10.0)

    def test_zero_shot_length_raises(self):
        """Test that zero shot length raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            depth_gauge_to_inclination(-5.0, 0.0)

    def test_negative_shot_length_raises(self):
        """Test that negative shot length raises error."""
        with pytest.raises(ValueError, match="must be positive"):
            depth_gauge_to_inclination(-5.0, -10.0)

    def test_floating_point_tolerance(self):
        """Test that small floating point errors are tolerated."""
        # Slightly over 1.0 due to floating point
        result = depth_gauge_to_inclination(10.0 + 1e-10, 10.0)
        assert result == pytest.approx(90.0, abs=0.01)


class TestInclinationToDepthGauge:
    """Tests for inclination_to_depth_gauge function.

    This is the inverse of depth_gauge_to_inclination.
    Converts inclination angle to depth delta:
        depth_delta = shot_length * sin(inclination)
    """

    def test_level_shot(self):
        """Test that zero inclination gives zero depth delta."""
        result = inclination_to_depth_gauge(0.0, 10.0)
        assert result == pytest.approx(0.0)

    def test_30_degree_descent(self):
        """Test 30-degree descending shot."""
        # sin(-30°) = -0.5
        result = inclination_to_depth_gauge(-30.0, 10.0)
        assert result == pytest.approx(-5.0, abs=0.01)

    def test_30_degree_ascent(self):
        """Test 30-degree ascending shot."""
        # sin(30°) = 0.5
        result = inclination_to_depth_gauge(30.0, 10.0)
        assert result == pytest.approx(5.0, abs=0.01)

    def test_vertical_down(self):
        """Test perfectly vertical descending shot."""
        result = inclination_to_depth_gauge(-90.0, 10.0)
        assert result == pytest.approx(-10.0, abs=0.01)

    def test_vertical_up(self):
        """Test perfectly vertical ascending shot."""
        result = inclination_to_depth_gauge(90.0, 10.0)
        assert result == pytest.approx(10.0, abs=0.01)

    def test_roundtrip(self):
        """Test roundtrip conversion: depth -> inclination -> depth."""
        original_depth = -7.5
        shot_length = 15.0

        inclination = depth_gauge_to_inclination(original_depth, shot_length)
        recovered_depth = inclination_to_depth_gauge(inclination, shot_length)

        assert recovered_depth == pytest.approx(original_depth, abs=0.001)

    def test_roundtrip_various_angles(self):
        """Test roundtrip for various angles."""
        shot_length = 20.0
        for angle in [-85.0, -45.0, -10.0, 0.0, 10.0, 45.0, 85.0]:
            depth = inclination_to_depth_gauge(angle, shot_length)
            recovered = depth_gauge_to_inclination(depth, shot_length)
            assert recovered == pytest.approx(angle, abs=0.001)


class TestValidateDepthGauge:
    """Tests for validate_depth_gauge function."""

    def test_valid_depth(self):
        """Test valid depth gauge value."""
        is_valid, error = validate_depth_gauge(-5.0, 10.0)
        assert is_valid is True
        assert error is None

    def test_valid_at_limit(self):
        """Test depth gauge at limit (equals shot length)."""
        is_valid, error = validate_depth_gauge(-10.0, 10.0)
        assert is_valid is True
        assert error is None

    def test_invalid_exceeds_length(self):
        """Test depth gauge exceeding shot length."""
        is_valid, error = validate_depth_gauge(-15.0, 10.0)
        assert is_valid is False
        assert "exceeds shot length" in error

    def test_invalid_zero_length(self):
        """Test depth gauge with zero shot length."""
        is_valid, error = validate_depth_gauge(-5.0, 0.0)
        assert is_valid is False
        assert "must be positive" in error

    def test_invalid_negative_length(self):
        """Test depth gauge with negative shot length."""
        is_valid, error = validate_depth_gauge(-5.0, -10.0)
        assert is_valid is False
        assert "must be positive" in error

    def test_positive_depth_valid(self):
        """Test positive depth delta (ascending)."""
        is_valid, _ = validate_depth_gauge(5.0, 10.0)
        assert is_valid is True


class TestDepthGaugeParsing:
    """Integration tests for depth gauge parsing.

    The FORMAT string (including depth gauge mode "W") is purely display
    metadata for the Compass editor. The parser does NOT perform depth
    gauge conversion -- all inclination values in a .DAT file are already
    in degrees. The FORMAT string is stored as a raw string.
    """

    def test_parse_depth_gauge_format(self):
        """Test parsing a header with depth gauge FORMAT string.

        The FORMAT string is stored verbatim. The parser no longer
        extracts inclination_unit as a separate field.
        """
        parser = CompassSurveyParser()
        header_text = """UNDERWATER CAVE
SURVEY NAME: SUMP1
SURVEY DATE: 7 10 2020
DECLINATION: 0.00  FORMAT: DDDWLRUDLADNF"""

        header_dict = parser._parse_survey_header_to_dict(header_text)  # noqa: SLF001

        assert header_dict["format_string"] == "DDDWLRUDLADNF"
        assert header_dict["has_backsights"] is False

    def test_parse_shot_inclination_always_degrees(self):
        """Test that inclination is always parsed as degrees, never converted.

        Even when the FORMAT string indicates depth gauge mode, the .DAT
        file stores data in Compass's internal units (feet, degrees).
        The parser reads inclination values as-is.
        """
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        # Inclination of -5.0 degrees is stored as-is (no depth gauge conversion)
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A1 A2 10.0 45.0 -5.0 1.0 2.0 3.0 4.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot.length == pytest.approx(10.0)
        assert shot.frontsight_inclination == pytest.approx(-5.0)

    def test_parse_shot_vertical_inclination(self):
        """Test parsing a vertical shot inclination (no conversion)."""
        parser = CompassSurveyParser()
        header = {"has_backsights": False}

        # Inclination of -10.0 degrees is stored as-is
        shot_dict = parser._parse_shot_to_dict(  # noqa: SLF001
            "A1 A2 10.0 0.0 -10.0 1.0 2.0 3.0 4.0",
            header,
        )
        shot = CompassShot.model_validate(shot_dict)

        assert shot.frontsight_inclination == pytest.approx(-10.0)
