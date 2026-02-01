# -*- coding: utf-8 -*-
"""Tests for project module."""

from pathlib import Path

import pytest

from compass_lib.errors import CompassParseException
from compass_lib.models import NEVLocation
from compass_lib.project.models import CommentDirective
from compass_lib.project.models import DatumDirective
from compass_lib.project.models import DeclinationMode
from compass_lib.project.models import FileDirective
from compass_lib.project.models import FlagsDirective
from compass_lib.project.models import FolderEndDirective
from compass_lib.project.models import FolderStartDirective
from compass_lib.project.models import LinkStation
from compass_lib.project.models import LocationDirective
from compass_lib.project.models import UnknownDirective
from compass_lib.project.models import UTMConvergenceDirective
from compass_lib.project.models import UTMZoneDirective
from compass_lib.project.parser import CompassProjectParser


class TestCommentDirective:
    """Tests for CommentDirective model."""

    def test_creation(self):
        """Test creating a comment directive."""
        directive = CommentDirective(comment="This is a comment")
        assert directive.comment == "This is a comment"

    def test_str(self):
        """Test string representation."""
        directive = CommentDirective(comment="Test comment")
        assert str(directive) == "/ Test comment"


class TestFolderStartDirective:
    """Tests for FolderStartDirective model."""

    def test_creation(self):
        """Test creating a folder start directive."""
        directive = FolderStartDirective(name="Mouse Palace")
        assert directive.name == "Mouse Palace"
        assert directive.type == "folder_start"

    def test_str(self):
        """Test string representation."""
        directive = FolderStartDirective(name="Folder-1")
        assert str(directive) == "[Folder-1;"


class TestFolderEndDirective:
    """Tests for FolderEndDirective model."""

    def test_creation(self):
        """Test creating a folder end directive."""
        directive = FolderEndDirective()
        assert directive.type == "folder_end"

    def test_str(self):
        """Test string representation."""
        directive = FolderEndDirective()
        assert str(directive) == "];"


class TestDatumDirective:
    """Tests for DatumDirective model."""

    def test_creation(self):
        """Test creating a datum directive."""
        directive = DatumDirective(datum="North American 1983")
        assert directive.datum == "North American 1983"

    def test_str(self):
        """Test string representation."""
        directive = DatumDirective(datum="North American 1983")
        assert str(directive) == "&North American 1983;"


class TestUTMZoneDirective:
    """Tests for UTMZoneDirective model."""

    def test_creation(self):
        """Test creating a UTM zone directive."""
        directive = UTMZoneDirective(utm_zone=13)
        assert directive.utm_zone == 13

    def test_str(self):
        """Test string representation."""
        directive = UTMZoneDirective(utm_zone=13)
        assert str(directive) == "$13;"

    def test_validation_too_low(self):
        """Test that zone < 1 raises ValueError."""
        with pytest.raises(ValueError, match="UTM zone"):
            UTMZoneDirective(utm_zone=0)

    def test_validation_too_high(self):
        """Test that zone > 60 raises ValueError."""
        with pytest.raises(ValueError, match="UTM zone"):
            UTMZoneDirective(utm_zone=61)

    def test_southern_hemisphere_zone(self):
        """Test creating directive with negative zone (southern hemisphere)."""
        directive = UTMZoneDirective(utm_zone=-13)
        assert directive.utm_zone == -13
        assert str(directive) == "$-13;"

    def test_zone_too_negative(self):
        """Test that zone < -60 raises ValueError."""
        with pytest.raises(
            ValueError,
            match=r".*UTM zone must be between -60 and 60 \(excluding 0\), got -61.*",
        ):
            UTMZoneDirective(utm_zone=-61)


