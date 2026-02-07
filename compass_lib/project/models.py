# -*- coding: utf-8 -*-
"""Project data models for Compass .MAK files.

Uses Pydantic discriminated unions for polymorphic directive handling.
All serialization is handled by Pydantic's built-in methods.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Any
from typing import ClassVar
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Discriminator
from pydantic import Field
from pydantic import Tag
from pydantic import field_validator
from pydantic import model_validator

from compass_lib.enums import Datum
from compass_lib.enums import FormatIdentifier
from compass_lib.models import NEVLocation  # noqa: TC001
from compass_lib.survey.models import CompassDatFile  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Iterator


# --- Directive Classes ---
# Each directive has a `type` field that acts as a discriminator


class UnknownDirective(BaseModel):
    """Unknown directive for roundtrip fidelity."""

    type: Literal["unknown"] = "unknown"
    directive_type: str
    content: str

    def __str__(self) -> str:
        return f"{self.directive_type}{self.content};"


class FolderStartDirective(BaseModel):
    """Folder start directive (lines starting with [)."""

    type: Literal["folder_start"] = "folder_start"
    name: str

    def __str__(self) -> str:
        return f"[{self.name};"


class FolderEndDirective(BaseModel):
    """Folder end directive (];)."""

    type: Literal["folder_end"] = "folder_end"

    def __str__(self) -> str:
        return "];"


class CommentDirective(BaseModel):
    """Comment directive (lines starting with /)."""

    type: Literal["comment"] = "comment"
    comment: str

    def __str__(self) -> str:
        return f"/ {self.comment}"


class DatumDirective(BaseModel):
    """Datum directive (lines starting with &)."""

    type: Literal["datum"] = "datum"
    datum: Datum

    @field_validator("datum", mode="before")
    @classmethod
    def normalize_datum(cls, value: str | Datum) -> Datum:
        """Validate and normalize datum string to Datum enum.

        Args:
            value: Datum as string or Datum enum

        Returns:
            Datum enum value

        Raises:
            ValueError: If datum string is not recognized
        """
        if isinstance(value, Datum):
            return value
        return Datum.normalize(value)

    def __str__(self) -> str:
        return f"&{self.datum.value};"


class UTMZoneDirective(BaseModel):
    """UTM zone directive (lines starting with $).

    Positive zones (1-60) indicate northern hemisphere.
    Negative zones (-1 to -60) indicate southern hemisphere.
    """

    type: Literal["utm_zone"] = "utm_zone"
    utm_zone: int

    @field_validator("utm_zone")
    @classmethod
    def validate_utm_zone(cls, v: int) -> int:
        if v == 0:
            raise ValueError(
                "UTM zone cannot be 0. Use 1-60 for north, -1 to -60 for south."
            )
        if abs(v) > 60:
            raise ValueError(
                f"UTM zone must be between -60 and 60 (excluding 0), got {v}"
            )
        return v

    def __str__(self) -> str:
        return f"${self.utm_zone};"


class UTMConvergenceDirective(BaseModel):
    """UTM convergence angle directive (lines starting with % or *).

    The % prefix indicates file-level convergence is enabled.
    The * prefix indicates file-level convergence is disabled.
    """

    type: Literal["utm_convergence"] = "utm_convergence"
    utm_convergence: float
    enabled: bool = True  # True for %, False for *

    def __str__(self) -> str:
        prefix = "%" if self.enabled else "*"
        return f"{prefix}{self.utm_convergence:.3f};"


# Flags constants (legacy bitmask - kept for backwards compatibility)
FLAGS_OVERRIDE_LRUDS: int = 0x1
FLAGS_LRUDS_AT_TO_STATION: int = 0x2


class DeclinationMode(str, Enum):
    """How declinations are derived and processed."""

    IGNORE = "I"  # Declinations are ignored
    ENTERED = "E"  # Use declinations entered in survey book
    AUTO = "A"  # Calculate from survey date and geographic location


class FlagsDirective(BaseModel):
    """Project flags directive (lines starting with !).

    Supports all 10 documented Compass project flags:
    1. G/g - Global override settings enabled/disabled
    2. I/E/A - Declination mode (Ignore/Entered/Auto)
    3. V/v - Apply UTM convergence enabled/disabled
    4. O/o - Override LRUD associations enabled/disabled
    5. T/t - LRUDs at To/From station
    6. S/s - Apply shot flags enabled/disabled
    7. X/x - Apply total exclusion flags enabled/disabled
    8. P/p - Apply plotting exclusion flags enabled/disabled
    9. L/l - Apply length exclusion flags enabled/disabled
    10. C/c - Apply close exclusion flags enabled/disabled

    Example: !GAVOTSCXPL;
    """

    # Class-level constants (must use ClassVar to avoid being treated as fields)
    OVERRIDE_LRUDS: ClassVar[int] = FLAGS_OVERRIDE_LRUDS
    LRUDS_AT_TO_STATION: ClassVar[int] = FLAGS_LRUDS_AT_TO_STATION

    type: Literal["flags"] = "flags"

    # Flag 1: G/g - Global override
    global_override: bool = False

    # Flag 2: I/E/A - Declination mode
    declination_mode: DeclinationMode | None = None

    # Flag 3: V/v - Apply UTM convergence
    apply_utm_convergence: bool = False

    # Flag 4: O/o - Override LRUD associations
    override_lruds: bool = False

    # Flag 5: T/t - LRUDs at To station (vs From station)
    lruds_at_to_station: bool = False

    # Flag 6: S/s - Apply shot flags
    apply_shot_flags: bool = False

    # Flag 7: X/x - Apply total exclusion flags
    apply_total_exclusion: bool = False

    # Flag 8: P/p - Apply plotting exclusion flags
    apply_plotting_exclusion: bool = False

    # Flag 9: L/l - Apply length exclusion flags
    apply_length_exclusion: bool = False

    # Flag 10: C/c - Apply close exclusion flags
    apply_close_exclusion: bool = False

    # Raw string for roundtrip fidelity
    raw_flags: str = ""

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def convert_flags_bitmask(cls, data: Any) -> Any:
        """Convert legacy flags bitmask to boolean fields."""
        if isinstance(data, dict) and "flags" in data:
            flags = data.pop("flags")
            if flags:
                data.setdefault("override_lruds", bool(flags & FLAGS_OVERRIDE_LRUDS))
                data.setdefault(
                    "lruds_at_to_station", bool(flags & FLAGS_LRUDS_AT_TO_STATION)
                )
        return data

    @property
    def is_override_lruds(self) -> bool:
        """Check if Override LRUDs flag is set."""
        return self.override_lruds

    @property
    def is_lruds_at_to_station(self) -> bool:
        """Check if LRUDs at TO station flag is set."""
        return self.lruds_at_to_station

    @property
    def flags(self) -> int:
        """Get flags as bitmask for backwards compatibility."""
        result = 0
        if self.override_lruds:
            result |= FLAGS_OVERRIDE_LRUDS
        if self.lruds_at_to_station:
            result |= FLAGS_LRUDS_AT_TO_STATION
        return result

    def __str__(self) -> str:
        if self.raw_flags:
            return f"!{self.raw_flags};"
        # Build flags string from individual flags
        parts = []
        parts.append("G" if self.global_override else "g")
        if self.declination_mode:
            parts.append(self.declination_mode.value)
        parts.append("V" if self.apply_utm_convergence else "v")
        parts.append("O" if self.override_lruds else "o")
        parts.append("T" if self.lruds_at_to_station else "t")
        parts.append("S" if self.apply_shot_flags else "s")
        parts.append("X" if self.apply_total_exclusion else "x")
        parts.append("P" if self.apply_plotting_exclusion else "p")
        parts.append("L" if self.apply_length_exclusion else "l")
        parts.append("C" if self.apply_close_exclusion else "c")
        return f"!{''.join(parts)};"


class LinkStation(BaseModel):
    """A linked/fixed station with optional coordinates."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    location: NEVLocation | None = None

    def __str__(self) -> str:
        if self.location:
            unit = self.location.unit.lower()
            return (
                f"{self.name}[{unit},{self.location.easting:.3f},"
                f"{self.location.northing:.3f},{self.location.elevation:.3f}]"
            )
        return self.name


