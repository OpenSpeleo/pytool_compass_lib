import json
import re
import unittest

import pytest
from pydantic import BaseModel
from pydantic import Field

from compass_lib.errors import DuplicateValueError
from compass_lib.mixins import BaseMixin


# A simple Pydantic model using V2 APIs to test the BaseMixin
class TestModel(BaseModel, BaseMixin):
    name: str
    age: int | None = Field(default=None)


class TestBaseMixin(unittest.TestCase):
    """Unit tests for the BaseMixin class using Pydantic V2 APIs."""

    def test_enforce_snake_and_remove_none(self):
        """Test the enforce_snake_and_remove_none validator to remove None values."""
        data = {"name": "John", "age": None}
        validated_data = TestModel.model_validate(data)

        assert validated_data.name == "John"
        assert validated_data.age is None

    def test_to_json(self):
        """Test the to_json method for serializing a model to a JSON string."""
        model = TestModel(name="John", age=30)
        json_output = model.to_json()
        expected_json = json.dumps({"name": "John", "age": 30}, indent=4, sort_keys=True)
        assert json_output == expected_json

    def test_validate_unique(self):
        """Test validate_unique method to ensure uniqueness of field values."""
        class TestValue:
            def __init__(self, field_value):
                self.name = field_value

        values = [TestValue("A"), TestValue("B"), TestValue("C")]
        unique_values = TestModel.validate_unique("name", values)
        assert len(unique_values) == 3

        # Test with duplicate values to raise DuplicateValueError
        values_with_duplicates = [TestValue("A"), TestValue("B"), TestValue("A")]

        with pytest.raises(DuplicateValueError, match=re.escape("[TestModel] Duplicate value")):  # noqa: E501
            TestModel.validate_unique("name", values_with_duplicates)

    def test_validate_unique_no_duplicates(self):
        """Test validate_unique with no duplicates."""
        class TestItem:
            def __init__(self, field_value):
                self.name = field_value

        values = [TestItem("X"), TestItem("Y"), TestItem("Z")]
        unique_values = TestModel.validate_unique("name", values)
        assert len(unique_values) == 3

    def test_validate_unique_duplicates(self):
        """Test validate_unique with duplicates to raise DuplicateValueError."""
        class TestItem:
            def __init__(self, field_value):
                self.name = field_value

        values = [TestItem("X"), TestItem("Y"), TestItem("X")]

        with pytest.raises(DuplicateValueError, match=re.escape("[TestModel] Duplicate value")):  # noqa: E501
            TestModel.validate_unique("name", values)


if __name__ == "__main__":
    unittest.main()
