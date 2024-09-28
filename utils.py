from typing import *
from datetime import datetime

def mtime(time: str) -> float:
    """
    Convert a time string in the format of HH:MM:SS to a timestamp compatible with time.time()
    """
    return datetime.strptime(time, "%H:%M:%S").replace(year=2024, month=1, day=1).timestamp()

def htime(time: str) -> float:
    """
    Convert a time string in the format of HH:MM:SS AM/PM to a timestamp compatible with time.time()
    """
    return datetime.strptime(time, "%I:%M:%S %p").replace(year=2024, month=1, day=1).timestamp()

def case_insensitive_get(d: Dict[str, Any], key: str) -> Any:
    """
    Get channel name from Chats dictionary in a case insensitive manner.
    """
    for k in d.keys():
        if k.lower() == key.lower():
            return k
    return None