class TestUTMConvergenceDirective:
    """Tests for UTMConvergenceDirective model."""

    def test_creation_enabled_default(self):
        """Test creating a UTM convergence directive defaults to enabled."""
        directive = UTMConvergenceDirective(utm_convergence=-0.26)
        assert directive.utm_convergence == pytest.approx(-0.26)
        assert directive.enabled is True

    def test_creation_enabled_explicit(self):
        """Test creating a UTM convergence directive with enabled=True."""
        directive = UTMConvergenceDirective(utm_convergence=1.5, enabled=True)
        assert directive.utm_convergence == pytest.approx(1.5)
        assert directive.enabled is True

    def test_creation_disabled(self):
        """Test creating a UTM convergence directive with enabled=False."""
        directive = UTMConvergenceDirective(utm_convergence=0.0, enabled=False)
        assert directive.utm_convergence == pytest.approx(0.0)
        assert directive.enabled is False

    def test_str_enabled(self):
        """Test string representation when enabled (% prefix)."""
        directive = UTMConvergenceDirective(utm_convergence=2.04, enabled=True)
        assert str(directive) == "%2.040;"

    def test_str_disabled(self):
        """Test string representation when disabled (* prefix)."""
        directive = UTMConvergenceDirective(utm_convergence=0.0, enabled=False)
        assert str(directive) == "*0.000;"


