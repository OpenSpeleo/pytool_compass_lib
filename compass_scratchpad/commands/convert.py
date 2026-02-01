# -*- coding: utf-8 -*-
"""Convert command for Compass files.

Supports bidirectional conversion between Compass native formats (DAT, MAK)
and JSON format using Pydantic's built-in serialization.
"""

import argparse
import json
import sys
from pathlib import Path

from compass_scratchpad.constants import COMPASS_ENCODING
from compass_scratchpad.constants import EXT_DAT
from compass_scratchpad.constants import EXT_JSON
from compass_scratchpad.constants import EXT_MAK
from compass_scratchpad.constants import FORMAT_COMPASS_DAT
from compass_scratchpad.constants import FORMAT_COMPASS_MAK
from compass_scratchpad.constants import FORMAT_COMPASS_PROJECT
from compass_scratchpad.constants import JSON_ENCODING
from compass_scratchpad.enums import CompassFileType
from compass_scratchpad.enums import FileFormat
from compass_scratchpad.io import load_project
from compass_scratchpad.io import read_dat_file
from compass_scratchpad.project.format import format_mak_file
from compass_scratchpad.project.models import CompassMakFile
from compass_scratchpad.survey.format import format_dat_file
from compass_scratchpad.survey.models import CompassDatFile


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
    suffix = path.suffix.lower()

    if suffix == EXT_DAT:
        return (FileFormat.COMPASS, CompassFileType.DAT)
    if suffix == EXT_MAK:
        return (FileFormat.COMPASS, CompassFileType.MAK)
    if suffix == EXT_JSON:
        # Read the file to detect format from content
        try:
            content = path.read_text(encoding=JSON_ENCODING)
            if (
                f'"format": "{FORMAT_COMPASS_DAT}"' in content
                or f'"format":"{FORMAT_COMPASS_DAT}"' in content
            ):
                return (FileFormat.JSON, CompassFileType.DAT)
            if (
                f'"format": "{FORMAT_COMPASS_MAK}"' in content
                or f'"format":"{FORMAT_COMPASS_MAK}"' in content
                or f'"format": "{FORMAT_COMPASS_PROJECT}"' in content
                or f'"format":"{FORMAT_COMPASS_PROJECT}"' in content
            ):
                return (FileFormat.JSON, CompassFileType.MAK)
        except Exception:
            pass
        return (FileFormat.JSON, None)

    return (FileFormat.COMPASS, None)


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
            trips = read_dat_file(input_path)
            dat_file = CompassDatFile(trips=trips)
            # Wrap in format envelope for DAT files
            envelope = {
                "version": "1.0",
                "format": FORMAT_COMPASS_DAT,
                "trips": json.loads(dat_file.model_dump_json(by_alias=True))["trips"],
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
            trips_data = data.get("trips", [])
            dat_file = CompassDatFile.model_validate({"trips": trips_data})
            result = format_dat_file(dat_file.trips) or ""
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
            print(result, end="")

        # Print status to stderr if writing to file
        if parsed_args.output_file is not None:
            source_format, file_type = detect_file_format(parsed_args.input_file)
            target_format = (
                FileFormat(parsed_args.target_format)
                if parsed_args.target_format
                else (
                    FileFormat.JSON
                    if source_format == FileFormat.COMPASS
                    else FileFormat.COMPASS
                )
            )
            print(
                f"Converted {parsed_args.input_file} ({source_format.value}) -> "
                f"{parsed_args.output_file} ({target_format.value})",
                file=sys.stderr,
            )

        return 0

    except ConversionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
