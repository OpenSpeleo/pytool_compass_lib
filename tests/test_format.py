# -*- coding: utf-8 -*-
"""Tests for formatting (serialization) modules."""

from datetime import date

import pytest

from compass_scratchpad.enums import AzimuthUnit
from compass_scratchpad.enums import InclinationUnit
from compass_scratchpad.enums import LengthUnit
from compass_scratchpad.project.format import format_directive
from compass_scratchpad.project.format import format_mak_file
from compass_scratchpad.project.models import CommentDirective
from compass_scratchpad.project.models import DatumDirective
from compass_scratchpad.project.models import FileDirective
from compass_scratchpad.project.models import FlagsDirective
from compass_scratchpad.project.models import LocationDirective
from compass_scratchpad.project.models import UTMConvergenceDirective
from compass_scratchpad.project.models import UTMZoneDirective
from compass_scratchpad.survey.format import format_dat_file
from compass_scratchpad.survey.format import format_shot
from compass_scratchpad.survey.format import format_trip_header
from compass_scratchpad.survey.models import CompassShot
from compass_scratchpad.survey.models import CompassTrip
from compass_scratchpad.survey.models import CompassTripHeader


class TestFormatShot:
    """Tests for format_shot function."""

    def test_basic_shot(self):
        """Test formatting a basic shot."""
        header = CompassTripHeader(has_backsights=False)
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.5,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
            left=1.0,
            right=2.0,
            up=3.0,
            down=0.5,
        )
        result = format_shot(shot, header)

        assert "A1" in result
        assert "A2" in result
        assert "10.50" in result
        assert "45.00" in result
        assert "-5.00" in result
        assert result.endswith("\r\n")

    def test_shot_with_missing_values(self):
        """Test formatting a shot with missing values."""
        header = CompassTripHeader(has_backsights=False)
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.0,
            frontsight_azimuth=45.0,
            frontsight_inclination=None,  # Missing
            left=None,  # Missing
            right=None,  # Missing
            up=None,  # Missing
            down=None,  # Missing
        )
        result = format_shot(shot, header)

        # Should contain -999.00 for missing values
        assert "-999.00" in result

    def test_shot_with_backsights(self):
        """Test formatting a shot with backsights."""
        header = CompassTripHeader(has_backsights=True)
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.0,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
            backsight_azimuth=225.0,
            backsight_inclination=5.0,
        )
        result = format_shot(shot, header)

        assert "225.00" in result
        assert "5.00" in result

    def test_shot_with_flags(self):
        """Test formatting a shot with flags."""
        header = CompassTripHeader(has_backsights=False)
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.0,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
            excluded_from_length=True,
            excluded_from_plotting=True,
        )
        result = format_shot(shot, header)

        assert "#|LP#" in result

    def test_shot_with_comment(self):
        """Test formatting a shot with comment."""
        header = CompassTripHeader(has_backsights=False)
        shot = CompassShot(
            from_station_name="A1",
            to_station_name="A2",
            length=10.0,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
            comment="Big Room",
        )
        result = format_shot(shot, header)

        assert "Big Room" in result

    def test_invalid_station_name_raises(self):
        """Test that invalid station names raise error."""
        header = CompassTripHeader(has_backsights=False)
        shot = CompassShot(
            from_station_name="A 1",  # Invalid: space
            to_station_name="A2",
            length=10.0,
            frontsight_azimuth=45.0,
            frontsight_inclination=-5.0,
        )

        with pytest.raises(ValueError, match="Invalid station name"):
            format_shot(shot, header)


