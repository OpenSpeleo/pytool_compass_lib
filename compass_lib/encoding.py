from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import asdict
from dataclasses import is_dataclass


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        from compass_lib.parser import ShotFlag  # noqa: PLC0415

        match obj:
            case datetime.date():
                return obj.isoformat()

            case ShotFlag():
                return obj.value

            case uuid.UUID():
                return str(obj)

        if is_dataclass(obj):
            return asdict(obj)

        return super().default(obj)
