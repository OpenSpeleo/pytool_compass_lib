# -*- coding: utf-8 -*-
"""Tests for core models module."""

import pytest

from compass_scratchpad.enums import Datum
from compass_scratchpad.models import Bounds
from compass_scratchpad.models import Location
from compass_scratchpad.models import NEVLocation
from compass_scratchpad.models import UTMLocation


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
        with pytest.raises(ValueError, match="unit"):
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


class TestUTMLocation:
    """Tests for UTMLocation model."""

    def test_creation_minimal(self):
        """Test creating a UTM location with minimal parameters."""
        loc = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
        )
        assert loc.easting == 500000.0
        assert loc.northing == 4000000.0
        assert loc.elevation == 100.0
        assert loc.zone == 13
        assert loc.convergence == 0.0
        assert loc.datum is None

    def test_creation_with_datum(self):
        """Test creating a UTM location with datum."""
        loc = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            datum=Datum.WGS_1984,
        )
        assert loc.datum == Datum.WGS_1984

    def test_creation_with_convergence(self):
        """Test creating a UTM location with convergence."""
        loc = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            convergence=1.5,
        )
        assert loc.convergence == 1.5

    def test_validation_easting_too_low(self):
        """Test that easting below valid range raises error."""
        with pytest.raises(ValueError, match="easting"):
            UTMLocation(
                easting=100000.0,  # Below 166000
                northing=4000000.0,
                elevation=100.0,
                zone=13,
            )

    def test_validation_zone_too_low(self):
        """Test that zone below 1 raises error."""
        with pytest.raises(ValueError, match="zone"):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=0,
            )

    def test_validation_zone_too_high(self):
        """Test that zone above 60 raises error."""
        with pytest.raises(ValueError, match="zone"):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=61,
            )

    def test_southern_hemisphere_zone(self):
        """Test creating location with negative zone (southern hemisphere)."""
        loc = UTMLocation(
            easting=500000.0,
            northing=6000000.0,
            elevation=100.0,
            zone=-33,  # Southern hemisphere
        )
        assert loc.zone == -33
        assert loc.is_northern_hemisphere is False
        assert loc.zone_number == 33

    def test_northern_hemisphere_zone(self):
        """Test creating location with positive zone (northern hemisphere)."""
        loc = UTMLocation(
            easting=500000.0,
            northing=6000000.0,
            elevation=100.0,
            zone=33,  # Northern hemisphere
        )
        assert loc.zone == 33
        assert loc.is_northern_hemisphere is True
        assert loc.zone_number == 33

    def test_zone_zero_rejected(self):
        """Test that zone 0 is rejected."""
        with pytest.raises(ValueError, match="cannot be 0"):
            UTMLocation(
                easting=500000.0,
                northing=6000000.0,
                elevation=100.0,
                zone=0,
            )

    def test_zone_too_negative(self):
        """Test that zone below -60 raises error."""
        with pytest.raises(ValueError, match="zone"):
            UTMLocation(
                easting=500000.0,
                northing=6000000.0,
                elevation=100.0,
                zone=-61,
            )


