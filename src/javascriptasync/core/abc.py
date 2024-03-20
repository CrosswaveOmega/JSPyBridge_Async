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


class Request(Dict[str, Any]):
    """
    A specialized class extending the Dictionary class for
    initializing JSON objects sent between Python and Node.js.

    This class streamlines the process of creating formatted JSON objects
    by providing a convenient interface for initializing dictionaries
    with specific key-value pairs. It is designed to reduce boilerplate code
    and enhance code readability, making communication between
    Python and Node.js instances more efficient.

    Some key attributes in the Request dictionary  are used
    exclusively for sending data to Node.js, while others are
    for receiving data from Node.js.  If a value is set to None,
    it is omitted from the underlying dictionary.

    Attributes:
    - r (int): Unique request ID for the specific request.
    - action (str): The name of the action Python or Node.js should perform.
    - ffid (int): Unique Foreign Object Reference ID identifying an object on either the Python or Node.js side of the bridge.
    - key (Any): A key attribute used on both sides of the bridge for different purposes.
    - keys (Any): A list of keys returned from Node.js.
    - args (Any): Additional parameters used for init, set, and call actions.
    - val (Any): A value returned by Node.js or Python as part of a request.
    - error (Any): If present, filled with error traceback information.
    - sig (Any): Unique key for the signature of Python objects sent to Node.js, used only if requested by Node.js.
    - c (str): Unique key for when Node.js needs to request data from Python. If present, it is always set to "pyi".
    - insp (str): If the autoInspect constant is enabled on the Node.js side, this key is added with the util.inspect values for Node.js objects.
    - len (int): Only used for blob requests, contains the original byte length for a blob value.
    - blob (str): Only used for blob requests, contains a Base64 encoded string for the blob.

    Example Usage:
    ```
    # Before using the class
    {"r": r, "action": "get", "ffid": ffid, "key": key}

    # With the class
    Request.create_by_action(r, 'get', ffid, key)
    ```

    Methods:
    - create_by_action(cls, r: int, action: str, ffid: int, key: Any, args: Any = None) -> "Request":
      Creates a Request object based on the given parameters.

    - create_for_pcall(cls, ffid: int, action: str, key: Any, args: Any = None) -> "Request":
      Creates a Request object for use with the 'pcall' methods in Executor.
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
        length: int = None,
        blob: str = None,
    ):
        self.r = r
        self.action = action
        self.ffid = ffid
        self.key = key
        self.keyvalues = keys
        self.args = args
        self.val = val
        self.error = error
        self.sig = sig
        self.c = c
        self.insp = insp
        self.length = length
        self.blob = blob
        super().__init__(
            {
                k: v
                for k, v in {
                    "r": r,
                    "action": action,
                    "ffid": ffid,
                    "key": key,
                    "keys": self.keyvalues,
                    "args": args,
                    "val": val,
                    "error": error,
                    "sig": sig,
                    "c": c,
                    "insp": insp,
                    "length": length,
                    "blob": blob,
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
                "keys": self.keyvalues,
                "args": self.args,
                "val": self.val,
                "error": self.error,
                "sig": self.sig,
                "c": self.c,
                "insp": self.insp,
                "length": self.length,
                "blob": self.blob,
            }.items()
            if v is not None
        }

    def error_state(self):
        """
        Determines if an error has occurred and been recorded in the request.

        Returns:
            bool: True if an error is present, False otherwise.
        """
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
        if action in ["serialize", "keys", "getdeep", "blob"]:
            return Request(r=r, action=action, ffid=ffid)
        elif action in ["get", "inspect"]:
            return Request(r=r, action=action, ffid=ffid, key=key)
        elif action in ["set", "init"]:
            return Request(r=r, action=action, ffid=ffid, key=key, args=args)

    @classmethod
    def create_for_pcall(cls, ffid: int, action: str, key: Any, args: Any = None) -> "Request":
        """
        Class method that creates a Request object for use with the 'pcall' methods
        in Executor.

        Parameters:
        ffid (int): The ID of the function.
        action (str): The action to be taken ("serialize", "keys", "get", "inspect", "set", "call", "init").

        key (Any): The key for the request, used in "get", "inspect", "set", "init" actions.
        args (Any): The arguments for the request, used in "set", "init" actions.

        Returns:
        Request: The Request object created using the parameters.
        """
        return Request(action=action, ffid=ffid, key=key, args=args)
