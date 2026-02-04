# -*- coding: utf-8 -*-
"""Comprehensive tests for southern hemisphere support.

This test module verifies end-to-end southern hemisphere functionality:
1. Parsing MAK files with negative zones
2. Formatting MAK files with negative zones
3. Coordinate conversion in southern hemisphere
4. Roundtrip parsing and formatting
"""

from pathlib import Path

import pytest

from compass_scratchpad.enums import Datum
from compass_scratchpad.models import UTMLocation
from compass_scratchpad.project.format import format_directive
from compass_scratchpad.project.format import format_project
from compass_scratchpad.project.models import CompassMakFile
from compass_scratchpad.project.models import DatumDirective
from compass_scratchpad.project.models import FileDirective
from compass_scratchpad.project.models import FlagsDirective
from compass_scratchpad.project.models import LocationDirective
from compass_scratchpad.project.models import UTMZoneDirective
from compass_scratchpad.project.parser import CompassProjectParser


class TestSouthernHemisphereMAKFiles:
    """Test parsing and formatting MAK files with negative zones."""

    @pytest.fixture
    def southern_mak_content(self):
        """Sample MAK file for southern hemisphere (Sydney, Australia area)."""
        return """@334000.000,6252000.000,50.000,-56,-1.234;
&WGS 1984;
!gIvotscxpl;

/
$-56;
&WGS 1984;
*0.00;
#TestCave.DAT;
"""

    def test_parse_southern_hemisphere_mak(self, southern_mak_content):
        """Test parsing a MAK file with negative zone (southern hemisphere)."""
        parser = CompassProjectParser()
        parsed = parser.parse_string_to_dict(southern_mak_content)
        mak_file = CompassMakFile.model_validate(parsed)
        
        # Check location directive
        location = mak_file.location
        assert location is not None
        assert location.utm_zone == -56
        assert location.easting == 334000.0
        assert location.northing == 6252000.0
        
        # Check UTM zone directive
        assert mak_file.utm_zone == -56
        
        # Verify hemisphere is southern
        assert location.utm_zone < 0, "Negative zone indicates southern hemisphere"

    def test_format_southern_hemisphere_mak(self):
        """Test formatting a MAK file with negative zone."""
        directives = [
            LocationDirective(
                easting=334000.0,
                northing=6252000.0,
                elevation=50.0,
                utm_zone=-56,
                utm_convergence=-1.234,
            ),
            DatumDirective(datum=Datum.WGS_1984),
            FlagsDirective(raw_flags="gIvotscxpl"),
            UTMZoneDirective(utm_zone=-56),
            FileDirective(file="TestCave.DAT"),
        ]
        
        mak_file = CompassMakFile(directives=directives)
        formatted = format_project(mak_file)
        
        # Verify negative zone is formatted correctly
        assert "@334000.000,6252000.000,50.000,-56,-1.234;" in formatted
        assert "$-56;" in formatted

    def test_roundtrip_southern_hemisphere_mak(self, southern_mak_content):
        """Test roundtrip parsing and formatting preserves negative zone."""
        # Parse
        parser = CompassProjectParser()
        parsed = parser.parse_string_to_dict(southern_mak_content)
        mak_file = CompassMakFile.model_validate(parsed)
        
        # Format
        formatted = format_project(mak_file)
        
        # Parse again
        parsed2 = parser.parse_string_to_dict(formatted)
        mak_file2 = CompassMakFile.model_validate(parsed2)
        
        # Verify zone is preserved
        assert mak_file2.utm_zone == -56
        assert mak_file2.location.utm_zone == -56

    @pytest.mark.parametrize("zone", [
        -1, -10, -20, -30, -40, -50, -60,  # Southern hemisphere
        1, 10, 20, 30, 40, 50, 60,  # Northern hemisphere
    ])
    def test_parse_and_format_all_zones(self, zone):
        """Test parsing and formatting all valid zone numbers (both hemispheres)."""
        mak_content = f"${ zone};"
        
        # Parse
        parser = CompassProjectParser()
        parsed = parser.parse_string_to_dict(mak_content)
        mak_file = CompassMakFile.model_validate(parsed)
        
        # Verify
        assert mak_file.utm_zone == zone
        
        # Format
        formatted = format_project(mak_file)
        assert f"${zone};" in formatted