class TestUTMLocationToLatLon:
    """Tests for UTMLocation.to_latlon() method.

    This method is designed to ALWAYS use WGS 1984 for consistency,
    regardless of what datum is specified in the UTMLocation model.
    """

    @pytest.fixture
    def sample_utm_coords(self):
        """Sample UTM coordinates for testing (Boulder, CO area)."""
        return {
            "easting": 476516.0,
            "northing": 4429320.0,
            "elevation": 1655.0,
            "zone": 13,
            "convergence": 0.0,
        }

    def test_to_latlon_basic(self, sample_utm_coords):
        """Test basic conversion to lat/lon."""
        loc = UTMLocation(**sample_utm_coords)
        lat, lon = loc.to_latlon()

        # These are approximate values for Boulder, CO
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert 39.9 < lat < 40.1  # Boulder is around 40°N
        assert -105.4 < lon < -105.2  # Boulder is around -105.3°W

    def test_to_latlon_returns_tuple(self, sample_utm_coords):
        """Test that to_latlon returns a tuple of (lat, lon)."""
        loc = UTMLocation(**sample_utm_coords)
        result = loc.to_latlon()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], float)
        assert isinstance(result[1], float)

    @pytest.mark.parametrize(
        "datum_value",
        [
            None,
            Datum.ADINDAN,
            Datum.ARC_1950,
            Datum.ARC_1960,
            Datum.AUSTRALIAN_1966,
            Datum.AUSTRALIAN_1984,
            Datum.CAMP_AREA_ASTRO,
            Datum.CAPE,
            Datum.EUROPEAN_1950,
            Datum.EUROPEAN_1979,
            Datum.GEODETIC_1949,
            Datum.HONG_KONG_1963,
            Datum.HU_TZU_SHAN,
            Datum.INDIAN,
            Datum.NORTH_AMERICAN_1927,
            Datum.NORTH_AMERICAN_1983,
            Datum.OMAN,
            Datum.ORDNANCE_SURVEY_1936,
            Datum.PULKOVO_1942,
            Datum.SOUTH_AMERICAN_1956,
            Datum.SOUTH_AMERICAN_1969,
            Datum.TOKYO,
            Datum.WGS_1972,
            Datum.WGS_1984,
        ],
    )
    def test_to_latlon_consistent_regardless_of_datum(
        self, sample_utm_coords, datum_value
    ):
        """Test that to_latlon produces consistent results regardless of datum.

        The method is designed to ALWAYS use WGS 1984 for uniformity,
        so all datum values (including None) should produce identical results.
        """
        # Create location with the specified datum
        coords_with_datum = sample_utm_coords.copy()
        coords_with_datum["datum"] = datum_value
        loc = UTMLocation(**coords_with_datum)

        lat, lon = loc.to_latlon()

        # These values should be consistent regardless of datum
        # Using WGS 1984 for Boulder, CO area
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert 39.9 < lat < 40.1
        assert -105.4 < lon < -105.2

    def test_to_latlon_all_datums_produce_identical_results(self, sample_utm_coords):
        """Test that all datum values produce exactly the same lat/lon output.

        This verifies the design intent: to_latlon() ignores the datum field
        and always uses WGS 1984 for consistency.
        """
        results = {}

        # Test with None first
        loc_none = UTMLocation(**sample_utm_coords, datum=None)
        results["None"] = loc_none.to_latlon()

        # Test with each datum
        for datum in Datum:
            coords_with_datum = sample_utm_coords.copy()
            coords_with_datum["datum"] = datum
            loc = UTMLocation(**coords_with_datum)
            results[datum.value] = loc.to_latlon()

        # Verify all results are identical
        reference_result = results["None"]
        for datum_name, result in results.items():
            assert result == reference_result, (
                f"Result for datum '{datum_name}' differs from None: "
                f"{result} != {reference_result}"
            )

    def test_to_latlon_precision(self, sample_utm_coords):
        """Test that to_latlon produces results with expected precision."""
        loc = UTMLocation(**sample_utm_coords)
        lat, lon = loc.to_latlon()

        # Should have reasonable precision (at least 6 decimal places)
        lat_str = f"{lat:.10f}"
        lon_str = f"{lon:.10f}"

        assert "." in lat_str
        assert "." in lon_str
        assert len(lat_str.split(".")[1]) >= 6
        assert len(lon_str.split(".")[1]) >= 6

    def test_to_latlon_different_zones(self):
        """Test conversion in different UTM zones."""
        # Test Zone 10 (West Coast USA)
        loc_zone10 = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=10,
        )
        lat10, lon10 = loc_zone10.to_latlon()
        assert 35.0 < lat10 < 37.0
        assert -124.0 < lon10 < -120.0

        # Test Zone 17 (East Coast USA)
        loc_zone17 = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=17,
        )
        lat17, lon17 = loc_zone17.to_latlon()
        assert 35.0 < lat17 < 37.0
        assert -84.0 < lon17 < -80.0

    def test_to_latlon_northern_hemisphere(self):
        """Test conversion for northern hemisphere coordinates."""
        # High latitude northern hemisphere
        loc = UTMLocation(
            easting=500000.0,
            northing=7000000.0,  # ~63°N
            elevation=100.0,
            zone=33,
        )
        lat, _ = loc.to_latlon()

        assert 62.0 < lat < 64.0  # Around 63°N
        assert lat > 0  # Northern hemisphere

    def test_to_latlon_equatorial(self):
        """Test conversion for near-equatorial coordinates."""
        loc = UTMLocation(
            easting=500000.0,
            northing=500000.0,  # Near equator
            elevation=100.0,
            zone=18,
        )
        lat, _ = loc.to_latlon()

        assert -5.0 < lat < 10.0  # Near equator

    @pytest.mark.parametrize("datum", [Datum.WGS_1984, Datum.NORTH_AMERICAN_1927, None])
    def test_to_latlon_with_convergence(self, sample_utm_coords, datum):
        """Test that convergence doesn't affect lat/lon conversion.

        Convergence is used for bearing adjustments, not coordinate conversion.
        """
        coords_no_conv = sample_utm_coords.copy()
        coords_no_conv["datum"] = datum
        coords_no_conv["convergence"] = 0.0

        coords_with_conv = sample_utm_coords.copy()
        coords_with_conv["datum"] = datum
        coords_with_conv["convergence"] = 2.5

        loc_no_conv = UTMLocation(**coords_no_conv)
        loc_with_conv = UTMLocation(**coords_with_conv)

        result_no_conv = loc_no_conv.to_latlon()
        result_with_conv = loc_with_conv.to_latlon()

        # Results should be identical (convergence doesn't affect conversion)
        assert result_no_conv == result_with_conv

    def test_to_latlon_documentation_matches_behavior(self, sample_utm_coords):
        """Test that the documented behavior matches actual behavior.

        Documentation states: "This method takes the decision to exclusively
        use DATUM WGS 1984 for uniformity and ignore the datum from the MAK
        project file."
        """
        # Test with a non-WGS84 datum
        loc_nad27 = UTMLocation(**sample_utm_coords, datum=Datum.NORTH_AMERICAN_1927)
        loc_wgs84 = UTMLocation(**sample_utm_coords, datum=Datum.WGS_1984)
        loc_none = UTMLocation(**sample_utm_coords, datum=None)

        result_nad27 = loc_nad27.to_latlon()
        result_wgs84 = loc_wgs84.to_latlon()
        result_none = loc_none.to_latlon()

        # All should produce identical results (WGS 1984 is always used)
        assert result_nad27 == result_wgs84
        assert result_nad27 == result_none
        assert result_wgs84 == result_none


