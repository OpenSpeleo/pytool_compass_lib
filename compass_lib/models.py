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

from compass_lib.enums import Datum


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

    zone: Annotated[
        int,
        Field(
            ge=-60,
            le=60,
            description="UTM zone number (1-60 north, -1 to -60 south, 0 not allowed)",
        ),
    ]

    convergence: Annotated[
        float,
        Field(default=0.0, ge=-5.0, le=5.0, description="Convergence angle in degrees"),
    ]

    datum: Annotated[
        Datum | None,
        Field(
            default=None,
            description="Datum (e.g., Datum.NORTH_AMERICAN_1927, Datum.WGS_1984)",
        ),
    ]

    # -----------------------------
    # Validators
    # -----------------------------

    @field_validator("zone")
    @classmethod
    def validate_zone(cls, v: int) -> int:
        """Validate UTM zone number.

        Positive values (1-60) indicate northern hemisphere.
        Negative values (-1 to -60) indicate southern hemisphere.
        Zero is not allowed.

        Args:
            v: Zone number

        Returns:
            Validated zone number

        Raises:
            ValueError: If zone is 0 or abs(zone) > 60
        """
        if v == 0:
            raise ValueError(
                "UTM zone cannot be 0. Use 1-60 for north, -1 to -60 for south."
            )
        if abs(v) > 60:
            raise ValueError(
                f"UTM zone must be between -60 and 60 (excluding 0), got {v}"
            )
        return v

    @field_validator("datum", mode="before")
    @classmethod
    def normalize_datum(cls, value: str | Datum | None) -> Datum | None:
        """Validate and normalize datum string to Datum enum.

        Accepts either a string (which will be normalized) or a Datum enum value.

        Args:
            value: Datum as string or Datum enum, or None

        Returns:
            Datum enum value or None

        Raises:
            ValueError: If datum string is not recognized
        """
        if value is None or isinstance(value, Datum):
            return value

        # Normalize string to Datum enum
        return Datum.normalize(value)

    # -----------------------------
    # Properties
    # -----------------------------

    @property
    def is_northern_hemisphere(self) -> bool:
        """Check if this location is in the northern hemisphere.

        Returns:
            True if northern hemisphere (zone > 0), False if southern (zone < 0)
        """
        return self.zone > 0

    @property
    def zone_number(self) -> int:
        """Get the absolute zone number (1-60).

        Returns:
            Absolute value of the zone number
        """
        return abs(self.zone)

    # -----------------------------
    # Methods
    # -----------------------------

    def to_latlon(self) -> tuple[float, float]:
        """
        Convert this UTM location to GPS coordinates (latitude, longitude).

        NOTE: This method takes the decision to exclusively use DATUM WGS 1984 for uniformity
        and ignore the datum from the MAK project file.
        This allows for a consistent and predictable conversion of UTM coordinates to GPS coordinates.
        And inter-operability with other software that uses WGS 1984 for GPS coordinates.

        The hemisphere is determined by the sign of the zone:
        - Positive zone (1-60): Northern hemisphere
        - Negative zone (-1 to -60): Southern hemisphere

        Args:
            None

        Returns:
            (lat, lon) in decimal degrees
        """  # noqa: E501

        WGS_1984_EPSG = 4326
        geographic_crs = CRS.from_epsg(WGS_1984_EPSG)

        # ---- Build UTM CRS ----
        # Note: pyproj expects "WGS84" (no space) in proj4 strings, not "WGS 1984"
        # Note: pyproj requires positive zone number and hemisphere specified separately
        hemisphere = "+north" if self.is_northern_hemisphere else "+south"
        utm_crs = CRS.from_proj4(
            f"+proj=utm +zone={self.zone_number} {hemisphere} +datum=WGS84 +units=m +no_defs"  # noqa: E501
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
