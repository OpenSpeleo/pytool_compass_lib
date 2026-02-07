# -*- coding: utf-8 -*-
"""Tests for Datum enum and datum validation.

This test module verifies:
1. All datum values from MAK files are properly defined in the enum
2. MAK files can be loaded with any datum value
3. Datum normalization and aliasing works correctly
4. Datum validation rejects invalid values
"""

import pytest

from compass_lib.enums import Datum
from compass_lib.models import UTMLocation
from compass_lib.project.format import format_directive
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import DatumDirective
from compass_lib.project.parser import CompassProjectParser


class TestDatumEnum:
    """Test the Datum enum."""

    def test_all_datum_values_exist(self):
        """Test that all expected datum values are defined."""
        expected_datums = [
            "Adindan",
            "Arc 1950",
            "Arc 1960",
            "Australian 1966",
            "Australian 1984",
            "Camp Area Astro",
            "Cape",
            "European 1950",
            "European 1979",
            "Geodetic 1949",
            "Hong Kong 1963",
            "Hu Tzu Shan",
            "Indian",
            "North American 1927",
            "North American 1983",
            "Oman",
            "Ordnance Survey 1936",
            "Pulkovo 1942",
            "South American 1956",
            "South American 1969",
            "Tokyo",
            "WGS 1972",
            "WGS 1984",
        ]

        actual_datums = [datum.value for datum in Datum]

        assert len(actual_datums) == len(expected_datums)
        for expected in expected_datums:
            assert expected in actual_datums, f"Missing datum: {expected}"

    def test_datum_enum_values(self):
        """Test that datum enum values match expected format."""
        assert Datum.ADINDAN.value == "Adindan"
        assert Datum.ARC_1950.value == "Arc 1950"
        assert Datum.ARC_1960.value == "Arc 1960"
        assert Datum.AUSTRALIAN_1966.value == "Australian 1966"
        assert Datum.AUSTRALIAN_1984.value == "Australian 1984"
        assert Datum.CAMP_AREA_ASTRO.value == "Camp Area Astro"
        assert Datum.CAPE.value == "Cape"
        assert Datum.EUROPEAN_1950.value == "European 1950"
        assert Datum.EUROPEAN_1979.value == "European 1979"
        assert Datum.GEODETIC_1949.value == "Geodetic 1949"
        assert Datum.HONG_KONG_1963.value == "Hong Kong 1963"
        assert Datum.HU_TZU_SHAN.value == "Hu Tzu Shan"
        assert Datum.INDIAN.value == "Indian"
        assert Datum.NORTH_AMERICAN_1927.value == "North American 1927"
        assert Datum.NORTH_AMERICAN_1983.value == "North American 1983"
        assert Datum.OMAN.value == "Oman"
        assert Datum.ORDNANCE_SURVEY_1936.value == "Ordnance Survey 1936"
        assert Datum.PULKOVO_1942.value == "Pulkovo 1942"
        assert Datum.SOUTH_AMERICAN_1956.value == "South American 1956"
        assert Datum.SOUTH_AMERICAN_1969.value == "South American 1969"
        assert Datum.TOKYO.value == "Tokyo"
        assert Datum.WGS_1972.value == "WGS 1972"
        assert Datum.WGS_1984.value == "WGS 1984"


