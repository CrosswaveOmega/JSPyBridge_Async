from typing import Any, Dict


class ThreadTaskStateBase:
    """Base class for the "ThreadState" and "TaskStateAsync" """

    stopping = False

    def wait(self, sec):
        raise Exception("NOT DEFINED.")


class BaseError(Exception):
    """Base error class."""


class EventLoopBase:
    """Base Class for the Event Loop"""


# {"c": "pyi", "r": r, "key": key, "val": val, "sig": sig}
class Request(Dict[str, Any]):
    def __init__(
        self,
        r: int = None,
        action: str = None,
        ffid: int = None,
        key: Any = None,
        args: Any = None,
        val: Any = None,
        error: Any = None,
        sig: Any = None,
        c: str = None,
    ):
        self.r = r
        self.action = action
        self.ffid = ffid
        self.key = key
        self.args = args
        self.val = val
        self.error = error
        self.sig = sig
        self.c = c
        super().__init__(
            {
                k: v
                for k, v in {
                    "r": r,
                    "action": action,
                    "ffid": ffid,
                    "key": key,
                    "args": args,
                    "val": val,
                    "error": error,
                    "sig": sig,
                    "c": c,
                }.items()
                if v is not None
            }
        )
