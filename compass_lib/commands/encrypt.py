from __future__ import annotations

import argparse
import base64
import logging
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def encrypt(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="compass encrypt")

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
        "-e",
        "--env_file",
        type=str,
        default=None,
        required=True,
        help="Path of the environment file containing the AES-SIV key.",
    )

    parser.add_argument(
        "-w",
        "--overwrite",
        action="store_true",
        help="Allow overwrite an already existing file.",
        default=False,
    )

    parsed_args = parser.parse_args(args)

    if not (input_file := Path(parsed_args.input_file)).exists():
        raise FileNotFoundError(f"Impossible to find: `{input_file}`.")

    if (
        output_file := Path(parsed_args.output_file)
    ).exists() and not parsed_args.overwrite:
        raise FileExistsError(
            f"The file {output_file} already existing. "
            "Please pass the flag `--overwrite` to ignore."
        )

    if not (envfile := Path(parsed_args.env_file)).exists():
        raise FileNotFoundError(f"Impossible to find: `{envfile}`.")
    load_dotenv(envfile, verbose=True, override=True)
    logger.info("Loaded environment variables from: `%s`", envfile)

    if (key_str := os.getenv("ARTIFACT_ENCRYPTION_KEY")) is None:
        raise ValueError(
            "No AES-SIV key found in the environment file. "
            "Check if `ARTIFACT_ENCRYPTION_KEY` is set."
        )

    key_bytes = base64.urlsafe_b64decode(key_str.encode("ascii"))
    aead = AESSIV(key_bytes)

    with input_file.open("rb") as f:
        clear_data = f.read()

    with output_file.open("wb") as f:
        f.write(aead.encrypt(clear_data, None))

    # Round Trip Check:
    with output_file.open("rb") as f:
        roundtrip_data = aead.decrypt(f.read(), None)
        assert clear_data == roundtrip_data

    return 0
