import unittest

import pytest

from compass_lib.parser import CompassParser


class TestCompassParser(unittest.TestCase):
    """Unit tests for CompassParser."""

    def test_file_doesnt_exist(self):
        """Test JSON encoding for a dataclass instance."""
        with pytest.raises(FileNotFoundError):
            _ = CompassParser.load_dat_file(filepath="doesnotexists.dat")


if __name__ == "__main__":
    unittest.main()
