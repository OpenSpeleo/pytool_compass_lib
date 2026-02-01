# -*- coding: utf-8 -*-
"""Tests for core models module."""

import pytest

from compass_scratchpad.models import Bounds
from compass_scratchpad.models import Location
from compass_scratchpad.models import NEVLocation


class TestNEVLocation:
    """Tests for NEVLocation model."""

    def test_creation(self):
        """Test creating a NEV location."""
        loc = NEVLocation(
            easting=100.5,
            northing=200.5,
            elevation=300.5,
            unit="f",
        )
        assert loc.easting == 100.5
        assert loc.northing == 200.5
        assert loc.elevation == 300.5
        assert loc.unit == "f"

    def test_default_unit(self):
        """Test default unit is feet."""
        loc = NEVLocation(
            easting=100.0,
            northing=200.0,
            elevation=300.0,
        )
        assert loc.unit == "f"

    def test_meters_unit(self):
        """Test meters unit."""
        loc = NEVLocation(
            easting=100.0,
            northing=200.0,
            elevation=300.0,
            unit="m",
        )
        assert loc.unit == "m"

    def test_invalid_unit(self):
        """Test that invalid unit raises ValueError."""
        with pytest.raises(ValueError):
            NEVLocation(
                easting=100.0,
                northing=200.0,
                elevation=300.0,
                unit="x",
            )

    def test_str(self):
        """Test string representation."""
        loc = NEVLocation(
            easting=100.0,
            northing=200.0,
            elevation=300.0,
            unit="f",
        )
        result = str(loc)
        assert "easting=100.0" in result
        assert "northing=200.0" in result
        assert "elevation=300.0" in result


class TestLocation:
    """Tests for Location model."""

    def test_creation(self):
        """Test creating a location."""
        loc = Location(
            northing=100.0,
            easting=200.0,
            vertical=300.0,
        )
        assert loc.northing == 100.0
        assert loc.easting == 200.0
        assert loc.vertical == 300.0

    def test_default_values(self):
        """Test default values are None."""
        loc = Location()
        assert loc.northing is None
        assert loc.easting is None
        assert loc.vertical is None

    def test_partial_values(self):
        """Test partial values."""
        loc = Location(northing=100.0)
        assert loc.northing == 100.0
        assert loc.easting is None
        assert loc.vertical is None

    def test_str(self):
        """Test string representation."""
        loc = Location(
            northing=100.0,
            easting=200.0,
            vertical=300.0,
        )
        result = str(loc)
        assert "northing=100.0" in result
        assert "easting=200.0" in result
        assert "vertical=300.0" in result


class TestBounds:
    """Tests for Bounds model."""

    def test_creation(self):
        """Test creating bounds."""
        bounds = Bounds()
        assert bounds.lower is not None
        assert bounds.upper is not None

    def test_creation_with_values(self):
        """Test creating bounds with values."""
        lower = Location(northing=100.0, easting=200.0, vertical=300.0)
        upper = Location(northing=400.0, easting=500.0, vertical=600.0)
        bounds = Bounds(lower=lower, upper=upper)

        assert bounds.lower.northing == 100.0
        assert bounds.upper.northing == 400.0

    def test_default_locations(self):
        """Test that default locations have None values."""
        bounds = Bounds()
        assert bounds.lower.northing is None
        assert bounds.upper.northing is None
