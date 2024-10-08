import unittest

import pytest

from compass_lib.constants import COMPASS_MAX_NAME_LENGTH
from compass_lib.constants import OSPL_MAX_RETRY_ATTEMPTS
from compass_lib.errors import DuplicateValueError
from compass_lib.errors import MaxRetriesError
from compass_lib.generators import UniqueIDGenerator
from compass_lib.generators import UniqueNameGenerator
from compass_lib.generators import _BaseUniqueValueGenerator

LOOP_MAX = 100


class TestUniqueNameGenerator(unittest.TestCase):

    def setUp(self):
        # Clear used names before each test
        self._reset_used_values()

    @staticmethod
    def _reset_used_values():
        UniqueNameGenerator._used_values.clear()  # noqa: SLF001

    def test_generate_unique_name(self):
        names = set()
        for _ in range(LOOP_MAX):
            name = UniqueNameGenerator.get()
            assert name not in names
            names.add(name)

    def test_register_name(self):
        name = "UNIQUE1"
        UniqueNameGenerator.register(name)

        assert name in UniqueNameGenerator._used_values  # noqa: SLF001

        with pytest.raises(
            DuplicateValueError,
            match=f"Value `{name}` has already been registred."
        ):
            UniqueNameGenerator.register(name)

    def test_prevent_duplicate_name_generation(self):
        name = "UNIQUE2"
        UniqueNameGenerator._used_values.add(name)  # noqa: SLF001
        generated_name = UniqueNameGenerator.get()
        assert generated_name != name

    def test_generate_name_too_long(self):
        with pytest.raises(
            ValueError,
            match=f"Maximum length allowed: {COMPASS_MAX_NAME_LENGTH}, "
                  f"received: {COMPASS_MAX_NAME_LENGTH + 1}"
        ):
            _ = UniqueNameGenerator.get(str_len=COMPASS_MAX_NAME_LENGTH + 1)


    def test_generate_name_with_different_length(self):
        for length in range(1, COMPASS_MAX_NAME_LENGTH + 1):
            name = UniqueNameGenerator.get(str_len=length)
            assert len(name) == length

    def test_reset_used_values(self):
        name = UniqueNameGenerator.get()
        if name not in UniqueNameGenerator._used_values:  # noqa: SLF001
            raise AssertionError(f"{name} should be in the used names set.")

        self._reset_used_values()
        new_name = UniqueNameGenerator.get()

        assert name not in UniqueNameGenerator._used_values  # noqa: SLF001
        assert name != new_name


class TestUniqueIDGenerator(unittest.TestCase):

    def setUp(self):
        # Clear used names before each test
        UniqueIDGenerator._used_values.clear()  # noqa: SLF001

    def test_generate_unique_id(self):
        ids = set()
        for target in range(1, LOOP_MAX + 1):
            id_val = UniqueIDGenerator.get()
            assert id_val not in ids
            assert id_val == target
            ids.add(id_val)

    def test_register_id(self):
        id_val = "1234"
        UniqueIDGenerator.register(id_val)
        assert id_val in UniqueIDGenerator._used_values  # noqa: SLF001

        with pytest.raises(
            DuplicateValueError,
            match=f"Value `{id_val}` has already been registred."
        ):
            UniqueIDGenerator.register(id_val)

    def test_prevent_duplicate_id_generation(self):
        id_val = "1"
        UniqueIDGenerator._used_values.add(id_val)  # noqa: SLF001
        generated_id = UniqueNameGenerator.get()
        assert generated_id != id_val


class StartAt1IDGenerator(_BaseUniqueValueGenerator):

    @classmethod
    def generate(cls, retry_step: int) -> str:
        return retry_step


class TestStartAt1IDGenerator(unittest.TestCase):

    def setUp(self):
        # Clear used names before each test
        UniqueIDGenerator._used_values.clear()  # noqa: SLF001

    def test_max_retries(self):
        for value in range(1, OSPL_MAX_RETRY_ATTEMPTS + 1):
            StartAt1IDGenerator.register(value)

        with pytest.raises(
            MaxRetriesError,
            match="Impossible to find an available value to use. Max retry attempts "
                  f"reached: {OSPL_MAX_RETRY_ATTEMPTS}"
        ):
            _ = StartAt1IDGenerator.get()


class TestBaseUniqueValueGenerator(unittest.TestCase):

    def test_unimplemented_abstract_get(self):
        with pytest.raises(NotImplementedError, match=""):
            _ = _BaseUniqueValueGenerator.generate(retry_step=1)


if __name__ == "__main__":
    unittest.main()