class TestFlagsDirective:
    """Tests for FlagsDirective model.

    Tests all 10 documented Compass project flags:
    1. G/g - Global override settings enabled/disabled
    2. I/E/A - Declination mode (Ignore/Entered/Auto)
    3. V/v - Apply UTM convergence enabled/disabled
    4. O/o - Override LRUD associations enabled/disabled
    5. T/t - LRUDs at To/From station
    6. S/s - Apply shot flags enabled/disabled
    7. X/x - Apply total exclusion flags enabled/disabled
    8. P/p - Apply plotting exclusion flags enabled/disabled
    9. L/l - Apply length exclusion flags enabled/disabled
    10. C/c - Apply close exclusion flags enabled/disabled
    """

    def test_creation_defaults(self):
        """Test creating a flags directive with all defaults (False)."""
        directive = FlagsDirective()
        assert directive.global_override is False
        assert directive.declination_mode is None
        assert directive.apply_utm_convergence is False
        assert directive.override_lruds is False
        assert directive.lruds_at_to_station is False
        assert directive.apply_shot_flags is False
        assert directive.apply_total_exclusion is False
        assert directive.apply_plotting_exclusion is False
        assert directive.apply_length_exclusion is False
        assert directive.apply_close_exclusion is False

    def test_creation_legacy_bitmask(self):
        """Test creating a flags directive using legacy bitmask."""
        directive = FlagsDirective(flags=0)
        assert directive.flags == 0
        assert not directive.is_override_lruds
        assert not directive.is_lruds_at_to_station

    def test_global_override_flag(self):
        """Test G/g global override flag."""
        directive = FlagsDirective(global_override=True)
        assert directive.global_override is True

    def test_declination_mode_ignore(self):
        """Test I declination mode (ignore)."""
        directive = FlagsDirective(declination_mode=DeclinationMode.IGNORE)
        assert directive.declination_mode == DeclinationMode.IGNORE

    def test_declination_mode_entered(self):
        """Test E declination mode (entered)."""
        directive = FlagsDirective(declination_mode=DeclinationMode.ENTERED)
        assert directive.declination_mode == DeclinationMode.ENTERED

    def test_declination_mode_auto(self):
        """Test A declination mode (auto-calculated)."""
        directive = FlagsDirective(declination_mode=DeclinationMode.AUTO)
        assert directive.declination_mode == DeclinationMode.AUTO

    def test_apply_utm_convergence_flag(self):
        """Test V/v apply UTM convergence flag."""
        directive = FlagsDirective(apply_utm_convergence=True)
        assert directive.apply_utm_convergence is True

    def test_override_lruds_flag(self):
        """Test O/o override LRUDs flag."""
        directive = FlagsDirective(flags=FlagsDirective.OVERRIDE_LRUDS)
        assert directive.is_override_lruds
        assert not directive.is_lruds_at_to_station

    def test_lruds_at_to_station_flag(self):
        """Test T/t LRUDs at TO station flag."""
        directive = FlagsDirective(flags=FlagsDirective.LRUDS_AT_TO_STATION)
        assert not directive.is_override_lruds
        assert directive.is_lruds_at_to_station

    def test_apply_shot_flags_flag(self):
        """Test S/s apply shot flags."""
        directive = FlagsDirective(apply_shot_flags=True)
        assert directive.apply_shot_flags is True

    def test_apply_total_exclusion_flag(self):
        """Test X/x apply total exclusion flags."""
        directive = FlagsDirective(apply_total_exclusion=True)
        assert directive.apply_total_exclusion is True

    def test_apply_plotting_exclusion_flag(self):
        """Test P/p apply plotting exclusion flags."""
        directive = FlagsDirective(apply_plotting_exclusion=True)
        assert directive.apply_plotting_exclusion is True

    def test_apply_length_exclusion_flag(self):
        """Test L/l apply length exclusion flags."""
        directive = FlagsDirective(apply_length_exclusion=True)
        assert directive.apply_length_exclusion is True

    def test_apply_close_exclusion_flag(self):
        """Test C/c apply close exclusion flags."""
        directive = FlagsDirective(apply_close_exclusion=True)
        assert directive.apply_close_exclusion is True

    def test_both_lrud_flags(self):
        """Test both LRUD flags set (O and T)."""
        directive = FlagsDirective(
            flags=FlagsDirective.OVERRIDE_LRUDS | FlagsDirective.LRUDS_AT_TO_STATION
        )
        assert directive.is_override_lruds
        assert directive.is_lruds_at_to_station

    def test_all_flags_enabled(self):
        """Test creating directive with all flags enabled."""
        directive = FlagsDirective(
            global_override=True,
            declination_mode=DeclinationMode.AUTO,
            apply_utm_convergence=True,
            override_lruds=True,
            lruds_at_to_station=True,
            apply_shot_flags=True,
            apply_total_exclusion=True,
            apply_plotting_exclusion=True,
            apply_length_exclusion=True,
            apply_close_exclusion=True,
        )
        assert directive.global_override is True
        assert directive.declination_mode == DeclinationMode.AUTO
        assert directive.apply_utm_convergence is True
        assert directive.override_lruds is True
        assert directive.lruds_at_to_station is True
        assert directive.apply_shot_flags is True
        assert directive.apply_total_exclusion is True
        assert directive.apply_plotting_exclusion is True
        assert directive.apply_length_exclusion is True
        assert directive.apply_close_exclusion is True

    def test_str_all_defaults(self):
        """Test string representation with all flags at default (False)."""
        directive = FlagsDirective()
        assert str(directive) == "!gvotsxplc;"

    def test_str_all_enabled(self):
        """Test string representation with all flags enabled."""
        directive = FlagsDirective(
            global_override=True,
            declination_mode=DeclinationMode.AUTO,
            apply_utm_convergence=True,
            override_lruds=True,
            lruds_at_to_station=True,
            apply_shot_flags=True,
            apply_total_exclusion=True,
            apply_plotting_exclusion=True,
            apply_length_exclusion=True,
            apply_close_exclusion=True,
        )
        assert str(directive) == "!GAVOTSXPLC;"

    def test_str_with_raw_flags(self):
        """Test string representation uses raw_flags when present."""
        directive = FlagsDirective(raw_flags="gIvotscxpl")
        assert str(directive) == "!gIvotscxpl;"


class TestFileDirective:
    """Tests for FileDirective model."""

    def test_creation_no_link_stations(self):
        """Test creating a file directive without link stations."""
        directive = FileDirective(file="ENTRANCE.DAT")
        assert directive.file == "ENTRANCE.DAT"
        assert directive.link_stations == []

    def test_creation_with_link_stations(self):
        """Test creating a file directive with link stations."""

        link_stations = [
            LinkStation(
                name="A1",
                location=NEVLocation(
                    easting=1.1, northing=2.2, elevation=3.3, unit="f"
                ),
            ),
            LinkStation(name="B1", location=None),
        ]
        directive = FileDirective(file="FULFORD.DAT", link_stations=link_stations)
        assert directive.file == "FULFORD.DAT"
        assert len(directive.link_stations) == 2
        assert directive.link_stations[0].name == "A1"
        assert directive.link_stations[1].location is None

    def test_str(self):
        """Test string representation."""
        directive = FileDirective(file="ENTRANCE.DAT")
        assert str(directive) == "#ENTRANCE.DAT;"