class TestDatumNormalization:
    """Test datum normalization and aliasing."""

    def test_normalize_exact_match(self):
        """Test normalization with exact datum names."""
        assert Datum.normalize("WGS 1984") == Datum.WGS_1984
        assert Datum.normalize("North American 1927") == Datum.NORTH_AMERICAN_1927
        assert Datum.normalize("Arc 1950") == Datum.ARC_1950

    def test_normalize_case_insensitive(self):
        """Test normalization is case-insensitive."""
        assert Datum.normalize("wgs 1984") == Datum.WGS_1984
        assert Datum.normalize("WGS 1984") == Datum.WGS_1984
        assert Datum.normalize("WgS 1984") == Datum.WGS_1984
        assert Datum.normalize("north american 1927") == Datum.NORTH_AMERICAN_1927
        assert Datum.normalize("NORTH AMERICAN 1927") == Datum.NORTH_AMERICAN_1927

    def test_normalize_none(self):
        """Test normalization with None input."""
        assert Datum.normalize(None) is None

    def test_normalize_whitespace(self):
        """Test normalization handles whitespace."""
        assert Datum.normalize("  WGS 1984  ") == Datum.WGS_1984
        assert Datum.normalize("  North American 1927  ") == Datum.NORTH_AMERICAN_1927

    def test_normalize_invalid_datum(self):
        """Test normalization rejects invalid datum names."""
        with pytest.raises(ValueError, match="Unknown datum"):
            Datum.normalize("Invalid Datum")
        with pytest.raises(ValueError, match="Unknown datum"):
            Datum.normalize("XYZ123")

    def test_from_string_alias(self):
        """Test from_string() is an alias for normalize()."""
        assert Datum.from_string("WGS 1984") == Datum.WGS_1984
        assert Datum.from_string("Arc 1950") == Datum.ARC_1950
        assert Datum.from_string(None) is None


class TestDatumDirective:
    """Test DatumDirective model with Datum enum."""

    def test_create_with_enum(self):
        """Test creating DatumDirective with Datum enum."""
        directive = DatumDirective(datum=Datum.WGS_1984)
        assert directive.datum == Datum.WGS_1984
        assert isinstance(directive.datum, Datum)

    def test_create_with_string(self):
        """Test creating DatumDirective with string (should normalize)."""
        directive = DatumDirective(datum="WGS 1984")
        assert directive.datum == Datum.WGS_1984
        assert isinstance(directive.datum, Datum)

    def test_create_with_full_name(self):
        """Test creating DatumDirective with full datum name."""
        directive = DatumDirective(datum="North American 1927")
        assert directive.datum == Datum.NORTH_AMERICAN_1927
        assert isinstance(directive.datum, Datum)

    def test_str_representation(self):
        """Test string representation uses datum value."""
        directive = DatumDirective(datum=Datum.WGS_1984)
        assert str(directive) == "&WGS 1984;"

        directive = DatumDirective(datum=Datum.NORTH_AMERICAN_1927)
        assert str(directive) == "&North American 1927;"

    def test_create_with_invalid_datum(self):
        """Test creating DatumDirective with invalid datum raises error."""
        with pytest.raises(ValueError, match="Unknown datum"):
            DatumDirective(datum="Invalid Datum")