class TestFormatTripHeader:
    """Tests for format_trip_header function."""

    def test_basic_header(self):
        """Test formatting a basic header."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            length_unit=LengthUnit.DECIMAL_FEET,
            azimuth_unit=AzimuthUnit.DEGREES,
            inclination_unit=InclinationUnit.DEGREES,
            has_backsights=False,
        )
        result = format_trip_header(header)

        assert "SECRET CAVE" in result
        assert "SURVEY NAME: A" in result
        assert "SURVEY DATE: 7 10 1979" in result
        assert "DECLINATION: 1.00" in result
        assert "FORMAT:" in result

    def test_header_with_team(self):
        """Test formatting header with team."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            team="D.SMITH,R.BROWN",
        )
        result = format_trip_header(header)

        assert "SURVEY TEAM:" in result
        assert "D.SMITH,R.BROWN" in result

    def test_header_with_comment(self):
        """Test formatting header with comment."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            comment="Entrance Passage",
        )
        result = format_trip_header(header)

        assert "COMMENT:Entrance Passage" in result

    def test_header_with_corrections(self):
        """Test formatting header with corrections."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            length_correction=2.0,
            frontsight_azimuth_correction=3.0,
            frontsight_inclination_correction=4.0,
        )
        result = format_trip_header(header)

        assert "CORRECTIONS:" in result
        assert "2.00" in result
        assert "3.00" in result
        assert "4.00" in result

    def test_header_without_column_headers(self):
        """Test formatting header without column headers."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
        )
        result = format_trip_header(header, include_column_headers=False)

        assert "FROM" not in result
        assert "LEN" not in result


class TestFormatDatFile:
    """Tests for format_dat_file function."""

    def test_single_trip(self):
        """Test formatting a file with one trip."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            has_backsights=False,
        )
        shots = [
            CompassShot(
                from_station_name="A1",
                to_station_name="A2",
                length=10.0,
                frontsight_azimuth=45.0,
                frontsight_inclination=-5.0,
            ),
        ]
        trip = CompassTrip(header=header, shots=shots)

        result = format_dat_file([trip])

        assert result is not None
        assert "SECRET CAVE" in result
        assert "A1" in result
        assert "\f\r\n" in result  # Form feed separator

    def test_multiple_trips(self):
        """Test formatting a file with multiple trips."""
        trips = []
        for name in ["A", "B"]:
            header = CompassTripHeader(
                cave_name="SECRET CAVE",
                survey_name=name,
                date=date(1979, 7, 10),
                declination=1.0,
                has_backsights=False,
            )
            shots = [
                CompassShot(
                    from_station_name=f"{name}1",
                    to_station_name=f"{name}2",
                    length=10.0,
                    frontsight_azimuth=45.0,
                    frontsight_inclination=-5.0,
                ),
            ]
            trips.append(CompassTrip(header=header, shots=shots))

        result = format_dat_file(trips)

        assert result is not None
        assert result.count("\f") == 2  # Two form feeds

    def test_streaming_mode(self):
        """Test streaming mode with write callback."""
        header = CompassTripHeader(
            cave_name="SECRET CAVE",
            survey_name="A",
            date=date(1979, 7, 10),
            declination=1.0,
            has_backsights=False,
        )
        shots = [
            CompassShot(
                from_station_name="A1",
                to_station_name="A2",
                length=10.0,
                frontsight_azimuth=45.0,
                frontsight_inclination=-5.0,
            ),
        ]
        trip = CompassTrip(header=header, shots=shots)

        chunks: list[str] = []
        result = format_dat_file([trip], write=chunks.append)

        assert result is None  # Returns None in streaming mode
        assert len(chunks) > 0
        assert "".join(chunks).count("\f") == 1


class TestFormatMakDirective:
    """Tests for format_directive function."""

    def test_comment_directive(self):
        """Test formatting comment directive."""
        directive = CommentDirective(comment="This is a comment")
        result = format_directive(directive)
        assert result == "/This is a comment\r\n"

    def test_datum_directive(self):
        """Test formatting datum directive."""
        directive = DatumDirective(datum="North American 1983")
        result = format_directive(directive)
        assert result == "&North American 1983;\r\n"

    def test_utm_zone_directive(self):
        """Test formatting UTM zone directive."""
        directive = UTMZoneDirective(utm_zone=13)
        result = format_directive(directive)
        assert result == "$13;\r\n"

    def test_utm_zone_directive_negative(self):
        """Test formatting negative UTM zone directive (southern hemisphere)."""
        directive = UTMZoneDirective(utm_zone=-13)
        result = format_directive(directive)
        assert result == "$-13;\r\n"

    def test_utm_convergence_directive(self):
        """Test formatting UTM convergence directive."""
        directive = UTMConvergenceDirective(utm_convergence=-0.26)
        result = format_directive(directive)
        assert result == "%-0.260;\r\n"

    def test_flags_directive(self):
        """Test formatting flags directive."""
        directive = FlagsDirective(flags=0)
        result = format_directive(directive)
        assert result == "!ot;\r\n"

        directive = FlagsDirective(
            flags=FlagsDirective.OVERRIDE_LRUDS | FlagsDirective.LRUDS_AT_TO_STATION
        )
        result = format_directive(directive)
        assert result == "!OT;\r\n"

    def test_location_directive(self):
        """Test formatting location directive."""
        directive = LocationDirective(
            easting=546866.9,
            northing=3561472.9,
            elevation=1414.1,
            utm_zone=13,
            utm_convergence=-0.26,
        )
        result = format_directive(directive)
        assert result.startswith("@")
        assert result.endswith(";\r\n")
        assert "546866.900" in result

    def test_file_directive_simple(self):
        """Test formatting simple file directive."""
        directive = FileDirective(file="ENTRANCE.DAT")
        result = format_directive(directive)
        assert result == "#ENTRANCE.DAT;\r\n"


class TestFormatMakFile:
    """Tests for format_mak_file function."""

    def test_multiple_directives(self):
        """Test formatting multiple directives."""
        directives = [
            DatumDirective(datum="North American 1983"),
            UTMZoneDirective(utm_zone=13),
            FileDirective(file="ENTRANCE.DAT"),
        ]

        result = format_mak_file(directives)

        assert result is not None
        assert "&North American 1983;" in result
        assert "$13;" in result
        assert "#ENTRANCE.DAT;" in result
