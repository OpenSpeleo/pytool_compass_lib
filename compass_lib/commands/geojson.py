# -*- coding: utf-8 -*-
"""GeoJSON export command for Compass files.

This command converts Compass MAK+DAT files to GeoJSON format,
computing station coordinates from the survey data.
"""

import argparse
import logging
from pathlib import Path

from cave_closure import LoopClosureAlgorithm
from cave_closure import LoopClosureMode

from compass_lib.enums import FileExtension
from compass_lib.geojson import convert_mak_to_geojson
from compass_lib.loop_closure import LoopClosure

logger = logging.getLogger(__name__)


def geojson(args: list[str]) -> int:
    """Entry point for the geojson command."""
    parser = argparse.ArgumentParser(
        prog="compass geojson",
        description="Convert Compass MAK+DAT files to GeoJSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  compass geojson -i project.MAK                    # Output to stdout
  compass geojson -i project.MAK -o cave.geojson    # Output to file
  compass geojson -i project.MAK --no-stations      # Only survey legs
  compass geojson -i project.MAK --passages         # Include passage polygons

Output:
  The GeoJSON FeatureCollection includes:
  - Point features for survey stations
  - LineString features for survey legs (shots)
  - Polygon features for passage outlines (optional, from LRUD data)

  Coordinates are in UTM meters, with the CRS specified in the output
  if the MAK file contains UTM zone information.

Notes:
  - Station coordinates are computed by traversing shots from fixed points
  - Fixed points come from link stations with coordinates or project location
  - If no fixed points exist, the first station is placed at origin (0,0,0)
  - All coordinates are converted to meters
""",
    )

    parser.add_argument(
        "-i",
        "--input-file",
        type=Path,
        required=True,
        help="Input MAK file path",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        type=Path,
        default=None,
        help="Output GeoJSON file path (prints to stdout if not specified)",
    )
    parser.add_argument(
        "--no-stations",
        action="store_true",
        help="Exclude station point features",
    )
    parser.add_argument(
        "--no-legs",
        action="store_true",
        help="Exclude survey leg features",
    )
    parser.add_argument(
        "--passages",
        action="store_true",
        help="Include passage polygon features (from LRUD data)",
    )
    parser.add_argument(
        "--anchors",
        action="store_true",
        help="Include anchor point features (fixed reference stations)",
    )
    parser.add_argument(
        "--no-colors",
        action="store_true",
        help="Disable origin-based coloring of stations and legs",
    )
    parser.add_argument(
        "--algorithm",
        choices=[algorithm.name for algorithm in LoopClosureAlgorithm.variants()],
        default=LoopClosureAlgorithm.LSE_REDUCED_PCG.name,
        help="Covariance-weighted loop closure algorithm",
    )
    parser.add_argument(
        "--mode",
        type=LoopClosureMode,
        choices=list(LoopClosureMode),
        default=LoopClosureMode.SPATIAL,
    )
    parser.add_argument(
        "--sigma-m",
        type=float,
        default=1.0,
        help=(
            "Independent Cartesian placement standard deviation in metres (default: 1)"
        ),
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Export measured geometry without loop closure",
    )
    parser.add_argument(
        "--minify",
        action="store_true",
        help="Compact output without indentation (smaller file size)",
    )

    parsed_args = parser.parse_args(args)

    # Validate input
    if not parsed_args.input_file.exists():
        logger.error("Error: Input file not found: %s", parsed_args.input_file)
        return 1

    if parsed_args.input_file.suffix.lower() != FileExtension.MAK.value:
        logger.error(
            "Error: Input file must be a .MAK file: %s", parsed_args.input_file
        )
        return 1

    try:
        loop_closure = (
            None
            if parsed_args.raw
            else LoopClosure(
                mode=parsed_args.mode,
                sigma_m=parsed_args.sigma_m,
                algorithm=getattr(LoopClosureAlgorithm, parsed_args.algorithm),
            )
        )

        result = convert_mak_to_geojson(
            parsed_args.input_file,
            output_path=parsed_args.output_file,
            include_stations=not parsed_args.no_stations,
            include_legs=not parsed_args.no_legs,
            include_passages=parsed_args.passages,
            include_anchors=parsed_args.anchors,
            color_by_origin=not parsed_args.no_colors,
            loop_closure=loop_closure,
            minify=parsed_args.minify,
        )

        if parsed_args.output_file is None:
            # Print to stdout
            print(result)  # noqa: T201

        else:
            # Print status to stderr
            logger.info(
                "Converted %s -> %s", parsed_args.input_file, parsed_args.output_file
            )

    except FileNotFoundError:
        logger.exception("FileNotFoundError")
        return 1

    except Exception:
        logger.exception("Unknown Problem ...")
        return 1

    return 0
