#!/usr/bin/env python

import json
import unittest
from pathlib import Path

from parameterized import parameterized
from parameterized import parameterized_class

from compass_lib.parser import CompassParser


@parameterized_class(
    ("filepath"),
    [
        ("./tests/artifacts/1998.dat",),
        ("./tests/artifacts/flags.dat",),
        ("./tests/artifacts/fulford.dat",),
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

    @parameterized.expand([True, False])
    def test_export_to_json(self, include_depth: bool = True):
        if self._parser is None:
            raise ValueError("the Compass Parser has not been setup.")

        json_str = self._parser.to_json(include_depth=include_depth)
        reloaded_json = json.loads(json_str)

        with Path(str(self._file)[:-3] + "json").open() as f:
            json_target = json.load(f)

            if not include_depth:
                # Remove all depth information
                for section in json_target["sections"]:
                    for shot in section["shots"]:
                        del shot["depth"]

        # SpeleoDB-ID is randomly generated on imports - always different.
        del reloaded_json["speleodb_id"]
        del json_target["speleodb_id"]

        with Path("converted.json").open(mode="w") as f:
            f.write(json.dumps(reloaded_json, sort_keys=True, indent=4))

        with Path("target.json").open(mode="w") as f:
            f.write(json.dumps(json_target, sort_keys=True, indent=4))

        assert reloaded_json == json_target

    # def test_export_to_dat(self):
    #     if self._parser is None:
    #         raise ValueError("the Compass Parser has not been setup.")

    #     # Save the Original Data
    #     start_data = json.loads(self._parser.to_json())

    #     with tempfile.TemporaryDirectory() as tmp_dir:

    #         target_f = Path(tmp_dir) / "export.dat"

    #         self._parser.to_dat(target_f)

    #         # Reload the exported data
    #         parser2 = CompassParser(self._file)
    #         end_data = json.loads(parser2.to_json())

    #     assert start_data == end_data


if __name__ == "__main__":
    unittest.main()
