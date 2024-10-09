import datetime
import json
import uuid


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):

        from compass_lib.parser import ShotFlag

        match obj:

            case datetime.date():
                return obj.isoformat()

            case ShotFlag():
                return obj.value

            case uuid.UUID():
                return str(obj)

        return super().default(obj)
