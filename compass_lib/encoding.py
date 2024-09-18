import dataclasses
import datetime
import json


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):

        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)

        if isinstance(obj, datetime.date):
            return obj.isoformat()

        from compass_lib.parser import ShotFlag
        if isinstance(obj, ShotFlag):
            return obj.value

        return super().default(obj)
