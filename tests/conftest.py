# -*- coding: utf-8 -*-
"""Pytest configuration and fixtures.

This module provides shared fixtures for discovering and accessing test artifacts.
All test files in the private directory are automatically discovered.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =============================================================================
# Path Constants
# =============================================================================

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
PRIVATE_DIR = ARTIFACTS_DIR / "private"


# =============================================================================
# Decryption
# =============================================================================


def _decrypt_artifacts() -> None:
    if (key_str := os.environ.get("ARTIFACT_ENCRYPTION_KEY")) is None:
        return

    try:
        key_bytes = base64.urlsafe_b64decode(key_str.encode("ascii"))
        aead = AESSIV(key_bytes)
    except ValueError:
        logger.exception("Invalid AES-SIV key provided.")
        return

    for enc_f in Path("tests/artifacts/private").rglob(pattern="*.encrypted"):
        with enc_f.open(mode="rb") as f:
            enc_data = f.read()

        try:
            dec_data = aead.decrypt(enc_data, None)
        except Exception:
            logger.exception("Failed to decrypt: `%s`.", enc_f)
            continue

        with (enc_f.parent / enc_f.stem).open(mode="wb") as f:
            f.write(dec_data)


def pytest_sessionstart(session) -> None:
    _decrypt_artifacts()


# =============================================================================
# Path Fixtures
# =============================================================================


@pytest.fixture
def artifacts_dir() -> Path:
    """Return path to test artifacts directory."""
    return ARTIFACTS_DIR


@pytest.fixture
def private_dir() -> Path:
    """Return path to private test artifacts directory."""
    return PRIVATE_DIR


# =============================================================================
# File Discovery Functions (used for parametrization)
# =============================================================================


def discover_mak_files() -> list[pytest.param]:
    """Discover all MAK files in the private directory.

    Returns:
        List of pytest.param objects for use with @pytest.mark.parametrize
    """
    if not PRIVATE_DIR.exists():
        return []
    mak_files = sorted(PRIVATE_DIR.glob("*.mak"))
    return [pytest.param(mak_file, id=mak_file.stem) for mak_file in mak_files]


def discover_dat_files() -> list[pytest.param]:
    """Discover all DAT files in the private directory.

    Returns:
        List of pytest.param objects for use with @pytest.mark.parametrize
    """
    if not PRIVATE_DIR.exists():
        return []
    dat_files = sorted(PRIVATE_DIR.glob("*.dat"))
    return [pytest.param(dat_file, id=dat_file.stem) for dat_file in dat_files]


def discover_mak_json_files() -> list[pytest.param]:
    """Discover all MAK JSON baseline files in the private directory.

    Returns:
        List of pytest.param objects for use with @pytest.mark.parametrize
    """
    if not PRIVATE_DIR.exists():
        return []
    json_files = sorted(PRIVATE_DIR.glob("*.mak.json"))
    return [pytest.param(json_file, id=json_file.stem) for json_file in json_files]


def discover_dat_json_files() -> list[pytest.param]:
    """Discover all DAT JSON baseline files in the private directory.

    Returns:
        List of pytest.param objects for use with @pytest.mark.parametrize
    """
    if not PRIVATE_DIR.exists():
        return []
    json_files = sorted(PRIVATE_DIR.glob("*.dat.json"))
    return [pytest.param(json_file, id=json_file.stem) for json_file in json_files]


def discover_geojson_files() -> list[pytest.param]:
    """Discover all GeoJSON files in the private directory.

    Returns:
        List of pytest.param objects for use with @pytest.mark.parametrize
    """
    if not PRIVATE_DIR.exists():
        return []
    geojson_files = sorted(PRIVATE_DIR.glob("*.geojson"))
    return [
        pytest.param(geojson_file, id=geojson_file.stem)
        for geojson_file in geojson_files
    ]


def discover_mak_with_json_baseline() -> list[pytest.param]:
    """Discover MAK files that have corresponding JSON baselines.

    Returns:
        List of pytest.param objects with (mak_path, json_path) tuples
    """
    if not PRIVATE_DIR.exists():
        return []
    params = []
    for mak_file in sorted(PRIVATE_DIR.glob("*.mak")):
        json_file = mak_file.with_suffix(".mak.json")
        if json_file.exists():
            params.append(pytest.param(mak_file, json_file, id=mak_file.stem))
    return params


def discover_dat_with_json_baseline() -> list[pytest.param]:
    """Discover DAT files that have corresponding JSON baselines.

    Returns:
        List of pytest.param objects with (dat_path, json_path) tuples
    """
    if not PRIVATE_DIR.exists():
        return []
    params = []
    for dat_file in sorted(PRIVATE_DIR.glob("*.dat")):
        json_file = dat_file.with_suffix(".dat.json")
        if json_file.exists():
            params.append(pytest.param(dat_file, json_file, id=dat_file.stem))
    return params


def discover_mak_with_geojson() -> list[pytest.param]:
    """Discover MAK files that have corresponding GeoJSON files.

    Returns:
        List of pytest.param objects with (mak_path, geojson_path) tuples
    """
    if not PRIVATE_DIR.exists():
        return []
    params = []
    for mak_file in sorted(PRIVATE_DIR.glob("*.mak")):
        geojson_file = mak_file.with_suffix(".geojson")
        if geojson_file.exists():
            params.append(pytest.param(mak_file, geojson_file, id=mak_file.stem))
    return params


# =============================================================================
# Pre-computed Parameter Lists (for module-level parametrize decorators)
# =============================================================================

# These are computed at import time for use with @pytest.mark.parametrize
ALL_MAK_FILES = discover_mak_files()
ALL_DAT_FILES = discover_dat_files()
ALL_MAK_JSON_FILES = discover_mak_json_files()
ALL_DAT_JSON_FILES = discover_dat_json_files()
ALL_GEOJSON_FILES = discover_geojson_files()
MAK_WITH_JSON_BASELINE = discover_mak_with_json_baseline()
DAT_WITH_JSON_BASELINE = discover_dat_with_json_baseline()
MAK_WITH_GEOJSON = discover_mak_with_geojson()

# First MAK file for single-file tests (may be None if no files exist)
FIRST_MAK = PRIVATE_DIR / "project001.mak" if PRIVATE_DIR.exists() else None


# =============================================================================
# List Fixtures (for tests that need lists, not parametrization)
# =============================================================================


@pytest.fixture
def all_mak_paths() -> list[Path]:
    """Return list of all MAK file paths."""
    if not PRIVATE_DIR.exists():
        return []
    return sorted(PRIVATE_DIR.glob("*.mak"))


@pytest.fixture
def all_dat_paths() -> list[Path]:
    """Return list of all DAT file paths."""
    if not PRIVATE_DIR.exists():
        return []
    return sorted(PRIVATE_DIR.glob("*.dat"))


@pytest.fixture
def all_mak_json_paths() -> list[Path]:
    """Return list of all MAK JSON file paths."""
    if not PRIVATE_DIR.exists():
        return []
    return sorted(PRIVATE_DIR.glob("*.mak.json"))


@pytest.fixture
def all_dat_json_paths() -> list[Path]:
    """Return list of all DAT JSON file paths."""
    if not PRIVATE_DIR.exists():
        return []
    return sorted(PRIVATE_DIR.glob("*.dat.json"))


@pytest.fixture
def all_geojson_paths() -> list[Path]:
    """Return list of all GeoJSON file paths."""
    if not PRIVATE_DIR.exists():
        return []
    return sorted(PRIVATE_DIR.glob("*.geojson"))


@pytest.fixture
def first_mak_path() -> Path | None:
    """Return the first MAK file path, or None if not available."""
    return FIRST_MAK if FIRST_MAK and FIRST_MAK.exists() else None
