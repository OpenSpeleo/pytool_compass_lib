from __future__ import annotations

from collections import OrderedDict
from typing import Any


class OrderedQueue(OrderedDict):
    def add(self, key: Any, value: Any, fail_if_present: bool = False) -> None:
        if key in self and fail_if_present:
            raise KeyError(f"The key `{key}` is already present: {self[key]=}")

        self[key] = value

    def remove(self, key: Any) -> None:
        del self[key]
