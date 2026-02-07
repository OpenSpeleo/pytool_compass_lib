# -*- coding: utf-8 -*-
"""Convert command for Compass files.

Supports bidirectional conversion between Compass native formats (DAT, MAK)
and JSON format using Pydantic's built-in serialization.
"""

import argparse
import json
from pathlib import Path

from compass_lib.constants import COMPASS_ENCODING
from compass_lib.constants import JSON_ENCODING
from compass_lib.enums import CompassFileType
from compass_lib.enums import FileExtension
from compass_lib.enums import FileFormat
from compass_lib.enums import FormatIdentifier
from compass_lib.io import load_project
from compass_lib.io import read_dat_file
from compass_lib.project.format import format_mak_file
from compass_lib.project.models import CompassMakFile
from compass_lib.survey.format import format_dat_file
from compass_lib.survey.models import CompassDatFile


class ConversionError(Exception):
    """Error raised for invalid conversion operations."""


def detect_file_format(
    path: Path,
) -> tuple[FileFormat, CompassFileType | None]:
    """Detect the file format and type based on extension and content.

    Args:
        path: File path

    Returns:
        Tuple of (format_type, file_type) where:
        - format_type: FileFormat.COMPASS or FileFormat.JSON
        - file_type: CompassFileType.DAT or CompassFileType.MAK (or None)
    """

    match f_ext := path.suffix.lower():
        case FileExtension.DAT.value:
            return (FileFormat.COMPASS, CompassFileType.DAT)

        case FileExtension.MAK.value:
            return (FileFormat.COMPASS, CompassFileType.MAK)

        case FileExtension.JSON.value:
            # Read the file to detect format from content
            content = path.read_text(encoding=JSON_ENCODING)
            if (
                f'"format": "{FormatIdentifier.COMPASS_DAT.value}"' in content
                or f'"format":"{FormatIdentifier.COMPASS_DAT.value}"' in content
            ):
                return (FileFormat.JSON, CompassFileType.DAT)

            if (
                f'"format": "{FormatIdentifier.COMPASS_MAK.value}"' in content
                or f'"format":"{FormatIdentifier.COMPASS_MAK.value}"' in content
            ):
                return (FileFormat.JSON, CompassFileType.MAK)

            raise ValueError(f"Unknown file type found inside json: `{f_ext}`")

        case _:
            raise ValueError(f"Unknown file extension: `{f_ext}`")


def _convert(
    input_path: Path,
    output_path: Path | None = None,
    target_format: FileFormat | str | None = None,
) -> str | None:
    """Convert a file between formats.

    Args:
        input_path: Input file path
        output_path: Output file path (None = return as string)
        target_format: Target format (FileFormat or string 'compass'/'json')

    Returns:
        Converted content as string if output_path is None,
        otherwise None (writes to file)

    Raises:
        ConversionError: If conversion is not valid
        FileNotFoundError: If input file doesn't exist
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Detect source format
    source_format, file_type = detect_file_format(input_path)

    if file_type is None:
        raise ConversionError(f"Cannot determine file type for: {input_path}")

    # Normalize target format to enum
    if isinstance(target_format, str):
        target_format = FileFormat(target_format)
    elif target_format is None:
        # Auto-determine: opposite of source
        target_format = (
            FileFormat.JSON
            if source_format == FileFormat.COMPASS
            else FileFormat.COMPASS
        )

    # Validate: no same-format conversion
    if source_format == target_format:
        raise ConversionError(
            f"Invalid conversion: {source_format.value} => {target_format.value}. "
            f"Source and target formats must be different."
        )

    # Perform conversion
    if source_format == FileFormat.COMPASS and target_format == FileFormat.JSON:
        # Compass -> JSON using Pydantic
        if file_type == CompassFileType.DAT:
            surveys = read_dat_file(input_path)
            dat_file = CompassDatFile(surveys=surveys)
            # Wrap in format envelope for DAT files
            envelope = {
                "version": "1.0",
                "format": FormatIdentifier.COMPASS_DAT.value,
                "surveys": json.loads(dat_file.model_dump_json(by_alias=True))[
                    "surveys"
                ],
            }
            result = json.dumps(envelope, indent=2, sort_keys=True)
        else:  # mak
            project = load_project(input_path)
            result = project.model_dump_json(indent=2, by_alias=True)

    elif source_format == FileFormat.JSON and target_format == FileFormat.COMPASS:
        # JSON -> Compass using Pydantic
        json_str = input_path.read_text(encoding=JSON_ENCODING)
        if file_type == CompassFileType.DAT:
            data = json.loads(json_str)
            # Handle both envelope format and raw format
            surveys_data = data.get("surveys", [])
            dat_file = CompassDatFile.model_validate({"surveys": surveys_data})
            result = format_dat_file(dat_file.surveys) or ""
        else:  # mak
            project = CompassMakFile.model_validate_json(json_str)
            result = format_mak_file(project.directives) or ""

    else:
        raise ConversionError(
            f"Unsupported conversion: {source_format.value} => {target_format.value}"
        )

    # Output handling
    if output_path is None:
        return result

    # Write to file
    if target_format == FileFormat.JSON:
        output_path.write_text(result, encoding=JSON_ENCODING)
    else:
        # Compass format uses Windows-1252
        output_path.write_text(result, encoding=COMPASS_ENCODING, errors="replace")

    return None


def convert(args: list[str]) -> int:
    """Entry point for the convert command."""
    parser = argparse.ArgumentParser(
        prog="compass convert",
        description="Convert Compass files between native and JSON formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  compass convert -i survey.DAT                     # Convert to JSON (stdout)
  compass convert -i survey.DAT -o survey.json      # Convert to JSON file
  compass convert -i project.MAK -f json            # Convert to JSON (stdout)
  compass convert -i survey.json -o survey.DAT      # Convert to Compass format
  compass convert -i survey.json -f compass         # Convert to Compass (stdout)

Supported conversions:
  compass -> json    Survey/project data to JSON
  json -> compass    JSON to survey/project data

Notes:
  - File type (DAT/MAK) is auto-detected from extension or JSON content
  - Target format is auto-detected if not specified (opposite of source)
  - Cannot convert compass -> compass or json -> json
""",
    )

    parser.add_argument(
        "-i",
        "--input-file",
        type=Path,
        required=True,
        help="Input file path (.DAT, .MAK, or .json)",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        type=Path,
        default=None,
        help="Output file path (prints to stdout if not specified)",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=[FileFormat.COMPASS.value, FileFormat.JSON.value],
        default=None,
        dest="target_format",
        help="Target format: 'compass' or 'json' (auto-detected if not specified)",
    )

    parsed_args = parser.parse_args(args)

    try:
        result = _convert(
            input_path=parsed_args.input_file,
            output_path=parsed_args.output_file,
            target_format=parsed_args.target_format,
        )

        if result is not None:
            # Print to stdout
            pass

        # Print status to stderr if writing to file
        if parsed_args.output_file is not None:
            source_format, _file_type = detect_file_format(parsed_args.input_file)
            (
                FileFormat(parsed_args.target_format)
                if parsed_args.target_format
                else (
                    FileFormat.JSON
                    if source_format == FileFormat.COMPASS
                    else FileFormat.COMPASS
                )
            )

    except ConversionError:
        return 1
    except FileNotFoundError:
        return 1
    except Exception:  # noqa: BLE001
        return 1

    return 0
