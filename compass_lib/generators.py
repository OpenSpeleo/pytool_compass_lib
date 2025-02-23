import random
from abc import ABCMeta
from abc import abstractmethod
from typing import Any

from compass_lib.constants import COMPASS_MAX_NAME_LENGTH
from compass_lib.constants import OSPL_MAX_RETRY_ATTEMPTS
from compass_lib.errors import DuplicateValueError
from compass_lib.errors import MaxRetriesError


class _BaseUniqueValueGenerator(metaclass=ABCMeta):
    _used_values = set()

    @classmethod
    def get(cls, *args, **kwargs) -> Any:
        iter_idx = 0
        while True:
            iter_idx += 1
            if iter_idx > OSPL_MAX_RETRY_ATTEMPTS:
                raise MaxRetriesError(
                    "Impossible to find an available value to use. "
                    "Max retry attempts reached: "
                    f"{OSPL_MAX_RETRY_ATTEMPTS}"
                )
            try:
                value = cls.generate(*args, retry_step=iter_idx, **kwargs)
                cls.register(value)
                break
            except DuplicateValueError:
                continue

        return value

    @classmethod
    def register(cls, value) -> None:
        if value in cls._used_values:
            raise DuplicateValueError(f"Value `{value}` has already been registred.")
        cls._used_values.add(value)

    @classmethod
    @abstractmethod
    def generate(cls, retry_step: int, *args, **kwargs) -> Any:
        raise NotImplementedError  # pragma: no cover


class UniqueNameGenerator(_BaseUniqueValueGenerator):
    VOCAB = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    @classmethod
    def get(cls, str_len: int = 6) -> str:
        return super().get(str_len=str_len)

    @classmethod
    def generate(cls, retry_step: int, str_len: int = 6) -> str:
        if str_len > COMPASS_MAX_NAME_LENGTH:
            raise ValueError(
                f"Maximum length allowed: {COMPASS_MAX_NAME_LENGTH}, "
                f"received: {str_len}"
            )
        return "".join(random.choices(cls.VOCAB, k=str_len))


class UniqueIDGenerator(_BaseUniqueValueGenerator):
    @classmethod
    def generate(cls, retry_step: int) -> str:
        max_value = max(cls._used_values) if cls._used_values else 0
        return max_value + 1
