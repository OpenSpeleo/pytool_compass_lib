# -*- coding: utf-8 -*-
"""Compass Parser Library.

A Python library for parsing and formatting Compass cave survey data files.
Supports .DAT (survey data), .MAK (project files), and .PLT (plot files).

Usage:
    # Load a complete project (MAK + all DAT files)
    from compass_scratchpad import load_project
    project = load_project(Path("cave.mak"))

    for file_dir in project.file_directives:
        print(f"File: {file_dir.file}")
        if file_dir.data:
            for trip in file_dir.data.trips:
                print(f"  Survey: {trip.header.survey_name}")

    # Or load individual files
    from compass_scratchpad import read_dat_file, read_mak_file
    trips = read_dat_file(Path("survey.DAT"))
    directives = read_mak_file(Path("project.MAK"))
"""

__version__ = "0.3.0"

# Constants
from compass_scratchpad.constants import COMPASS_ENCODING
from compass_scratchpad.constants import FEET_TO_METERS
from compass_scratchpad.constants import JSON_ENCODING
from compass_scratchpad.constants import METERS_TO_FEET

# Enums
from compass_scratchpad.enums import AzimuthUnit
from compass_scratchpad.enums import CompassFileType
from compass_scratchpad.enums import DrawOperation
from compass_scratchpad.enums import FileFormat
from compass_scratchpad.enums import InclinationUnit
from compass_scratchpad.enums import LengthUnit
from compass_scratchpad.enums import LrudAssociation
from compass_scratchpad.enums import LrudItem
from compass_scratchpad.enums import Severity
from compass_scratchpad.enums import ShotItem
from compass_scratchpad.errors import CompassParseError
from compass_scratchpad.errors import CompassParseException
from compass_scratchpad.errors import SourceLocation
from compass_scratchpad.interface import CompassInterface
from compass_scratchpad.io import CancellationToken
from compass_scratchpad.io import load_project
from compass_scratchpad.io import read_dat_file
from compass_scratchpad.io import read_mak_and_dat_files
from compass_scratchpad.io import read_mak_file
from compass_scratchpad.io import save_project
from compass_scratchpad.io import write_dat_file
from compass_scratchpad.io import write_mak_file
from compass_scratchpad.models import Bounds
from compass_scratchpad.models import Location
from compass_scratchpad.models import NEVLocation
from compass_scratchpad.project.models import CompassMakFile
from compass_scratchpad.project.models import FileDirective
from compass_scratchpad.project.models import LinkStation
from compass_scratchpad.survey.models import CompassDatFile
from compass_scratchpad.survey.models import CompassShot
from compass_scratchpad.survey.models import CompassTrip
from compass_scratchpad.survey.models import CompassTripHeader
from compass_scratchpad.validation import days_in_month
from compass_scratchpad.validation import is_valid_station_name
from compass_scratchpad.validation import validate_station_name

__all__ = [
    # Constants
    "COMPASS_ENCODING",
    "FEET_TO_METERS",
    "JSON_ENCODING",
    "METERS_TO_FEET",
    # Enums
    "AzimuthUnit",
    "CompassFileType",
    "DrawOperation",
    "FileFormat",
    "InclinationUnit",
    "LengthUnit",
    "LrudAssociation",
    "LrudItem",
    "Severity",
    "ShotItem",
    # Errors
    "CompassParseError",
    "CompassParseException",
    "SourceLocation",
    # Base Models
    "Bounds",
    "Location",
    "NEVLocation",
    # Survey Models
    "CompassDatFile",
    "CompassShot",
    "CompassTrip",
    "CompassTripHeader",
    # Project Models
    "CompassMakFile",
    "FileDirective",
    "LinkStation",
    # Validation
    "is_valid_station_name",
    "validate_station_name",
    "days_in_month",
    # I/O
    "CompassInterface",
    "load_project",
    "save_project",
    "read_dat_file",
    "read_mak_file",
    "read_mak_and_dat_files",
    "write_dat_file",
    "write_mak_file",
    "CancellationToken",
]
