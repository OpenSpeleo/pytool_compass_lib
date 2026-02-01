# -*- coding: utf-8 -*-
"""Tests for errors module."""

import pytest

from compass_scratchpad.enums import Severity
from compass_scratchpad.errors import CompassParseError
from compass_scratchpad.errors import CompassParseException
from compass_scratchpad.errors import SourceLocation


class TestSourceLocation:
    """Tests for SourceLocation class."""

    def test_creation(self):
        """Test creating a source location."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="some text",
        )
        assert loc.source == "test.dat"
        assert loc.line == 5
        assert loc.column == 10
        assert loc.text == "some text"

    def test_str(self):
        """Test string representation."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="",
        )
        result = str(loc)
        assert "test.dat" in result
        assert "line 6" in result  # 1-based
        assert "column 11" in result  # 1-based

    def test_immutable(self):
        """Test that SourceLocation is immutable (frozen)."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="",
        )
        with pytest.raises(AttributeError):
            loc.source = "other.dat"


class TestCompassParseError:
    """Tests for CompassParseError dataclass (error record)."""

    def test_creation(self):
        """Test creating a parse error."""
        error = CompassParseError(
            severity=Severity.ERROR,
            message="Something went wrong",
        )
        assert error.severity == Severity.ERROR
        assert error.message == "Something went wrong"
        assert error.location is None

    def test_creation_with_location(self):
        """Test creating a parse error with location."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="bad data",
        )
        error = CompassParseError(
            severity=Severity.ERROR,
            message="Invalid value",
            location=loc,
        )
        assert error.location == loc

    def test_str_without_location(self):
        """Test string representation without location."""
        error = CompassParseError(
            severity=Severity.ERROR,
            message="Something went wrong",
        )
        result = str(error)
        assert "error:" in result
        assert "Something went wrong" in result

    def test_str_with_location(self):
        """Test string representation with location."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="bad data",
        )
        error = CompassParseError(
            severity=Severity.ERROR,
            message="Invalid value",
            location=loc,
        )
        result = str(error)
        assert "error:" in result
        assert "Invalid value" in result
        assert "test.dat" in result
        assert "bad data" in result

    def test_warning_severity(self):
        """Test warning severity."""
        error = CompassParseError(
            severity=Severity.WARNING,
            message="Minor issue",
        )
        result = str(error)
        assert "warning:" in result


class TestCompassParseException:
    """Tests for CompassParseException class."""

    def test_creation(self):
        """Test creating a parse exception."""
        exc = CompassParseException("Parse failed")
        assert exc.message == "Parse failed"
        assert exc.location is None

    def test_creation_with_location(self):
        """Test creating a parse exception with location."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="bad data",
        )
        exc = CompassParseException("Parse failed", loc)
        assert exc.location == loc

    def test_str_without_location(self):
        """Test string representation without location."""
        exc = CompassParseException("Parse failed")
        assert str(exc) == "Parse failed"

    def test_str_with_location(self):
        """Test string representation with location."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="",
        )
        exc = CompassParseException("Parse failed", loc)
        result = str(exc)
        assert "Parse failed" in result
        assert "test.dat" in result

    def test_to_error(self):
        """Test converting exception to error record."""
        loc = SourceLocation(
            source="test.dat",
            line=5,
            column=10,
            text="bad data",
        )
        exc = CompassParseException("Parse failed", loc)
        error = exc.to_error()

        assert isinstance(error, CompassParseError)
        assert error.severity == Severity.ERROR
        assert error.message == "Parse failed"
        assert error.location == loc

    def test_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(CompassParseException) as exc_info:
            raise CompassParseException("Test error")

        assert exc_info.value.message == "Test error"
