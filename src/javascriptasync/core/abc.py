from typing import Any, Dict


class ThreadTaskStateBase:
    """Base class for the "ThreadState" and "TaskStateAsync" """

    stopping = False

    def stop(self):
        self.stopping=True

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
    @classmethod
    def create_by_action(cls, r: int, action: str, ffid: int, key: Any, args: Any=None) -> 'Request':
        """
        Class method that creates a Request object based on the given parameters.

        Parameters:
        r (int): The ID of the request.
        action (str): The action to be taken ("serialize", "keys", "get", "inspect", "set", "init").
        ffid (int): The ID of the function.
        key (Any): The key for the request, used in "get", "inspect", "set", "init" actions.
        args (Any): The arguments for the request, used in "set", "init" actions.

        Returns:
        Request: The Request object created using the parameters.
        """
        if action in ['serialize','keys','getdeep']:
            return Request(r=r,action=action,ffid=ffid)
        elif action in ['get','inspect']:
            return Request(r=r,action=action,ffid=ffid,key=key)
        elif action in ['set','init']:
            return Request(r=r,action=action,ffid=ffid,key=key,args=args)