class FileDirective(BaseModel):
    """Data file directive (lines starting with #)."""

    type: Literal["file"] = "file"
    file: str
    link_stations: list[LinkStation] = Field(default_factory=list)
    # Populated when loading project - excluded from serialization by default
    data: CompassDatFile | None = Field(default=None, exclude=True)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __str__(self) -> str:
        if not self.link_stations:
            return f"#{self.file};"
        result = f"#{self.file}"
        for station in self.link_stations:
            result += f",\r\n  {station}"
        result += ";"
        return result


class LocationDirective(BaseModel):
    """Project location directive (lines starting with @).

    Positive zones (1-60) indicate northern hemisphere.
    Negative zones (-1 to -60) indicate southern hemisphere.
    Zone 0 is allowed to indicate "no location specified".
    """

    type: Literal["location"] = "location"
    easting: float
    northing: float
    elevation: float
    utm_zone: int
    utm_convergence: float

    @field_validator("utm_zone")
    @classmethod
    def validate_utm_zone(cls, v: int) -> int:
        if abs(v) > 60:
            raise ValueError(f"UTM zone must be between -60 and 60, got {v}")
        return v

    @property
    def has_location(self) -> bool:
        """True if this contains a real location (zone != 0)."""
        return self.utm_zone != 0

    def __str__(self) -> str:
        return (
            f"@{self.easting:.3f},{self.northing:.3f},"
            f"{self.elevation:.3f},{self.utm_zone},{self.utm_convergence:.3f};"
        )