class TestSouthernHemisphereCoordinates:
    """Test coordinate conversions in southern hemisphere."""

    def test_sydney_coordinates(self):
        """Test real Sydney, Australia coordinates."""
        # Sydney Opera House approximate UTM coordinates (Zone 56S)
        loc = UTMLocation(
            easting=334000.0,
            northing=6252000.0,
            elevation=5.0,
            zone=-56,
            datum=Datum.WGS_1984,
        )
        
        lat, lon = loc.to_latlon()
        
        # Sydney Opera House: -33.8568°S, 151.2153°E
        assert -34.0 < lat < -33.5
        assert 150.5 < lon < 152.0
        assert lat < 0  # Southern hemisphere

    def test_melbourne_coordinates(self):
        """Test Melbourne, Australia coordinates."""
        # Melbourne area (Zone 55S)
        loc = UTMLocation(
            easting=320000.0,
            northing=5813000.0,
            elevation=10.0,
            zone=-55,
            datum=Datum.WGS_1984,
        )
        
        lat, lon = loc.to_latlon()
        
        # Melbourne: -37.8°S, 144.9°E
        assert -38.5 < lat < -37.0
        assert 144.0 < lon < 146.0
        assert lat < 0

    def test_santiago_chile_coordinates(self):
        """Test Santiago, Chile coordinates."""
        # Santiago area (Zone 19S)
        loc = UTMLocation(
            easting=350000.0,
            northing=6300000.0,
            elevation=570.0,
            zone=-19,
            datum=Datum.WGS_1984,
        )
        
        lat, lon = loc.to_latlon()
        
        # Santiago: -33.4°S, -70.6°W
        assert -34.0 < lat < -32.0
        assert -71.5 < lon < -69.5
        assert lat < 0
        assert lon < 0  # Western hemisphere

    def test_cape_town_coordinates(self):
        """Test Cape Town, South Africa coordinates."""
        # Cape Town area (Zone 34S)
        loc = UTMLocation(
            easting=261000.0,
            northing=6243000.0,
            elevation=20.0,
            zone=-34,
            datum=Datum.WGS_1984,
        )
        
        lat, lon = loc.to_latlon()
        
        # Cape Town: -33.9°S, 18.4°E
        assert -34.5 < lat < -33.0
        assert 17.5 < lon < 19.5
        assert lat < 0

    def test_hemisphere_detection_from_zone(self):
        """Test that hemisphere is correctly detected from zone sign."""
        # Northern hemisphere
        loc_north = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=1000.0,
            zone=16,
        )
        assert loc_north.is_northern_hemisphere is True
        assert loc_north.zone_number == 16
        
        # Southern hemisphere
        loc_south = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=1000.0,
            zone=-16,
        )
        assert loc_south.is_northern_hemisphere is False
        assert loc_south.zone_number == 16

    def test_negative_zone_preserves_zone_number(self):
        """Test that zone_number property returns absolute value."""
        for zone in range(1, 61):
            loc_north = UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=zone,
            )
            assert loc_north.zone_number == zone
            assert loc_north.is_northern_hemisphere is True
            
            loc_south = UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=-zone,
            )
            assert loc_south.zone_number == zone
            assert loc_south.is_northern_hemisphere is False


class TestSouthernHemisphereValidation:
    """Test validation for southern hemisphere zones."""

    def test_zone_zero_not_allowed_in_utm_location(self):
        """Test that zone 0 is not allowed in UTMLocation."""
        with pytest.raises(ValueError, match="cannot be 0"):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=0,
            )

    def test_zone_beyond_60_not_allowed(self):
        """Test that zone > 60 is not allowed."""
        with pytest.raises(ValueError):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=61,
            )

    def test_zone_below_minus_60_not_allowed(self):
        """Test that zone < -60 is not allowed."""
        with pytest.raises(ValueError):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=-61,
            )

    def test_all_negative_zones_allowed(self):
        """Test that all negative zones -1 to -60 are allowed."""
        for zone in range(-60, 0):
            loc = UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=zone,
            )
            assert loc.zone == zone
            assert loc.is_northern_hemisphere is False
            assert loc.zone_number == abs(zone)
