from collections.abc import Generator
from pathlib import Path

BASE_ARTIFACTS_PATH = Path("tests/artifacts")


def get_valid_dat_artifacts() -> Generator[Path, None, None]:
    paths = BASE_ARTIFACTS_PATH.rglob(pattern="*.dat", case_sensitive=False)

    for fp in sorted(paths):
        if Path("tests/artifacts/invalid_files").resolve() in fp.resolve().parents:
            continue

        yield Path(fp)


def get_invalid_dat_artifacts() -> Generator[Path, None, None]:
    yield from sorted(
        (BASE_ARTIFACTS_PATH / "invalid_files").glob(
            pattern="*.dat", case_sensitive=False
        )
    )