# --- Discriminated Union ---
# Pydantic automatically deserializes to the correct type based on "type" field


def _get_directive_type(v: Any) -> str:
    """Extract the discriminator value for directive types.

    Called by Pydantic during validation to determine which directive
    type to instantiate. Handles both dict input (from JSON) and
    already-instantiated model objects.
    """
    if isinstance(v, dict):
        return v.get("type", "unknown")
    # Already a model instance - get the type field
    return getattr(v, "type", "unknown")


Directive = Annotated[
    Annotated[CommentDirective, Tag("comment")]
    | Annotated[DatumDirective, Tag("datum")]
    | Annotated[UTMZoneDirective, Tag("utm_zone")]
    | Annotated[UTMConvergenceDirective, Tag("utm_convergence")]
    | Annotated[FlagsDirective, Tag("flags")]
    | Annotated[LocationDirective, Tag("location")]
    | Annotated[FileDirective, Tag("file")]
    | Annotated[FolderStartDirective, Tag("folder_start")]
    | Annotated[FolderEndDirective, Tag("folder_end")]
    | Annotated[UnknownDirective, Tag("unknown")],
    Discriminator(_get_directive_type),
]

# Type alias for backwards compatibility and type hints
CompassProjectDirective = (
    CommentDirective
    | DatumDirective
    | UTMZoneDirective
    | UTMConvergenceDirective
    | FlagsDirective
    | LocationDirective
    | FileDirective
    | FolderStartDirective
    | FolderEndDirective
    | UnknownDirective
)


# --- Main Project Model ---


class CompassMakFile(BaseModel):
    """A Compass .MAK project file.

    Serialization is fully automatic via Pydantic:
        json_str = project.model_dump_json(indent=2)
        project = CompassMakFile.model_validate_json(json_str)
    """

    model_config = ConfigDict(populate_by_name=True)

    # Wrapper format fields (for JSON compatibility)
    version: str = "1.0"
    format: str = Field(default=FormatIdentifier.COMPASS_MAK.value)
    directives: list[Directive] = Field(default_factory=list)

    @property
    def file_directives(self) -> list[FileDirective]:
        return [d for d in self.directives if isinstance(d, FileDirective)]

    @property
    def location(self) -> LocationDirective | None:
        for d in self.directives:
            if isinstance(d, LocationDirective):
                return d
        return None

    @property
    def datum(self) -> Datum | None:
        for d in self.directives:
            if isinstance(d, DatumDirective):
                return d.datum
        return None

    @property
    def utm_zone(self) -> int | None:
        # Priority: UTMZoneDirective > LocationDirective (if has_location)
        for d in self.directives:
            if isinstance(d, UTMZoneDirective):
                return d.utm_zone
        loc = self.location
        if loc and loc.has_location:
            return loc.utm_zone
        return None

    @property
    def flags(self) -> FlagsDirective | None:
        """Get the project flags directive if present."""
        for d in self.directives:
            if isinstance(d, FlagsDirective):
                return d
        return None

    @property
    def utm_convergence(self) -> float:
        """Get the UTM convergence angle.

        Returns the convergence value from UTMConvergenceDirective if present,
        or from LocationDirective, defaulting to 0.0.
        """
        for d in self.directives:
            if isinstance(d, UTMConvergenceDirective):
                return d.utm_convergence
        loc = self.location
        if loc:
            return loc.utm_convergence
        return 0.0

    def iter_files(self) -> Iterator[FileDirective]:
        for d in self.directives:
            if isinstance(d, FileDirective):
                yield d

    def get_all_stations(self) -> set[str]:
        stations: set[str] = set()
        for fd in self.file_directives:
            if fd.data:
                stations.update(fd.data.get_all_stations())
        return stations

    def get_all_link_stations(self) -> list[LinkStation]:
        return [ls for fd in self.file_directives for ls in fd.link_stations]

    def get_fixed_stations(self) -> list[LinkStation]:
        return [
            ls for fd in self.file_directives for ls in fd.link_stations if ls.location
        ]

    @property
    def total_surveys(self) -> int:
        return sum(
            len(fd.data.surveys) if fd.data else 0 for fd in self.file_directives
        )

    @property
    def total_shots(self) -> int:
        return sum(fd.data.total_shots if fd.data else 0 for fd in self.file_directives)


# Avoid circular import - import at end

# Update forward reference
FileDirective.model_rebuild()
