from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from compass_lib.parser import CompassParser
from tests.utils import get_valid_dat_artifacts

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _decrypt_artifacts() -> None:
    if (fernet_key := os.environ.get("ARTIFACT_ENCRYPTION_KEY")) is None:
        return

    try:
        fernet_key = Fernet(fernet_key)
    except ValueError:
        logger.exception("Invalid Fernet key provided.")
        return

    for enc_f in Path("tests/artifacts").rglob(pattern="*.encrypted"):
        with enc_f.open(mode="rb") as f:
            enc_data = f.read()

        try:
            dec_data = fernet_key.decrypt(enc_data)
        except Exception:
            logger.exception("Failed to decrypt: `%s`.", enc_f)
            continue

        with (enc_f.parent / enc_f.stem).open(mode="wb") as f:
            f.write(dec_data)


def pytest_sessionstart(session) -> None:
    _decrypt_artifacts()


def pytest_addoption(parser):
    parser.addoption(
        "--generate-json-files",
        action="store_true",
        help="Generate JSON artifacts",
        default=False,
    )


def _generate_artifacts():
    for fp in sorted(get_valid_dat_artifacts()):
        compass_file = Path(fp)
        logger.warning("\n# ------------------ `%s` ------------------ #", compass_file)

        try:
            survey = CompassParser.load_dat_file(compass_file)
            survey.to_json(filepath=compass_file.with_suffix(".json"))
        except (TypeError, ValueError, IndexError):
            logger.error("Failed to generate JSON for `%s`.", compass_file)  # noqa: TRY400
            continue


def pytest_configure(config):
    if config.getoption("--generate-json-files"):
        _decrypt_artifacts()
        _generate_artifacts()
        pytest.exit("JSON files generated, exiting pytest")