class TestLocationDirective:
    """Tests for LocationDirective model."""

    def test_creation(self):
        """Test creating a location directive."""
        directive = LocationDirective(
            easting=546866.9,
            northing=3561472.9,
            elevation=1414.1,
            utm_zone=13,
            utm_convergence=-0.26,
        )
        assert directive.easting == pytest.approx(546866.9)
        assert directive.northing == pytest.approx(3561472.9)
        assert directive.elevation == pytest.approx(1414.1)
        assert directive.utm_zone == 13
        assert directive.utm_convergence == pytest.approx(-0.26)

    def test_str(self):
        """Test string representation."""
        directive = LocationDirective(
            easting=123.45,
            northing=345.678,
            elevation=10234.0,
            utm_zone=13,
            utm_convergence=2.04,
        )
        assert str(directive) == "@123.450,345.678,10234.000,13,2.040;"


class TestCompassProjectParser:
    """Tests for CompassProjectParser."""

    def test_parse_location(self):
        """Test parsing location directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("@546866.900,3561472.900,1414.100,13,-0.260;")

        assert len(directives) == 1
        loc = directives[0]
        assert isinstance(loc, LocationDirective)
        assert loc.easting == pytest.approx(546866.9)
        assert loc.northing == pytest.approx(3561472.9)
        assert loc.elevation == pytest.approx(1414.1)
        assert loc.utm_zone == 13
        assert loc.utm_convergence == pytest.approx(-0.26)

    def test_parse_datum(self):
        """Test parsing datum directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("&North American 1983;")

        assert len(directives) == 1
        assert isinstance(directives[0], DatumDirective)
        assert directives[0].datum == "North American 1983"

    def test_parse_utm_zone(self):
        """Test parsing UTM zone directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("$13;")

        assert len(directives) == 1
        assert isinstance(directives[0], UTMZoneDirective)
        assert directives[0].utm_zone == 13

    def test_parse_negative_utm_zone(self):
        """Test parsing negative UTM zone (southern hemisphere)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("$-13;")

        assert len(directives) == 1
        assert isinstance(directives[0], UTMZoneDirective)
        assert directives[0].utm_zone == -13

    def test_parse_location_with_negative_zone(self):
        """Test parsing location with negative zone (southern hemisphere)."""
        parser = CompassProjectParser()
        data = "@500000.0,6000000.0,100.0,-33,-1.5;"
        directives = parser.parse_string(data)

        assert len(directives) == 1
        assert isinstance(directives[0], LocationDirective)
        assert directives[0].utm_zone == -33

    def test_parse_utm_convergence_enabled(self):
        """Test parsing UTM convergence directive with % (enabled)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("%-0.26;")

        assert len(directives) == 1
        assert isinstance(directives[0], UTMConvergenceDirective)
        assert directives[0].utm_convergence == pytest.approx(-0.26)
        assert directives[0].enabled is True

    def test_parse_utm_convergence_disabled(self):
        """Test parsing UTM convergence directive with * (disabled)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("*0.00;")

        assert len(directives) == 1
        assert isinstance(directives[0], UTMConvergenceDirective)
        assert directives[0].utm_convergence == pytest.approx(0.0)
        assert directives[0].enabled is False

    def test_parse_utm_convergence_disabled_with_value(self):
        """Test parsing disabled UTM convergence with non-zero value."""
        parser = CompassProjectParser()
        directives = parser.parse_string("*12.34;")

        assert len(directives) == 1
        assert isinstance(directives[0], UTMConvergenceDirective)
        assert directives[0].utm_convergence == pytest.approx(12.34)
        assert directives[0].enabled is False

    def test_parse_flags_lowercase(self):
        """Test parsing flags directive with lowercase (all disabled)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("!ot;")

        assert len(directives) == 1
        assert isinstance(directives[0], FlagsDirective)
        assert not directives[0].is_override_lruds
        assert not directives[0].is_lruds_at_to_station

    def test_parse_flags_uppercase(self):
        """Test parsing flags directive with uppercase."""
        parser = CompassProjectParser()
        directives = parser.parse_string("!OT;")

        assert len(directives) == 1
        assert isinstance(directives[0], FlagsDirective)
        assert directives[0].is_override_lruds
        assert directives[0].is_lruds_at_to_station

    def test_parse_flags_all_10_flags(self):
        """Test parsing all 10 flags from documentation example: !GAVOTSCXPL;"""
        parser = CompassProjectParser()
        directives = parser.parse_string("!GAVOTSCXPL;")

        assert len(directives) == 1
        flags = directives[0]
        assert isinstance(flags, FlagsDirective)
        assert flags.global_override is True  # G
        assert flags.declination_mode == DeclinationMode.AUTO  # A
        assert flags.apply_utm_convergence is True  # V
        assert flags.override_lruds is True  # O
        assert flags.lruds_at_to_station is True  # T
        assert flags.apply_shot_flags is True  # S
        assert flags.apply_close_exclusion is True  # C
        assert flags.apply_total_exclusion is True  # X
        assert flags.apply_plotting_exclusion is True  # P
        assert flags.apply_length_exclusion is True  # L

    def test_parse_flags_declination_ignore(self):
        """Test parsing declination mode I (ignore)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("!gIvotscxpl;")

        assert len(directives) == 1
        flags = directives[0]
        assert isinstance(flags, FlagsDirective)
        assert flags.global_override is False  # g
        assert flags.declination_mode == DeclinationMode.IGNORE  # I
        assert flags.apply_utm_convergence is False  # v

    def test_parse_flags_declination_entered(self):
        """Test parsing declination mode E (entered)."""
        parser = CompassProjectParser()
        directives = parser.parse_string("!gEvotscxpl;")

        assert len(directives) == 1
        flags = directives[0]
        assert isinstance(flags, FlagsDirective)
        assert flags.declination_mode == DeclinationMode.ENTERED  # E

    def test_parse_flags_preserves_raw(self):
        """Test that raw_flags is preserved for roundtrip."""
        parser = CompassProjectParser()
        directives = parser.parse_string("!gIvotscxpl;")

        assert len(directives) == 1
        flags = directives[0]
        assert flags.raw_flags == "gIvotscxpl"

    def test_parse_folder_start(self):
        """Test parsing folder start directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("[Mouse Palace;")

        assert len(directives) == 1
        assert isinstance(directives[0], FolderStartDirective)
        assert directives[0].name == "Mouse Palace"

    def test_parse_folder_end(self):
        """Test parsing folder end directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("];")

        assert len(directives) == 1
        assert isinstance(directives[0], FolderEndDirective)

    def test_parse_nested_folders(self):
        """Test parsing nested folders from documentation example."""
        parser = CompassProjectParser()
        mak_content = """[Folder-1;
  #cave1.dat;
  [Folder-2;
    #cave2.dat;
    [Folder-3;
      #cave3.dat;
      #cave4.dat;
    ];
    #cave5.dat;
  ];
  #cave6.dat;
];"""
        directives = parser.parse_string(mak_content)

        # Count directive types
        folder_starts = [d for d in directives if isinstance(d, FolderStartDirective)]
        folder_ends = [d for d in directives if isinstance(d, FolderEndDirective)]
        files = [d for d in directives if isinstance(d, FileDirective)]

        assert len(folder_starts) == 3  # Folder-1, Folder-2, Folder-3
        assert len(folder_ends) == 3  # Three closing ];
        assert len(files) == 6  # cave1.dat through cave6.dat

        # Verify folder names
        assert folder_starts[0].name == "Folder-1"
        assert folder_starts[1].name == "Folder-2"
        assert folder_starts[2].name == "Folder-3"

        # Verify file names
        assert files[0].file == "cave1.dat"
        assert files[1].file == "cave2.dat"
        assert files[2].file == "cave3.dat"
        assert files[3].file == "cave4.dat"
        assert files[4].file == "cave5.dat"
        assert files[5].file == "cave6.dat"

    def test_parse_comment(self):
        """Test parsing comment directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("/ This is a comment")

        assert len(directives) == 1
        assert isinstance(directives[0], CommentDirective)
        assert directives[0].comment == "This is a comment"

    def test_parse_simple_file(self):
        """Test parsing simple file directive."""
        parser = CompassProjectParser()
        directives = parser.parse_string("#ENTRANCE.DAT;")

        assert len(directives) == 1
        assert isinstance(directives[0], FileDirective)
        assert directives[0].file == "ENTRANCE.DAT"
        assert directives[0].link_stations == []

    def test_parse_file(self, artifacts_dir: Path):
        """Test parsing a complete MAK file."""
        parser = CompassProjectParser()
        directives = parser.parse_file(artifacts_dir / "simple.mak")

        # Check directive types
        assert any(isinstance(d, LocationDirective) for d in directives)
        assert any(isinstance(d, DatumDirective) for d in directives)
        assert any(isinstance(d, FlagsDirective) for d in directives)
        assert any(isinstance(d, FileDirective) for d in directives)

        # Check location
        locations = [d for d in directives if isinstance(d, LocationDirective)]
        assert len(locations) == 1
        assert locations[0].utm_zone == 13

        # Check files
        files = [d for d in directives if isinstance(d, FileDirective)]
        assert len(files) == 1
        assert files[0].file == "simple.dat"

    def test_parse_file_with_link_stations(self, artifacts_dir: Path):
        """Test parsing file directive with link stations."""
        parser = CompassProjectParser()
        directives = parser.parse_file(artifacts_dir / "link_stations.mak")

        assert len(directives) >= 1
        file_directive = next(
            (d for d in directives if isinstance(d, FileDirective)), None
        )
        assert file_directive is not None
        assert file_directive.file == "FULFORD.DAT"
        assert len(file_directive.link_stations) == 3

        # Check first station (feet)
        station_a = file_directive.link_stations[0]
        assert station_a.name == "A"
        assert station_a.location is not None
        assert station_a.location.unit == "f"
        assert station_a.location.easting == pytest.approx(1.1)
        assert station_a.location.northing == pytest.approx(2.2)
        assert station_a.location.elevation == pytest.approx(3.3)

        # Check second station (no location)
        station_b = file_directive.link_stations[1]
        assert station_b.name == "B"
        assert station_b.location is None

        # Check third station (meters)
        station_c = file_directive.link_stations[2]
        assert station_c.name == "C"
        assert station_c.location is not None
        assert station_c.location.unit == "m"

    def test_parse_invalid_utm_zone(self):
        """Test that invalid UTM zone raises exception."""
        parser = CompassProjectParser()

        with pytest.raises(CompassParseException, match="cannot be 0"):
            parser.parse_string("$0;")

        with pytest.raises(CompassParseException, match="UTM zone must be between"):
            parser.parse_string("$61;")

    def test_parse_unknown_directive(self):
        """Test that unknown directives are parsed leniently."""
        parser = CompassProjectParser()

        # Unknown directives are now parsed and preserved for roundtrip

        directives = parser.parse_string("Xinvalid;")
        assert len(directives) == 1
        assert isinstance(directives[0], UnknownDirective)
        assert directives[0].directive_type == "X"
        assert directives[0].content == "invalid"

    def test_parse_missing_semicolon(self):
        """Test that missing semicolon raises exception."""
        parser = CompassProjectParser()

        with pytest.raises(CompassParseException):
            parser.parse_string("$13")
