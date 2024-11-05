import os
import unittest
from datetime import datetime

import pytest

from compass_lib.parser import CompassParser


class TestCompassParser(unittest.TestCase):
    """Unit tests for CompassParser."""

    def test_file_doesnt_exist(self):
        """Test JSON encoding for a dataclass instance."""
        with pytest.raises(FileNotFoundError):
            _ = CompassParser(filepath="doesnotexists.dat")

    def test_repr(self):
        filepath = "tests/artifacts/1998.dat"
        parser = CompassParser(filepath=filepath)
        repr_str = repr(parser)
        assert repr_str == f"[CompassSurveyFile DAT] `{filepath}`:"

    def test_hash(self):
        parser = CompassParser(filepath="tests/artifacts/1998.dat")
        assert hash(parser) == 1669966191239739783  # noqa: PLR2004

    def test_lstat(self):
        parser = CompassParser(filepath="tests/artifacts/1998.dat")
        stat_result = parser.lstat
        assert isinstance(stat_result, os.stat_result)
        assert stat_result.st_size == 12581  # noqa: PLR2004

        assert stat_result.st_atime == 1728369155.5372071  # noqa: PLR2004
        assert parser.date_last_opened == datetime.fromtimestamp(1728369155.5372071)  # noqa: DTZ006  # 2024/10/08

        assert stat_result.st_mtime == 1728369154.7030082  # noqa: PLR2004
        assert parser.date_last_modified == datetime.fromtimestamp(1728369154.7030082)  # noqa: DTZ006  # 2024/10/08

        assert stat_result.st_ctime == 1728369154.7030082  # noqa: PLR2004
        assert parser.date_created == datetime.fromtimestamp(1728369154.7030082)  # noqa: DTZ006  # 2024/10/08


if __name__ == "__main__":
    unittest.main()
