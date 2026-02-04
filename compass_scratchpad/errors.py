# -*- coding: utf-8 -*-
"""Error handling for Compass file parsing.

This module provides error classes for tracking parsing errors with
source location information for helpful error messages.
"""

from dataclasses import dataclass

from compass_scratchpad.enums import Severity


@dataclass(frozen=True)
class SourceLocation:
    """Tracks the source location of text for error reporting.

    Attributes:
        source: The source file name or identifier
        line: Line number (0-based)
        column: Column number (0-based)
        text: The text at this location
    """

    source: str
    line: int
    column: int
    text: str

    def __str__(self) -> str:
        """Format as human-readable location string."""
        return f"(in {self.source}, line {self.line + 1}, column {self.column + 1})"


@dataclass(frozen=True)
class CompassParseError:
    """Represents a parsing error or warning with source location.

    This is a data record for storing error information, not an exception.
    Use CompassParseException for raising errors.

    Attributes:
        severity: ERROR or WARNING
        message: Human-readable error message
        location: Source location where error occurred (optional)
    """

    severity: Severity
    message: str
    location: SourceLocation | None = None

    def __str__(self) -> str:
        """Format as human-readable error string."""
        base = f"{self.severity.value}: {self.message}"
        if self.location:
            base += f" {self.location}"
            if self.location.text:
                base += f"\n  {self.location.text}"
        return base


class CompassParseException(Exception):  # noqa: N818
    """Exception raised for critical parsing errors.

    Attributes:
        message: Error message
        location: Source location where error occurred
    """

    def __init__(self, message: str, location: SourceLocation | None = None):
        self.message = message
        self.location = location
        super().__init__(str(self))

    def __str__(self) -> str:
        """Format as human-readable exception string."""
        if self.location:
            return f"{self.message} {self.location}"
        return self.message

    def to_error(self) -> CompassParseError:
        """Convert exception to CompassParseError record."""
        return CompassParseError(
            severity=Severity.ERROR,
            message=self.message,
            location=self.location,
        )
