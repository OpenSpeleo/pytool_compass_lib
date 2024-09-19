#!/usr/bin/env python

import json
import unittest
from pathlib import Path
import tempfile

from parameterized import parameterized_class

from compass_lib.parser import CompassParser


@parameterized_class(
    ("filepath"),
    [
        ("./tests/artifacts/1998.dat",),
        ("./tests/artifacts/flags.dat",),
        ("./tests/artifacts/fulford.dat",),
        ("./tests/artifacts/random.dat",),
        ("./tests/artifacts/random.dat",),
        ("./tests/artifacts/unicode.dat",)
    ]
)
class ReadCompassDATFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._file = Path(cls.filepath)
        if not cls._file.exists():
            raise FileNotFoundError(f"File not found: `{cls._file}`")

    def setUp(self) -> None:
        self._parser = CompassParser(self._file)

    def test_export_to_json(self):
        if self._parser is None:
            raise ValueError("the Compass Parser has not been setup.")

        json_str = self._parser.to_json()

        with Path(str(self._file)[:-3] + "json").open() as f:
            json_target = json.load(f)

        assert json.loads(json_str) == json_target

    def test_export_to_dat(self):
        if self._parser is None:
            raise ValueError("the Compass Parser has not been setup.")

        # Save the Original Data
        start_data = json.loads(self._parser.to_json())

        with tempfile.TemporaryDirectory() as tmp_dir:

            target_f = Path(tmp_dir) / "export.dat"

            self._parser.to_dat(target_f)

            # Reload the exported data
            parser2 = CompassParser(self._file)
            end_data = json.loads(parser2.to_json())

        assert start_data == end_data


if __name__ == "__main__":
    unittest.main()
