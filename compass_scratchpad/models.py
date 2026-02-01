# -*- coding: utf-8 -*-
"""Core data models for Compass file formats.

This module contains the base Pydantic models used across
survey, project, and plot parsing.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pyproj import CRS
from pyproj import Transformer


class NEVLocation(BaseModel):
    """3D location with Northing, Easting, and Vertical (elevation) components.

    All values are stored with their associated unit. The unit for all three
    components must be the same.

    Attributes:
        easting: East-West coordinate
        northing: North-South coordinate
        elevation: Vertical elevation
        unit: The length unit for all coordinates ('f' for feet, 'm' for meters)
    """

    easting: float
    northing: float
    elevation: float
    unit: Annotated[str, Field(default="f", pattern="^[fmFM]$")]

    def __str__(self) -> str:
        """Format as human-readable string."""
        return (
            f"NEVLocation(easting={self.easting}, "
            f"northing={self.northing}, "
            f"elevation={self.elevation}, "
            f"unit={self.unit})"
        )


class UTMLocation(BaseModel):
    """Represents a UTM-based coordinate for fixed stations."""

    easting: Annotated[
        float,
        Field(
            ge=166_000,
            le=834_000,
            description="Easting coordinate in meters (valid UTM range)",
        ),
    ]

    northing: Annotated[
        float,
        Field(ge=0, le=10_000_000, description="Northing coordinate in meters"),
    ]

    elevation: Annotated[
        float,
        Field(
            ge=-435.0,  # Dead Sea (Israel/Jordan/West Bank)
            le=8850,  # Everest
            description="Elevation in meters",
        ),
    ]

    zone: Annotated[int, Field(ge=1, le=60, description="UTM zone number (1-60)")]

    convergence: Annotated[
        float,
        Field(default=0.0, ge=-5.0, le=5.0, description="Convergence angle in degrees"),
    ]

    datum: Annotated[
        str | None,
        Field(
            default=None,
            description="Datum (e.g., 'NAD27', 'WGS84', 'North American 1927')",
        ),
    ]

    # -----------------------------
    # Validators
    # -----------------------------

    @field_validator("datum")
    @classmethod
    def normalize_datum(cls, value: str | None) -> str | None:
        """Validate and normalize datum string"""
        if value is None:
            return None

        value = value.strip().upper()

        # normalize common datum names
        aliases = {
            "NORTH AMERICAN 1927": "NAD27",
            "NORTH AMERICAN 1983": "NAD83",
            "NORTH AMERICAN DATUM 1927": "NAD27",
            "NORTH AMERICAN DATUM 1983": "NAD83",
            "WGS 1984": "WGS84",
            "WORLD GEODETIC SYSTEM 1984": "WGS84",
        }

        return aliases.get(value, value)

    # -----------------------------
    # Methods
    # -----------------------------

    def to_latlon(self) -> tuple[float, float]:
        """
        Convert this UTM location to GPS coordinates (latitude, longitude).

        Returns:
            (lat, lon) in decimal degrees
        """
        # ---- Datum → EPSG mapping ----
        datum_epsg_map = {
            None: 4326,  # default to WGS84 if unspecified
            "WGS84": 4326,
            "NAD83": 4269,
            "NAD27": 4267,
        }

        datum = self.datum or "WGS84"

        try:
            geographic_crs = CRS.from_epsg(datum_epsg_map[datum])
        except KeyError as e:
            raise ValueError(f"Unsupported datum for GPS conversion: {datum!r}") from e

        # ---- Build UTM CRS ----
        utm_crs = CRS.from_proj4(
            f"+proj=utm +zone={self.zone} +datum={datum} +units=m +no_defs"
        )

        transformer = Transformer.from_crs(
            utm_crs,
            geographic_crs,
            always_xy=True,
        )

        lon, lat = transformer.transform(self.easting, self.northing)
        return lat, lon


class Location(BaseModel):
    """3D plot location with northing, easting, and vertical components.

    Used for plot file commands. Values are in feet.

    Attributes:
        northing: North-South coordinate (feet)
        easting: East-West coordinate (feet)
        vertical: Vertical coordinate (feet)
    """

    northing: float | None = None
    easting: float | None = None
    vertical: float | None = None

    def __str__(self) -> str:
        """Format as human-readable string."""
        return (
            f"Location(northing={self.northing}, "
            f"easting={self.easting}, "
            f"vertical={self.vertical})"
        )


class Bounds(BaseModel):
    """Bounding box with lower and upper bounds.

    Attributes:
        lower: Lower bound location
        upper: Upper bound location
    """

    lower: Location = Field(default_factory=Location)
    upper: Location = Field(default_factory=Location)
