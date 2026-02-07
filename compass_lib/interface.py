# -*- coding: utf-8 -*-
"""Unified interface for Compass file I/O.

This module provides the primary entry point for reading and writing
Compass files. It follows the openspeleo_lib pattern:

1. Parsers produce dictionaries (like loading JSON from disk)
2. Dictionaries feed directly to Pydantic models via `model_validate()`
3. Models serialize to dictionaries via `model_dump()`
4. Formatters convert dictionaries to file content

This keeps parsing/formatting logic completely separate from Pydantic models.
"""

from pathlib import Path
from typing import Any
from typing import Protocol

from compass_lib.constants import COMPASS_ENCODING
from compass_lib.constants import JSON_ENCODING
from compass_lib.project.format import format_mak_file
from compass_lib.project.models import CompassMakFile
from compass_lib.project.parser import CompassProjectParser
from compass_lib.survey.format import format_dat_file
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.parser import CompassSurveyParser

# Re-export for backwards compatibility
DEFAULT_ENCODING = COMPASS_ENCODING


class ProgressCallback(Protocol):
    """Protocol for progress callbacks."""

    def __call__(
        self,
        message: str | None = None,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        """Report progress."""
        ...


class CancellationToken:
    """Token for checking if an operation should be cancelled."""

    def __init__(self) -> None:
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True


class CompassInterface:
    """Unified interface for Compass file I/O.

    This class provides all file I/O operations for Compass files,
    following the pattern:
    - Reading: File → Parser → Dictionary → model_validate() → Model
    - Writing: Model → model_dump() → Dictionary → Formatter → File

    Example:
        # Load a complete project
        project = CompassInterface.load_project(Path("cave.mak"))

        # Access nested data
        for file_dir in project.file_directives:
            if file_dir.data:
                for survey in file_dir.data.surveys:
                    print(survey.header.survey_name)

        # Save to JSON
        CompassInterface.save_json(project, Path("cave.json"))
    """

    # -------------------------------------------------------------------------
    # Loading Methods (File → Model)
    # -------------------------------------------------------------------------

    @classmethod
    def load_project(
        cls,
        mak_path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
        on_progress: ProgressCallback | None = None,
        cancellation: CancellationToken | None = None,
    ) -> CompassMakFile:
        """Load a complete Compass project (MAK + all DAT files).

        This is the main entry point for loading Compass projects. It:
        1. Parses the MAK file to dictionary
        2. Parses each referenced DAT file to dictionary
        3. Nests DAT dictionaries into file directives
        4. Validates entire structure with single model_validate() call

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
        if on_progress:
            on_progress(message=f"Reading {mak_path}")

        # Parse MAK file to dictionary
        mak_parser = CompassProjectParser()
        with mak_path.open(encoding=encoding, errors="replace") as f:
            mak_content = f.read()
        mak_data = mak_parser.parse_string_to_dict(mak_content, str(mak_path))

        if cancellation and cancellation.cancelled:
            raise InterruptedError("Operation cancelled")

        # Calculate total size for progress
        mak_dir = mak_path.parent
        total_size = 0
        dat_files: list[tuple[dict[str, Any], Path]] = []

        for directive in mak_data.get("directives", []):
            if directive.get("type") == "file":
                dat_path = mak_dir / directive["file"]
                if dat_path.exists():
                    total_size += dat_path.stat().st_size
                    dat_files.append((directive, dat_path))

        # Parse each DAT file and attach to directive dictionary
        completed = 0
        dat_parser = CompassSurveyParser()

        for directive, dat_path in dat_files:
            if cancellation and cancellation.cancelled:
                raise InterruptedError("Operation cancelled")

            if on_progress:
                on_progress(
                    message=f"Reading {dat_path.name}",
                    completed=completed,
                    total=total_size,
                )

            # Parse DAT file to dictionary and attach
            with dat_path.open(encoding=encoding, errors="replace") as f:
                dat_content = f.read()
            dat_data = dat_parser.parse_string_to_dict(dat_content, str(dat_path))
            directive["data"] = dat_data

            completed += dat_path.stat().st_size
            if on_progress:
                on_progress(completed=completed, total=total_size)

        # Single model_validate() call for entire structure
        return CompassMakFile.model_validate(mak_data)

    @classmethod
    def load_dat(
        cls,
        path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
    ) -> CompassDatFile:
        """Load a single DAT file.

        Args:
            path: Path to the .DAT file
            encoding: Character encoding

        Returns:
            CompassDatFile with all surveys
        """
        parser = CompassSurveyParser()
        with path.open(encoding=encoding, errors="replace") as f:
            content = f.read()
        data = parser.parse_string_to_dict(content, str(path))

        # Single model_validate() call
        return CompassDatFile.model_validate(data)

    @classmethod
    def load_mak(
        cls,
        path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
    ) -> CompassMakFile:
        """Load a MAK file without loading DAT files.

        Args:
            path: Path to the .MAK file
            encoding: Character encoding

        Returns:
            CompassMakFile with directives only (no DAT data)
        """
        parser = CompassProjectParser()
        with path.open(encoding=encoding, errors="replace") as f:
            content = f.read()
        data = parser.parse_string_to_dict(content, str(path))

        # Single model_validate() call
        return CompassMakFile.model_validate(data)

    # -------------------------------------------------------------------------
    # Saving Methods (Model → File)
    # -------------------------------------------------------------------------

    @classmethod
    def save_project(
        cls,
        project: CompassMakFile,
        mak_path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
        save_dat_files: bool = True,
    ) -> None:
        """Save a complete Compass project (MAK + all DAT files).

        Args:
            project: The project to save
            mak_path: Path to write the .MAK file
            encoding: Character encoding (default: Windows-1252)
            save_dat_files: Whether to also save DAT files (default: True)
        """
        # Save MAK file
        cls.save_mak(project, mak_path, encoding=encoding)

        # Optionally save DAT files
        if save_dat_files:
            mak_dir = mak_path.parent
            for file_dir in project.file_directives:
                if file_dir.data:
                    dat_path = mak_dir / file_dir.file
                    cls.save_dat(file_dir.data, dat_path, encoding=encoding)

    @classmethod
    def save_mak(
        cls,
        project: CompassMakFile,
        path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:
        """Save a MAK file.

        Args:
            project: The project to save
            path: Path to write to
            encoding: Character encoding
        """
        content = format_mak_file(project.directives)
        with path.open(mode="w", encoding=encoding, newline="") as f:
            f.write(content or "")

    @classmethod
    def save_dat(
        cls,
        dat_file: CompassDatFile,
        path: Path,
        *,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:
        """Save a DAT file.

        Args:
            dat_file: The DAT file to save
            path: Path to write to
            encoding: Character encoding
        """
        content = format_dat_file(dat_file.surveys)
        with path.open(mode="w", encoding=encoding, newline="") as f:
            f.write(content or "")

    # -------------------------------------------------------------------------
    # JSON Methods
    # -------------------------------------------------------------------------

    @classmethod
    def save_json(
        cls,
        model: CompassMakFile | CompassDatFile,
        path: Path,
    ) -> None:
        """Save a model as JSON.

        Uses Pydantic's built-in serialization.

        Args:
            model: Project or DAT file to serialize
            path: Path to write JSON file
        """
        json_str = model.model_dump_json(indent=2, by_alias=True)
        path.write_text(json_str, encoding=JSON_ENCODING)

    @classmethod
    def load_project_json(cls, path: Path) -> CompassMakFile:
        """Load a project from JSON.

        Args:
            path: Path to JSON file

        Returns:
            Deserialized project
        """
        json_str = path.read_text(encoding=JSON_ENCODING)
        return CompassMakFile.model_validate_json(json_str)

    @classmethod
    def load_dat_json(cls, path: Path) -> CompassDatFile:
        """Load a DAT file from JSON.

        Args:
            path: Path to JSON file

        Returns:
            Deserialized DAT file
        """
        json_str = path.read_text(encoding=JSON_ENCODING)
        return CompassDatFile.model_validate_json(json_str)