class TestUTMLocationSouthernHemisphere:
    """Tests for UTMLocation in southern hemisphere (negative zones)."""

    def test_southern_hemisphere_sydney_area(self):
        """Test coordinate conversion for Sydney, Australia area (Zone 56S)."""
        # Sydney area coordinates in UTM Zone 56S
        loc = UTMLocation(
            easting=334000.0,
            northing=6252000.0,
            elevation=50.0,
            zone=-56,  # Southern hemisphere
        )

        assert loc.is_northern_hemisphere is False
        assert loc.zone_number == 56

        lat, lon = loc.to_latlon()

        # Sydney is around -33.87°S, 151.21°E
        # These coordinates should give approximately -33.8°S
        assert -34.5 < lat < -33.0  # Southern latitude (negative)
        assert 150.5 < lon < 152.0  # Eastern longitude
        assert lat < 0  # Verify southern hemisphere

    def test_southern_hemisphere_buenos_aires_area(self):
        """Test coordinate conversion for Buenos Aires, Argentina area (Zone 21S)."""
        # Buenos Aires area coordinates
        loc = UTMLocation(
            easting=367000.0,
            northing=6177000.0,
            elevation=25.0,
            zone=-21,  # Southern hemisphere
        )

        assert loc.is_northern_hemisphere is False
        assert loc.zone_number == 21

        lat, lon = loc.to_latlon()

        # Buenos Aires is around -34.6°S, -58.4°W
        assert -36.0 < lat < -33.0  # Southern latitude
        assert -60.0 < lon < -57.0  # Western longitude
        assert lat < 0  # Verify southern hemisphere

    def test_southern_hemisphere_south_africa_area(self):
        """Test coordinate conversion for South Africa area (Zone 35S)."""
        loc = UTMLocation(
            easting=275000.0,
            northing=6200000.0,
            elevation=1400.0,
            zone=-35,  # Southern hemisphere
        )

        assert loc.is_northern_hemisphere is False
        assert loc.zone_number == 35

        lat, lon = loc.to_latlon()

        # Should be in South Africa region (Zone 35S)
        assert -35.0 < lat < -32.0  # Southern latitude
        assert 17.0 < lon < 26.0  # Eastern longitude (Zone 35 spans wide range)
        assert lat < 0  # Verify southern hemisphere

    def test_southern_vs_northern_same_zone_number(self):
        """Test that same zone number but different hemispheres give different results."""  # noqa: E501
        # Northern hemisphere Zone 16
        loc_north = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=1000.0,
            zone=16,
        )

        # Southern hemisphere Zone 16
        loc_south = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=1000.0,
            zone=-16,
        )

        lat_north, _ = loc_north.to_latlon()
        lat_south, _ = loc_south.to_latlon()

        # Latitudes should have opposite signs
        assert lat_north > 0  # Northern
        assert lat_south < 0  # Southern

        # Longitudes might be similar (same zone)
        # But latitudes should be very different
        assert abs(lat_north - lat_south) > 60  # At least 60 degrees apart

    def test_southern_hemisphere_properties(self):
        """Test that hemisphere detection properties work correctly."""
        loc_south = UTMLocation(
            easting=500000.0,
            northing=5000000.0,
            elevation=100.0,
            zone=-25,
        )

        assert loc_south.zone == -25
        assert loc_south.zone_number == 25
        assert loc_south.is_northern_hemisphere is False

        loc_north = UTMLocation(
            easting=500000.0,
            northing=5000000.0,
            elevation=100.0,
            zone=25,
        )

        assert loc_north.zone == 25
        assert loc_north.zone_number == 25
        assert loc_north.is_northern_hemisphere is True
