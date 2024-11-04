#!/usr/bin/env python

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

from parameterized import parameterized_class


class CMDUnittest(unittest.TestCase):
    command_template = (
        "compass convert --input_file={input_f} --output_file={output_f} "
        "--format=json {extra}"
    )


@parameterized_class(
    ("input_file"),
    [
        ("./tests/artifacts/random.dat",),
        ("./tests/artifacts/fulford.dat",)
    ]
)
class ConvertCMDTest(CMDUnittest):

    @classmethod
    def setUpClass(cls):
        cls._file = Path(cls.input_file)
        if not cls._file.exists():
            raise FileNotFoundError(f"File not found: `{cls._file}`")

        cls._temp_dir_ctx = tempfile.TemporaryDirectory()
        cls._temp_dir = Path(cls._temp_dir_ctx.__enter__())

    @classmethod
    def tearDownClass(cls):
        cls._temp_dir_ctx.__exit__(None, None, None)

    def _get_cmd(self, extra=""):
        return self.command_template.format(
            input_f=self._file,
            output_f=self._temp_dir / "aaa.json",
            extra=extra
        ).strip()

    def test_1_convert(self):
        cmd = self._get_cmd()
        result = subprocess.run(
            shlex.split(cmd),  # noqa: S603
            stdout=subprocess.DEVNULL,
            check=False
        )
        assert result.returncode == 0

    def test_2_no_overwrite_failure(self):
        cmd = self._get_cmd()
        result = subprocess.run(
            shlex.split(cmd),  # noqa: S603
            stdout=subprocess.DEVNULL,
            check=False
        )
        assert result.returncode == 1

    def test_3_overwrite_success(self):
        cmd = self._get_cmd(extra="--overwrite")
        result = subprocess.run(
            shlex.split(cmd),  # noqa: S603
            stdout=subprocess.DEVNULL,
            check=False
        )
        assert result.returncode == 0


class ConvertCMDFileNotExistsTest(CMDUnittest):
    def test_convert(self):
        cmd = self.command_template.format(
            input_f="1223443255",
            output_f="out.json",
            extra=""
        )
        result = subprocess.run(
            shlex.split(cmd),  # noqa: S603
            stdout=subprocess.DEVNULL,
            check=False
        )
        assert result.returncode == 1

if __name__ == "__main__":
    unittest.main()
