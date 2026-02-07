# -*- coding: utf-8 -*-
"""Compass Parser Library.

A Python library for parsing and formatting Compass cave survey data files.
Supports .DAT (survey data), .MAK (project files), and .PLT (plot files).

Usage:
    # Load a complete project (MAK + all DAT files)
    from compass_lib import load_project
    project = load_project(Path("cave.mak"))

    for file_dir in project.file_directives:
        print(f"File: {file_dir.file}")
        if file_dir.data:
            for survey in file_dir.data.surveys:
                print(f"  Survey: {survey.header.survey_name}")

    # Or load individual files
    from compass_lib import read_dat_file, read_mak_file
    surveys = read_dat_file(Path("survey.DAT"))
    directives = read_mak_file(Path("project.MAK"))
"""

__version__ = "0.0.3"

# Constants
from compass_lib.constants import COMPASS_ENCODING
from compass_lib.constants import FEET_TO_METERS
from compass_lib.constants import JSON_ENCODING
from compass_lib.constants import METERS_TO_FEET

# Enums
from compass_lib.enums import AzimuthUnit
from compass_lib.enums import CompassFileType
from compass_lib.enums import DrawOperation
from compass_lib.enums import FileFormat
from compass_lib.enums import InclinationUnit
from compass_lib.enums import LengthUnit
from compass_lib.enums import LrudAssociation
from compass_lib.enums import LrudItem
from compass_lib.enums import Severity
from compass_lib.enums import ShotItem
from compass_lib.errors import CompassParseError
from compass_lib.errors import CompassParseException
from compass_lib.errors import SourceLocation
from compass_lib.interface import CompassInterface
from compass_lib.io import CancellationToken
from compass_lib.io import load_project
from compass_lib.io import read_dat_file
from compass_lib.io import read_mak_and_dat_files
from compass_lib.io import read_mak_file
from compass_lib.io import save_project
from compass_lib.io import write_dat_file
from compass_lib.io import write_mak_file
from compass_lib.models import Bounds
from compass_lib.models import Location
from compass_lib.models import NEVLocation
from compass_lib.project.models import CompassMakFile
from compass_lib.project.models import FileDirective
from compass_lib.project.models import LinkStation
from compass_lib.survey.models import CompassDatFile
from compass_lib.survey.models import CompassShot
from compass_lib.survey.models import CompassSurvey
from compass_lib.survey.models import CompassSurveyHeader
from compass_lib.validation import days_in_month
from compass_lib.validation import is_valid_station_name
from compass_lib.validation import validate_station_name

__all__ = [
    # Constants
    "COMPASS_ENCODING",
    "FEET_TO_METERS",
    "JSON_ENCODING",
    "METERS_TO_FEET",
    # Enums
    "AzimuthUnit",
    # Base Models
    "Bounds",
    "CancellationToken",
    # Survey Models
    "CompassDatFile",
    "CompassFileType",
    # I/O
    "CompassInterface",
    # Project Models
    "CompassMakFile",
    # Errors
    "CompassParseError",
    "CompassParseException",
    "CompassShot",
    "CompassSurvey",
    "CompassSurveyHeader",
    "DrawOperation",
    "FileDirective",
    "FileFormat",
    "InclinationUnit",
    "LengthUnit",
    "LinkStation",
    "Location",
    "LrudAssociation",
    "LrudItem",
    "NEVLocation",
    "Severity",
    "ShotItem",
    "SourceLocation",
    "days_in_month",
    # Validation
    "is_valid_station_name",
    "load_project",
    "read_dat_file",
    "read_mak_and_dat_files",
    "read_mak_file",
    "save_project",
    "validate_station_name",
    "write_dat_file",
    "write_mak_file",
]
