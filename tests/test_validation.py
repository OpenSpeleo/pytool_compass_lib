# -*- coding: utf-8 -*-
"""Tests for validation module."""

import pytest

from compass_scratchpad.validation import days_in_month
from compass_scratchpad.validation import is_valid_station_name
from compass_scratchpad.validation import validate_station_name


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
