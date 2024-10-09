from collections import OrderedDict
from typing import Any


class OrderedQueue(OrderedDict):
    def add(self, key: Any) -> None:
        if key not in self:
            self[key] = None

    def remove(self, key: Any) -> None:
        del self[key]
