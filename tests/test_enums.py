import unittest
from pathlib import Path

import pytest

from compass_lib.enums import LRUD
from compass_lib.enums import AzimuthUnits
from compass_lib.enums import CompassFileType
from compass_lib.enums import InclinationUnits
from compass_lib.enums import LengthUnits
from compass_lib.enums import ShotFlag
from compass_lib.enums import ShotItem
from compass_lib.enums import StationSide


class TestCustomEnum(unittest.TestCase):
    """Tests for the CustomEnum class and its subclasses."""

    def test_reverse(self):
        """Test the reverse method for returning enum by value."""
        result = AzimuthUnits.reverse("D")
        assert result == AzimuthUnits.DEGREES

        result = InclinationUnits.reverse("G")
        assert result == InclinationUnits.PERCENT_GRADE


class TestCompassFileType(unittest.TestCase):
    """Tests for the CompassFileType enum."""

    def test_from_str(self):
        """Test from_str method for converting string to CompassFileType."""
        result = CompassFileType.from_str("DAT")
        assert result == CompassFileType.DAT

        result = CompassFileType.from_str("PLT")
        assert result == CompassFileType.PLT

        with pytest.raises(ValueError, match="Unknown value: UNKNOWN"):
            CompassFileType.from_str("unknown")

    def test_from_path(self):
        """Test from_path method for extracting CompassFileType from file path."""
        result = CompassFileType.from_path("survey.dat")
        assert result == CompassFileType.DAT

        result = CompassFileType.from_path(Path("survey.mak"))
        assert result == CompassFileType.MAK

        with pytest.raises(ValueError, match="Unknown value: FILE"):
            CompassFileType.from_path("invalid.file")


class TestAzimuthUnits(unittest.TestCase):
    """Tests for the AzimuthUnits enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert AzimuthUnits.DEGREES.value == "D"
        assert AzimuthUnits.QUADS.value == "Q"
        assert AzimuthUnits.GRADIANS.value == "G"


class TestInclinationUnits(unittest.TestCase):
    """Tests for the InclinationUnits enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert InclinationUnits.DEGREES.value == "D"
        assert InclinationUnits.PERCENT_GRADE.value == "G"
        assert InclinationUnits.DEPTH_GAUGE.value == "W"


class TestLengthUnits(unittest.TestCase):
    """Tests for the LengthUnits enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert LengthUnits.DECIMAL_FEET.value == "D"
        assert LengthUnits.METERS.value == "M"


class TestLRUD(unittest.TestCase):
    """Tests for the LRUD enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert LRUD.LEFT.value == "L"
        assert LRUD.UP.value == "U"


class TestShotItem(unittest.TestCase):
    """Tests for the ShotItem enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert ShotItem.LENGTH.value == "L"
        assert ShotItem.FRONTSIGHT_AZIMUTH.value == "A"
        assert ShotItem.BACKSIGHT_INCLINATION.value == "d"


class TestStationSide(unittest.TestCase):
    """Tests for the StationSide enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert StationSide.FROM.value == "F"
        assert StationSide.TO.value == "T"


class TestShotFlag(unittest.TestCase):
    """Tests for the ShotFlag enum."""

    def test_enum_values(self):
        """Test enum values for correctness."""
        assert ShotFlag.EXCLUDE_PLOTING.value == "P"
        assert ShotFlag.SPLAY.value == "S"


if __name__ == "__main__":
    unittest.main()
