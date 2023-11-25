from typing import Any, Dict

class ThreadTaskStateBase:
    """Base class for the "ThreadState" and "TaskStateAsync" """
    stopping=False

    def wait(self, sec):
        raise Exception("NOT DEFINED.")


class BaseError(Exception):
    """Base error class."""


class EventLoopBase:
    """Base Class for the Event Loop"""


class Request(Dict[str, Any]):
    def __init__(self, r: int, action: str, ffid: int, key: Any, val: Any, c: str):
        super().__init__({"r": r, "action": action, "ffid": ffid, "key": key, "val": val, "c": c})
