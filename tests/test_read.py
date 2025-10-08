from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import orjson
from deepdiff import DeepDiff
from parameterized import parameterized_class

from compass_lib.parser import CompassParser
from tests.utils import get_valid_dat_artifacts


@parameterized_class(
    ("filepath"),
    [(p,) for p in get_valid_dat_artifacts()],
    # [
    #     ("./tests/artifacts/1998.dat",),
    #     ("./tests/artifacts/flags.dat",),
    #     ("./tests/artifacts/fulford.dat",),
    #     ("./tests/artifacts/fulsurf.dat",),
    #     ("./tests/artifacts/random.dat",),
    #     ("./tests/artifacts/unicode.dat",),
    # ],
)
class ReadCompassDATFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._file = Path(cls.filepath)
        if not cls._file.exists():
            raise FileNotFoundError(f"File not found: `{cls._file}`")

    def setUp(self) -> None:
        self._survey = CompassParser.load_dat_file(self._file)

    def test_export_to_json(self):
        json_str = self._survey.to_json()
        reloaded_json = json.loads(json_str)

        with self._file.with_suffix(".json").open() as f:
            json_target = json.load(f)

        with Path("converted.json").open(mode="w") as f:
            f.write(
                orjson.dumps(
                    reloaded_json,
                    None,
                    option=(orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS),
                ).decode("utf-8")
            )

        with Path("target.json").open(mode="w") as f:
            f.write(
                orjson.dumps(
                    json_target,
                    None,
                    option=(orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS),
                ).decode("utf-8")
            )

        diff = DeepDiff(reloaded_json, json_target, ignore_order=True)
        assert diff == {}, f"Identity Check failed: {diff}"

    def test_compass_roundtrip(self):
        json_str = self._survey.to_json()
        original_json = json.loads(json_str)

        with tempfile.TemporaryDirectory() as tmpdir:
            dat_file = Path(tmpdir) / "export.dat"
            CompassParser.export_to_dat(self._survey, dat_file)

            survey = CompassParser.load_dat_file(dat_file)
            roundtrip_json = json.loads(survey.to_json())

        diff = DeepDiff(original_json, roundtrip_json, ignore_order=True)
        assert diff == {}, f"Identity Check failed: {diff}"

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
