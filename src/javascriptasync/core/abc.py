from typing import Any, Dict

import threading


class ThreadTaskStateBase:
    """Base class for the "ThreadState" and "TaskStateAsync" """

    stopping = False

    def stop(self):
        self.stopping = True

    def wait(self, sec):
        raise NotImplementedError("NOT DEFINED.")  # pylint: disable=broad-except


class BaseError(Exception):
    """Base error class."""


class EventObject:
    """Parent mixin for CrossThreadEvent and CrossThreadEventSync, to return values
    back to a calling thread or coroutine without the need for threading barriers."""

    output = None
    timeout_happened = False
    event_lock = threading.Lock()

    def set(self):
        """shared 'set' function for both threading.Event and asyncio.Event"""
        raise NotImplementedError()

    def set_data(self, data):
        """Set the data returned to the subscribed thread or coroutine."""
        self.output = data

    def get_data(self):
        """called within the target thread or coroutine,
        retrieve the data published to this Event."""
        with self.event_lock:
            req = Request(**self.output)
            return req

    def publish(self, data: Any):
        """Publish data back to the thread or coroutine
        which requested it.  Triggers the event_lock until
        the data has been sucsesfully returned."""
        with self.event_lock:
            self.set()  #
            self.set_data(data)

    def timeout_flag(self):
        """Set the timeout_happened flag to true."""
        print("a timeout happened")
        with self.event_lock:
            self.timeout_happened = True
            return True

    def was_timeout(self) -> bool:
        """Return true if a timeout happened, false otherwise."""
        evt = False
        with self.event_lock:
            evt = self.timeout_happened
        return evt


# {"c": "pyi", "r": r, "key": key, "val": val, "sig": sig}
class Request(Dict[str, Any]):
    """
    Extended class of Dictionary to provide some common
    functionality.

    Args:
        Dict (_type_): _description_
    """

    def __init__(
        self,
        r: int = None,
        action: str = None,
        ffid: int = None,
        key: Any = None,
        keys: Any = None,
        args: Any = None,
        val: Any = None,
        error: Any = None,
        sig: Any = None,
        c: str = None,
        insp: str = None,
    ):
        self.r = r
        self.action = action
        self.ffid = ffid
        self.key = key
        self.keys = keys
        self.args = args
        self.val = val
        self.error = error
        self.sig = sig
        self.c = c
        self.insp = insp

        super().__init__(
            {
                k: v
                for k, v in {
                    "r": r,
                    "action": action,
                    "ffid": ffid,
                    "key": key,
                    "keys": self.keys,
                    "args": args,
                    "val": val,
                    "error": error,
                    "sig": sig,
                    "c": c,
                    "insp": insp,
                }.items()
                if v is not None
            }
        )

    def __setattr__(self, key, value):
        self[key] = value
        super().__setattr__(key, value)

    def __dict__(self):
        return {
            k: v
            for k, v in {
                "r": self.r,
                "action": self.action,
                "ffid": self.ffid,
                "key": self.key,
                "keys": self.keys,
                "args": self.args,
                "val": self.val,
                "error": self.error,
                "sig": self.sig,
                "c": self.c,
                "insp": self.insp,
            }.items()
            if v is not None
        }

    def error_state(self):
        return self.error is not None

    @classmethod
    def create_by_action(
        cls, r: int, action: str, ffid: int, key: Any, args: Any = None
    ) -> "Request":
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
        if action in ["serialize", "keys", "getdeep"]:
            return Request(r=r, action=action, ffid=ffid)
        elif action in ["get", "inspect"]:
            return Request(r=r, action=action, ffid=ffid, key=key)
        elif action in ["set", "init"]:
            return Request(r=r, action=action, ffid=ffid, key=key, args=args)

    @classmethod
    def create_for_pcall(cls, ffid: int, action: str, key: Any, args: Any = None) -> "Request":
        """
        Class method that creates a Request object based on the given parameters.

        Parameters:
        ffid (int): The ID of the function.
        action (str): The action to be taken ("serialize", "keys", "get", "inspect", "set", "call", "init").

        key (Any): The key for the request, used in "get", "inspect", "set", "init" actions.
        args (Any): The arguments for the request, used in "set", "init" actions.

        Returns:
        Request: The Request object created using the parameters.
        """
        return Request(action=action, ffid=ffid, key=key, args=args)
