# -*- coding: utf-8 -*-
"""Formatting (serialization) for Compass .MAK project files.

This module provides functions to convert project directive models back to
the Compass .MAK file format string representation.
"""

from collections.abc import Callable

from compass_scratchpad.project.models import CommentDirective
from compass_scratchpad.project.models import CompassMakFile
from compass_scratchpad.project.models import CompassProjectDirective
from compass_scratchpad.project.models import DatumDirective
from compass_scratchpad.project.models import FileDirective
from compass_scratchpad.project.models import FlagsDirective
from compass_scratchpad.project.models import LocationDirective
from compass_scratchpad.project.models import UnknownDirective
from compass_scratchpad.project.models import UTMConvergenceDirective
from compass_scratchpad.project.models import UTMZoneDirective


def format_directive(directive: CompassProjectDirective) -> str:  # noqa: PLR0911
    """Format a single directive as text.

    Args:
        directive: Directive to format

    Returns:
        Formatted directive string with CRLF
    """
    match directive:
        case CommentDirective():
            return f"/{directive.comment}\r\n"

        case DatumDirective():
            return f"&{directive.datum};\r\n"

        case UTMZoneDirective():
            return f"${directive.utm_zone};\r\n"

        case UTMConvergenceDirective():
            prefix = "%" if directive.enabled else "*"
            return f"{prefix}{directive.utm_convergence:.3f};\r\n"

        case FlagsDirective():
            # Use raw_flags if available for roundtrip fidelity
            if directive.raw_flags:
                return f"!{directive.raw_flags};\r\n"
            o = "O" if directive.is_override_lruds else "o"
            t = "T" if directive.is_lruds_at_to_station else "t"
            return f"!{o}{t};\r\n"

        case LocationDirective():
            parts = [
                f"{directive.easting:.3f}",
                f"{directive.northing:.3f}",
                f"{directive.elevation:.3f}",
                str(directive.utm_zone),
                f"{directive.utm_convergence:.3f}",
            ]
            return f"@{','.join(parts)};\r\n"

        case FileDirective():
            if not directive.link_stations:
                return f"#{directive.file};\r\n"

            if len(directive.link_stations) == 1:
                station = directive.link_stations[0]
                station_str = _format_link_station(station)
                return f"#{directive.file},{station_str};\r\n"

            # Multiple link stations: multiline format
            lines = [f"#{directive.file},\r\n"]
            for i, station in enumerate(directive.link_stations):
                station_str = _format_link_station(station)
                if i < len(directive.link_stations) - 1:
                    lines.append(f"  {station_str},\r\n")
                else:
                    lines.append(f"  {station_str};\r\n")
            return "".join(lines)

        case UnknownDirective():
            return f"{directive.directive_type}{directive.content};\r\n"

        case _:
            return str(directive) + "\r\n"


def _format_link_station(station) -> str:
    """Format a link station with optional location.

    Args:
        station: LinkStation object

    Returns:
        Formatted string
    """
    if station.location is None:
        return station.name

    loc = station.location
    unit = loc.unit.lower()
    parts = [
        unit.upper(),
        f"{loc.easting:.3f}",
        f"{loc.northing:.3f}",
        f"{loc.elevation:.3f}",
    ]
    return f"{station.name}[{','.join(parts)}]"


def format_mak_file(
    directives: list[CompassProjectDirective],
    *,
    write: Callable[[str], None] | None = None,
) -> str | None:
    """Format a complete MAK file from directives.

    Args:
        directives: List of directives
        write: Optional callback for streaming output. If provided,
               chunks are written via this callback and None is returned.

    Returns:
        Formatted file content as string (if write is None),
        or None (if write callback is provided)
    """
    if write is not None:
        # Streaming mode
        for directive in directives:
            write(format_directive(directive))
        return None

    # Return mode
    chunks: list[str] = []
    format_mak_file(directives, write=chunks.append)
    return "".join(chunks)


def format_project(
    project: CompassMakFile,
    *,
    write: Callable[[str], None] | None = None,
) -> str | None:
    """Format a complete MAK file from a CompassMakFile.

    This is a convenience wrapper around format_mak_file that accepts
    a CompassMakFile object directly.

    Args:
        project: Project to format
        write: Optional callback for streaming output

    Returns:
        Formatted file content as string (if write is None),
        or None (if write callback is provided)
    """
    return format_mak_file(project.directives, write=write)
