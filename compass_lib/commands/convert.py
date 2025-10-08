from __future__ import annotations

import argparse
from pathlib import Path

from compass_lib.parser import CompassParser


def convert(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="compass convert")

    parser.add_argument(
        "-i",
        "--input_file",
        type=str,
        default=None,
        required=True,
        help="Compass Survey Source File.",
    )

    parser.add_argument(
        "-o",
        "--output_file",
        type=str,
        default=None,
        required=True,
        help="Path to save the converted file at.",
    )

    parser.add_argument(
        "-w",
        "--overwrite",
        action="store_true",
        help="Allow overwrite an already existing file.",
        default=False,
    )

    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=["json"],
        required=True,
        help="Conversion format used.",
    )

    parsed_args = parser.parse_args(args)

    dmp_file = Path(parsed_args.input_file)
    if not dmp_file.exists():
        raise FileNotFoundError(f"Impossible to find: `{dmp_file}`.")

    output_file = Path(parsed_args.output_file)
    if output_file.exists() and not parsed_args.overwrite:
        raise FileExistsError(
            f"The file {output_file} already existing. "
            "Please pass the flag `--overwrite` to ignore."
        )

    survey = CompassParser.load_dat_file(dmp_file)
    survey.to_json(filepath=output_file)
    return 0
