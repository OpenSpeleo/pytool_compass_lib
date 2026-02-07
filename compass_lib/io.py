# -*- coding: utf-8 -*-
"""File I/O operations for Compass files.

This module provides backwards-compatible wrappers around CompassInterface.

For new code, prefer using CompassInterface directly:

    from compass_lib.interface import CompassInterface

    project = CompassInterface.load_project(Path("cave.mak"))
    CompassInterface.save_json(project, Path("cave.json"))

The functions in this module are thin wrappers maintained for API stability.
"""

from pathlib import Path

from compass_lib.interface import DEFAULT_ENCODING
from compass_lib.interface import CancellationToken
from compass_lib.interface import CompassInterface
from compass_lib.interface import ProgressCallback
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import CompassProjectDirective
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassSurvey

# Re-export for API compatibility
__all__ = [
    "DEFAULT_ENCODING",
    "CancellationToken",
    "ProgressCallback",
    "load_dat_json",
    "load_project",
    "load_project_json",
    "read_dat_file",
    "read_mak_and_dat_files",
    "read_mak_file",
    "save_dat_json",
    "save_project",
    "save_project_json",
    "write_dat_file",
    "write_mak_file",
]


# --- Reading Functions ---


def read_dat_file(
    path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
) -> list[CompassSurvey]:
    """Read a Compass .DAT survey file.

    Args:
        path: Path to the .DAT file
        encoding: Character encoding (default: Windows-1252)

    Returns:
        List of parsed surveys
    """
    dat_file = CompassInterface.load_dat(path, encoding=encoding)
    return dat_file.surveys


def read_mak_file(
    path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
) -> list[CompassProjectDirective]:
    """Read a Compass .MAK project file (directives only).

    This function reads only the MAK file and does not load referenced
    DAT files. Use `load_project()` to load the complete project with
    all DAT file data.

    Args:
        path: Path to the .MAK file
        encoding: Character encoding (default: Windows-1252)

    Returns:
        List of parsed directives
    """
    mak_file = CompassInterface.load_mak(path, encoding=encoding)
    return mak_file.directives


def load_project(
    mak_path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
    on_progress: ProgressCallback | None = None,
    cancellation: CancellationToken | None = None,
) -> CompassMakFile:
    """Load a complete Compass project (MAK + all DAT files).

    This is the main entry point for loading Compass projects.

    Args:
        mak_path: Path to the .MAK file
        encoding: Character encoding (default: Windows-1252)
        on_progress: Optional progress callback
        cancellation: Optional cancellation token

    Returns:
        CompassMakFile with all DAT data loaded

    Raises:
        InterruptedError: If cancellation was requested
        FileNotFoundError: If MAK file doesn't exist
    """
    return CompassInterface.load_project(
        mak_path,
        encoding=encoding,
        on_progress=on_progress,
        cancellation=cancellation,
    )


def read_mak_and_dat_files(
    mak_path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
    on_progress: ProgressCallback | None = None,
    cancellation: CancellationToken | None = None,
) -> list[CompassProjectDirective]:
    """Read a Compass .MAK project file and all linked .DAT files.

    Note: This function returns a list of directives for backwards compatibility.
    For new code, use `load_project()` which returns a `CompassMakFile` object.

    Args:
        mak_path: Path to the .MAK file
        encoding: Character encoding (default: Windows-1252)
        on_progress: Optional progress callback
        cancellation: Optional cancellation token

    Returns:
        List of parsed directives with attached DAT file data

    Raises:
        InterruptedError: If cancellation was requested
    """
    mak_file = load_project(
        mak_path,
        encoding=encoding,
        on_progress=on_progress,
        cancellation=cancellation,
    )
    return mak_file.directives


# --- Writing Functions ---


def write_dat_file(
    path: Path,
    surveys: list[CompassSurvey],
    *,
    encoding: str = DEFAULT_ENCODING,
) -> None:
    """Write a Compass .DAT survey file.

    Args:
        path: Path to write to
        surveys: List of surveys to write
        encoding: Character encoding (default: Windows-1252)
    """
    dat_file = CompassDatFile(surveys=surveys)
    CompassInterface.save_dat(dat_file, path, encoding=encoding)


def write_mak_file(
    path: Path,
    directives: list[CompassProjectDirective],
    *,
    encoding: str = DEFAULT_ENCODING,
) -> None:
    """Write a Compass .MAK project file.

    Args:
        path: Path to write to
        directives: List of directives to write
        encoding: Character encoding (default: Windows-1252)
    """
    project = CompassMakFile(directives=directives)
    CompassInterface.save_mak(project, path, encoding=encoding)


def save_project(
    mak_path: Path,
    project: CompassMakFile,
    *,
    encoding: str = DEFAULT_ENCODING,
    save_dat_files: bool = True,
) -> None:
    """Save a complete Compass project (MAK + all DAT files).

    Args:
        mak_path: Path to write the .MAK file
        project: The project to save
        encoding: Character encoding (default: Windows-1252)
        save_dat_files: Whether to also save DAT files (default: True)
    """
    CompassInterface.save_project(
        project,
        mak_path,
        encoding=encoding,
        save_dat_files=save_dat_files,
    )


# --- JSON I/O Functions ---


def save_project_json(path: Path, project: CompassMakFile) -> None:
    """Save a project as JSON.

    Args:
        path: Path to write JSON file
        project: Project to serialize
    """
    CompassInterface.save_json(project, path)


def load_project_json(path: Path) -> CompassMakFile:
    """Load a project from JSON.

    Args:
        path: Path to JSON file

    Returns:
        Deserialized project
    """
    return CompassInterface.load_project_json(path)


def save_dat_json(path: Path, dat_file: CompassDatFile) -> None:
    """Save a DAT file as JSON."""
    CompassInterface.save_json(dat_file, path)


def load_dat_json(path: Path) -> CompassDatFile:
    """Load a DAT file from JSON."""
    return CompassInterface.load_dat_json(path)
