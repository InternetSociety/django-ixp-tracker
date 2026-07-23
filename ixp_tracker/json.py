import dataclasses
from datetime import datetime, timezone
from enum import Enum
from json import JSONEncoder

DATE_FORMAT = "%Y-%m-%d %H:%M:%S%z"


class IXPJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, datetime):
            return stringify_date(o)
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def stringify_date(date_value: datetime) -> str:
    if date_value.tzinfo is None:
        date_value = date_value.replace(tzinfo=timezone.utc)
    return date_value.strftime(DATE_FORMAT)


def dateify_string(string_value: str) -> datetime:
    return datetime.strptime(string_value, DATE_FORMAT)
