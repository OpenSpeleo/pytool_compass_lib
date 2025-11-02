from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import asdict
from dataclasses import is_dataclass
from typing import Any


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        from compass_lib.models import ShotFlag  # noqa: PLC0415

        match o:
            case datetime.date():
                return o.isoformat()

            case ShotFlag():
                return o.value

            case uuid.UUID():
                return str(o)

            case _ if is_dataclass(o):
                return asdict(o)  # pyright: ignore[reportArgumentType]

            case _:
                return super().default(o)
