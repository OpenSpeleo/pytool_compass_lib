# -*- coding: utf-8 -*-
"""Tests for enums module."""

import pytest

from compass_scratchpad.enums import AzimuthUnit
from compass_scratchpad.enums import DrawOperation
from compass_scratchpad.enums import InclinationUnit
from compass_scratchpad.enums import LengthUnit
from compass_scratchpad.enums import LrudAssociation
from compass_scratchpad.enums import LrudItem
from compass_scratchpad.enums import Severity
from compass_scratchpad.enums import ShotItem


class TestAzimuthUnit:
    """Tests for AzimuthUnit enum."""

    def test_values(self):
        """Test enum values."""
        assert AzimuthUnit.DEGREES.value == "D"
        assert AzimuthUnit.QUADS.value == "Q"
        assert AzimuthUnit.GRADS.value == "R"

    def test_convert_to_grads(self):
        """Test conversion to grads."""
        # 180 degrees = 200 grads
        result = AzimuthUnit.convert(180.0, AzimuthUnit.GRADS)
        assert result == pytest.approx(200.0)

        # 90 degrees = 100 grads
        result = AzimuthUnit.convert(90.0, AzimuthUnit.GRADS)
        assert result == pytest.approx(100.0)

    def test_convert_to_degrees(self):
        """Test conversion to degrees (no change)."""
        result = AzimuthUnit.convert(180.0, AzimuthUnit.DEGREES)
        assert result == 180.0

    def test_convert_to_quads(self):
        """Test conversion to quads (no change in value)."""
        result = AzimuthUnit.convert(45.0, AzimuthUnit.QUADS)
        assert result == 45.0

    def test_convert_none(self):
        """Test conversion of None returns None."""
        assert AzimuthUnit.convert(None, AzimuthUnit.GRADS) is None


class TestInclinationUnit:
    """Tests for InclinationUnit enum."""

    def test_values(self):
        """Test enum values."""
        assert InclinationUnit.DEGREES.value == "D"
        assert InclinationUnit.PERCENT_GRADE.value == "G"
        assert InclinationUnit.DEGREES_AND_MINUTES.value == "M"
        assert InclinationUnit.GRADS.value == "R"
        assert InclinationUnit.DEPTH_GAUGE.value == "W"

    def test_convert_to_percent_grade(self):
        """Test conversion to percent grade."""
        # 45 degrees = 100% grade (tan(45) = 1)
        result = InclinationUnit.convert(45.0, InclinationUnit.PERCENT_GRADE)
        assert result == pytest.approx(100.0, rel=1e-10)

    def test_convert_to_grads(self):
        """Test conversion to grads."""
        # 180 degrees = 200 grads
        result = InclinationUnit.convert(180.0, InclinationUnit.GRADS)
        assert result == pytest.approx(200.0)

    def test_convert_to_degrees(self):
        """Test conversion to degrees (no change)."""
        result = InclinationUnit.convert(45.0, InclinationUnit.DEGREES)
        assert result == 45.0

    def test_convert_none(self):
        """Test conversion of None returns None."""
        assert InclinationUnit.convert(None, InclinationUnit.PERCENT_GRADE) is None


class TestLengthUnit:
    """Tests for LengthUnit enum."""

    def test_values(self):
        """Test enum values."""
        assert LengthUnit.DECIMAL_FEET.value == "D"
        assert LengthUnit.FEET_AND_INCHES.value == "I"
        assert LengthUnit.METERS.value == "M"

    def test_convert_to_meters(self):
        """Test conversion to meters."""
        # 1 foot = 0.3048 meters
        result = LengthUnit.convert(1.0, LengthUnit.METERS)
        assert result == pytest.approx(0.3048)

        # 10 feet = 3.048 meters
        result = LengthUnit.convert(10.0, LengthUnit.METERS)
        assert result == pytest.approx(3.048)

    def test_convert_to_feet(self):
        """Test conversion to decimal feet (no change)."""
        result = LengthUnit.convert(10.0, LengthUnit.DECIMAL_FEET)
        assert result == 10.0

    def test_convert_none(self):
        """Test conversion of None returns None."""
        assert LengthUnit.convert(None, LengthUnit.METERS) is None


class TestLrudAssociation:
    """Tests for LrudAssociation enum."""

    def test_values(self):
        """Test enum values."""
        assert LrudAssociation.FROM.value == "F"
        assert LrudAssociation.TO.value == "T"


class TestLrudItem:
    """Tests for LrudItem enum."""

    def test_values(self):
        """Test enum values."""
        assert LrudItem.LEFT.value == "L"
        assert LrudItem.RIGHT.value == "R"
        assert LrudItem.UP.value == "U"
        assert LrudItem.DOWN.value == "D"


class TestShotItem:
    """Tests for ShotItem enum."""

    def test_values(self):
        """Test enum values."""
        assert ShotItem.LENGTH.value == "L"
        assert ShotItem.FRONTSIGHT_AZIMUTH.value == "A"
        assert ShotItem.FRONTSIGHT_INCLINATION.value == "D"
        assert ShotItem.BACKSIGHT_AZIMUTH.value == "a"
        assert ShotItem.BACKSIGHT_INCLINATION.value == "d"


class TestSeverity:
    """Tests for Severity enum."""

    def test_values(self):
        """Test enum values."""
        assert Severity.ERROR.value == "error"
        assert Severity.WARNING.value == "warning"


class TestDrawOperation:
    """Tests for DrawOperation enum."""

    def test_values(self):
        """Test enum values."""
        assert DrawOperation.MOVE_TO.value == "M"
        assert DrawOperation.LINE_TO.value == "D"
