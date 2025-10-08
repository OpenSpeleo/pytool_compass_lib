from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Iterator

BASE_ARTIFACTS_PATH = Path("tests/artifacts")


def compass_files_rglob(dirpath: Path) -> Iterator[Path]:
    if sys.version_info >= (3, 12):
        yield from dirpath.rglob(pattern="*.dat", case_sensitive=False)

    yield from dirpath.rglob(pattern="*.dat")
    yield from dirpath.rglob(pattern="*.DAT")


def get_valid_dat_artifacts() -> Generator[Path, None, None]:
    for fp in sorted(compass_files_rglob(BASE_ARTIFACTS_PATH)):
        if Path("tests/artifacts/invalid_files").resolve() in fp.resolve().parents:
            continue

        yield Path(fp)


def get_invalid_dat_artifacts() -> Generator[Path, None, None]:
    yield from sorted(compass_files_rglob(BASE_ARTIFACTS_PATH / "invalid_files"))