class TestMAKFileWithAllDatums:
    """Test that MAK files can be loaded with any datum value."""

    @pytest.fixture
    def mak_template(self):
        """Template for MAK file content."""
        return """@458708.000,2254046.000,0.000,16,-0.140;
&{datum};
!gIvotscxpl;

/
$16;
&{datum};
*0.00;
#TestCave.DAT;
"""

    @pytest.mark.parametrize(
        "datum_value",
        [
            "Adindan",
            "Arc 1950",
            "Arc 1960",
            "Australian 1966",
            "Australian 1984",
            "Camp Area Astro",
            "Cape",
            "European 1950",
            "European 1979",
            "Geodetic 1949",
            "Hong Kong 1963",
            "Hu Tzu Shan",
            "Indian",
            "North American 1927",
            "North American 1983",
            "Oman",
            "Ordnance Survey 1936",
            "Pulkovo 1942",
            "South American 1956",
            "South American 1969",
            "Tokyo",
            "WGS 1972",
            "WGS 1984",
        ],
    )
    def test_parse_mak_with_datum(self, mak_template, datum_value):
        """Test parsing MAK file with each datum value."""
        mak_content = mak_template.format(datum=datum_value)
        parser = CompassProjectParser()
        parsed = parser.parse_string_to_dict(mak_content)

        # Validate the parsed data

        mak_file = CompassMakFile.model_validate(parsed)

        # Check that datum directives are present and correct
        datum_directives = [
            d for d in mak_file.directives if hasattr(d, "datum") and d.type == "datum"
        ]
        assert len(datum_directives) == 2, (
            f"Expected 2 datum directives for {datum_value}"
        )

        for directive in datum_directives:
            assert isinstance(directive.datum, Datum), (
                f"Datum should be enum for {datum_value}"
            )
            assert directive.datum.value == datum_value, (
                f"Datum value mismatch for {datum_value}"
            )

    @pytest.mark.parametrize(
        ("datum_variant", "expected_datum"),
        [
            ("north american 1927", Datum.NORTH_AMERICAN_1927),
            ("NORTH AMERICAN 1927", Datum.NORTH_AMERICAN_1927),
            ("North American 1927", Datum.NORTH_AMERICAN_1927),
            ("wgs 1984", Datum.WGS_1984),
            ("WGS 1984", Datum.WGS_1984),
            ("  Arc 1950  ", Datum.ARC_1950),  # With whitespace
        ],
    )
    def test_parse_mak_with_datum_variants(
        self, mak_template, datum_variant, expected_datum
    ):
        """Test parsing MAK file with different datum string variations."""
        mak_content = mak_template.format(datum=datum_variant)
        parser = CompassProjectParser()
        parsed = parser.parse_string_to_dict(mak_content)

        mak_file = CompassMakFile.model_validate(parsed)

        # Check that datum variations are normalized correctly
        datum_directives = [
            d for d in mak_file.directives if hasattr(d, "datum") and d.type == "datum"
        ]
        assert len(datum_directives) == 2

        for directive in datum_directives:
            assert directive.datum == expected_datum

    def test_roundtrip_datum_preservation(self):
        """Test that datum values are preserved in roundtrip parsing and
        formatting."""
        # Test roundtrip for each datum
        for datum in Datum:
            directive = DatumDirective(datum=datum)
            formatted = format_directive(directive)

            # Parse the formatted string
            parser = CompassProjectParser()
            parsed = parser.parse_string_to_dict(formatted)

            mak_file = CompassMakFile.model_validate(parsed)

            # Verify the datum is preserved
            assert len(mak_file.directives) == 1
            assert isinstance(mak_file.directives[0], DatumDirective)
            assert mak_file.directives[0].datum == datum
            assert mak_file.directives[0].datum.value == datum.value


class TestUTMLocationWithDatum:
    """Test UTMLocation model with Datum enum."""

    def test_create_with_datum_enum(self):
        """Test creating UTMLocation with Datum enum."""

        location = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            datum=Datum.WGS_1984,
        )
        assert location.datum == Datum.WGS_1984
        assert isinstance(location.datum, Datum)

    def test_create_with_datum_string(self):
        """Test creating UTMLocation with datum string."""

        location = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            datum="WGS 1984",
        )
        assert location.datum == Datum.WGS_1984
        assert isinstance(location.datum, Datum)

    def test_create_with_datum_case_insensitive(self):
        """Test creating UTMLocation with case-insensitive datum name."""

        location = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            datum="north american 1927",
        )
        assert location.datum == Datum.NORTH_AMERICAN_1927
        assert isinstance(location.datum, Datum)

    def test_create_with_none_datum(self):
        """Test creating UTMLocation with None datum."""

        location = UTMLocation(
            easting=500000.0,
            northing=4000000.0,
            elevation=100.0,
            zone=13,
            datum=None,
        )
        assert location.datum is None

    def test_create_with_invalid_datum(self):
        """Test creating UTMLocation with invalid datum raises error."""
        with pytest.raises(ValueError, match="Unknown datum"):
            UTMLocation(
                easting=500000.0,
                northing=4000000.0,
                elevation=100.0,
                zone=13,
                datum="Invalid Datum",
            )
