from __future__ import annotations

import dataclasses
import datetime
import json
import unittest

import pytest

from compass_lib.encoding import EnhancedJSONEncoder
from compass_lib.enums import ShotFlag


# A sample dataclass for testing
@dataclasses.dataclass
class SampleData:
    name: str
    age: int
    active: bool


class TestEnhancedJSONEncoder(unittest.TestCase):
    """Unit tests for EnhancedJSONEncoder."""

    def setUp(self):
        """Setup a standard encoder instance before each test."""
        self.encoder = EnhancedJSONEncoder()

    def test_dataclass_encoding(self):
        """Test JSON encoding for a dataclass instance."""
        obj = SampleData(name="John", age=30, active=True)
        expected_json = '{"name": "John", "age": 30, "active": true}'
        result = json.dumps(obj, cls=EnhancedJSONEncoder)
        assert result == expected_json, "Failed to encode dataclass correctly"

    def test_date_encoding(self):
        """Test JSON encoding for a datetime.date instance."""
        obj = datetime.date(2024, 1, 1)
        expected_json = '"2024-01-01"'
        result = json.dumps(obj, cls=EnhancedJSONEncoder)
        assert result == expected_json, "Failed to encode date correctly"

    def test_shotflag_encoding(self):
        """Test JSON encoding for ShotFlag enum instance."""
        obj = ShotFlag.EXCLUDE_PLOTING
        expected_json = '"P"'
        result = json.dumps(obj, cls=EnhancedJSONEncoder)
        assert result == expected_json, "Failed to encode ShotFlag enum correctly"

    def test_default_encoding(self):
        """Test JSON encoding for types not handled by EnhancedJSONEncoder."""
        obj = {"key": "value"}
        expected_json = '{"key": "value"}'
        result = json.dumps(obj, cls=EnhancedJSONEncoder)
        assert result == expected_json, "Failed to fallback to default encoding"

    def test_unsupported_type_encoding(self):
        """Test that unsupported types raise a TypeError as expected."""

        class UnsupportedType:
            pass

        obj = UnsupportedType()

        with pytest.raises(TypeError):
            json.dumps(obj, cls=EnhancedJSONEncoder)


if __name__ == "__main__":
    unittest.main()
