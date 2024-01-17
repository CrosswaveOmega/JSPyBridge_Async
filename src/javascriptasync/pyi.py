# pylint: disable=unused-argument
from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio

# THe Python Interface for JavaScript

import inspect
import importlib
import traceback

from weakref import WeakValueDictionary
import types
from typing import Any, Dict, List, Tuple

from .util import generate_snowflake

if TYPE_CHECKING:
    from .configjs import JSConfig
from .errorsjs import NoAsyncLoop, NoPyiAction

from .core.jslogging import log_info, log_print, log_debug, log_warning


def python(method: str) -> types.ModuleType:
    """
    Import a Python module or function dynamically from javascript.

    Args:
        method (str): The name of the Python module or function to import.

    Returns:
        module or function: The imported Python module or function.
    """
    return importlib.import_module(method, package=None)


# It's not used by the JS files.
# def file_import(moduleName: str, absolutePath: str, folderPath: str) -> types.ModuleType:
#     """Import a Python module from a file using its absolute path from javascript.

#     Args:
#         moduleName (str): The name of the module.
#         absolutePath (str): The absolute path to the Python module file.
#         folderPath (str): The folder path to add to sys.path for importing.

#     Returns:
#         module: The imported Python module.

#     """
#     # ABSOLUTELY NOT.
#     # if folderPath not in sys.path:    sys.path.append(folderPath)

#     spec = importlib.util.spec_from_file_location(moduleName, absolutePath)
#     module_from_spec = importlib.util.module_from_spec(spec)
#     spec.loader.exec_module(module_from_spec)
#     return module_from_spec


class Iterate:
    """
    Helper class for iteration over Python objects through javascript.

    This class is used for Python object iteration, making it easier to work with iterators and iterable objects.

    Args:
        v: The Python object to iterate over.

    Attributes:
        what: The Python object being iterated over.
        Next (function): A function to get the next item in the iteration.

    Example:
        iterator = Iterate(some_iterable)
        next_item = iterator.Next()
    """

    def __init__(self, v):
        self.what = v

        # If we have a normal iterator, we need to make it a generator
        if inspect.isgeneratorfunction(v):
            it = self.next_gen()
        elif hasattr(v, "__iter__"):
            it = self.next_iter()

        def next_iter():
            try:
                return next(it)
            except Exception:  # pylint: disable=broad-except
                return "$$STOPITER"

        self.Next = next_iter

    def next_iter(self):
        for entry in self.what:
            yield entry
        return

    def next_gen(self):
        yield self.what()


fix_key = lambda key: key.replace("~~", "") if isinstance(key, str) else key


class PyInterfaceActions:
    """Mixin which defines actions for PyInterface"""


class PyInterface:
    """
    Python Interface for JavaScript.

    This is the class through which Node.JS uses to interact with the
    python side of the bridge.


    Attributes:
        m (Dict[int, Any]): A dictionary of objects with FFID (foreign object reference id) as keys.
        weakmap (WeakValueDictionary): A weak reference dictionary for managing objects.
        cur_ffid (int): The current FFID value.
        ffid_param (int): Parameter used to generate the next FFID.
        config (JSConfig): Reference to the active JSConfig object.
        send_inspect (bool): Whether to send inspect data for console logging.
        current_async_loop: The current asyncio event loop.
        my_actions (Dict[str,MethodType]): All possible methods JavaScript may use through PYI



    """

    def __init__(self, config_obj: JSConfig):
        """Initalize a new PYInterface.

        Args:
            config_obj (JSConfig): Reference to the active JSConfig object.

        """
        # "fileImport": file_import,
        self.m = {0: {"python": python, "Iterate": Iterate}}
        # Things added to this dict are auto GC'ed
        self.weakmap = WeakValueDictionary()
        self.cur_ffid = 10000
        self.ffid_param = 10000
        self.config = config_obj
        # This toggles if we want to send inspect data for console logging. It's auto
        # disabled when a for loop is active; use `repr` to request logging instead.
        self.m[0]["sendInspect"] = lambda x: setattr(self, "send_inspect", x)
        self.send_inspect = True
        self.current_async_loop = None
        self.my_actions = {}
        # self.executor: Any = None
        self._define_actions()

    def _define_actions(self):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name != "action_selector":
                signature = inspect.signature(method)
                parameters = [k for k in signature.parameters.keys()]
                # log_debug(name,signature,parameters)
                if set(["r", "ffid", "key", "args"]).issubset(parameters):
                    # log_debug("is_subset")
                    self.my_actions[name] = method
                if set(["r", "ffid", "keys", "args"]).issubset(parameters):
                    # log_debug("is_subset2")
                    self.my_actions[name] = method

    def _queue_push(self, r, key, val, sig=""):
        self.config.event_loop.queue_payload(
            {"c": "pyi", "r": r, "key": key, "val": val, "sig": sig}
        )

    def __str__(self):
        """Return a string representation of the PyInterface object."""
        res = str(self.m)
        return res

    # def set_executor(self, exe: Any):
    #     """Set the current executor object.

    #     Args:
    #         exe (Any): The new executor object to be set.
    #     """
    #     self.executor = exe

    # @property
    # def executor(self):
    #     """Get the executor object currently initalized in JSConfig."""
    #     return self.config.executor

    # @executor.setter
    # def executor(self, executor):
    #     pass

    def action_selector(self, action: str, r: int, ffid: int, key: str, args: List):
        """Selects and calls a method based on the given action name.

        Args:
            action (str): The name of the action corresponding to the method to be called.
            r (int): An integer argument for the selected method.
            ffid (int): An integer argument for the selected method.
            key (str): A string argument for the selected method.
            args (List): A list of arguments for the selected method.

        Returns:
            The result of calling the selected method with the given arguments.

        Raises:
            NoPyiAction: If the given action is not defined in the my_actions dictionary.
        """
        print(action, r, ffid, key, args)
        if action in self.my_actions:
            print("found", action, r, ffid, key, args)
            return self.my_actions[action](r, ffid, key, args)
        raise NoPyiAction(f"There's no method in PYI for action {action}. {r},{ffid},{key},{args}.")

    def assign_ffid(self, what: Any):
        """Assign a new FFID (foreign object reference id) for an object.

        Args:
            what(Any): The object to assign an FFID to.

        Returns:
            int: The assigned FFID.
        """
        # self.cur_ffid += 1
        self.ffid_param += 1
        self.cur_ffid = generate_snowflake(self.ffid_param)
        ffid_snow = self.cur_ffid  # generate_snowflake(self.cur_ffid)
        self.m[ffid_snow] = what
        log_print("NEW FFID ADDED ", ffid_snow, what)
        return ffid_snow

    def length(self, r: int, ffid: int, keys: List, args: Tuple):
        """Gets the length of an object specified by keys,
        and return that value back to NodeJS.

        Args:
            r: The response identifier.
            ffid: The FFID of the object.
            keys: The keys to traverse the object hierarchy.
            args: Additional arguments (not used in this method).

        Raises:
            LookupError: If the property specified by keys does not exist.
        """
        v = self.m[ffid]
        for key in keys:
            if type(v) in (dict, tuple, list):
                v = v[key]
            elif hasattr(v, str(key)):
                v = getattr(v, str(key))
            elif hasattr(v, "__getitem__"):
                try:
                    v = v[key]
                except LookupError as le:
                    raise LookupError(
                        f"Property '{fix_key(key)}' does not exist on {repr(v)}"
                    ) from le
            else:
                raise LookupError(f"Property '{fix_key(key)}' does not exist on {repr(v)}")
        l = len(v)
        self._queue_push(r, "num", l)

    def init(self, r: int, ffid: int, key: str, args: Tuple):
        """Initialize an object on the Python side, assign an FFID to it, and
        return that object back to NodeJS.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            key (str): The key to access the object.
            args (Tuple): Additional arguments.

        """
        v = self.m[ffid](*args)
        ffid = self.assign_ffid(v)
        self._queue_push(r, "inst", ffid)

    def call(self, r: int, ffid: int, keys: List, args: Tuple, kwargs: Dict, invoke=True):
        """Call a method or access a property of an object on the python side,
        and return the result back to NodeJS.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            keys (List): The keys to access the object.
            args (Tuple): The method arguments.
            kwargs (Dict): Keyword arguments.
            invoke (bool): Whether to invoke a method.

        """
        v = self.m[ffid]

        # Subtle differences here depending on if we want to call or get a property.
        # Since in Python, items ([]) and attributes (.) function differently,
        # when calling first we want to try . then []
        # For example with the .append function we don't want ['append'] taking
        # precedence in a dict. However if we're only getting objects, we can
        # first try bracket for dicts, then attributes.
        if invoke:
            log_debug("INVOKING MODE %s,%s,%s,%s", v, type(v), str(repr(keys)), str(repr(args)))
            for key in keys:
                t = getattr(v, str(key), None)

                log_debug("GET MODE %s,%s,%s,%s", v, type(v), str(key), str(args))
                if t:
                    v = t
                elif hasattr(v, "__getitem__"):
                    try:
                        v = v[key]
                    except LookupError as le:
                        raise LookupError(
                            f"Property '{fix_key(key)}' does not exist on {repr(v)}"
                        ) from le
                else:
                    raise LookupError(f"Property '{fix_key(key)}' does not exist on {repr(v)}")
        else:
            for key in keys:
                if type(v) in (dict, tuple, list):
                    v = v[key]
                elif hasattr(v, str(key)):
                    v = getattr(v, str(key))
                elif hasattr(v, "__getitem__"):
                    try:
                        v = v[key]
                    except LookupError as le:
                        raise LookupError(
                            f"Property '{fix_key(key)}' does not exist on {repr(v)}"
                        ) from le
                else:
                    raise LookupError(f"Property '{fix_key(key)}' does not exist on {repr(v)}")

        # Classes when called will return void, but we need to return
        # object to JS.
        was_class = False
        if invoke:
            if inspect.iscoroutinefunction(v):
                if self.current_async_loop is None:
                    raise NoAsyncLoop(
                        "Tried to call a coroutine callback without setting the asyncio loop!  Use 'await set_async_loop()' somewhere in your code!"
                    )
                future = asyncio.run_coroutine_threadsafe(
                    v(*args, **kwargs), self.current_async_loop
                )
                v = future.result()
            else:
                if inspect.isclass(v):
                    was_class = True
                log_info("INVOKING %s,%s,%s", v, type(v), was_class)
                v = v(*args, **kwargs)
        typ = type(v)
        if typ is str:
            self._queue_push(r, "string", v)
            return
        if typ is int or typ is float or (v is None) or (v is True) or (v is False):
            self._queue_push(r, "int", v)
            return
        if inspect.isclass(v) or isinstance(v, type):
            # generate a new ffid.
            self._queue_push(r, "class", self.assign_ffid(v), self.make_signature(v))
            return
        if callable(v):  # anything with __call__
            self._queue_push(r, "fn", self.assign_ffid(v), self.make_signature(v))
            return
        if (typ is dict) or (inspect.ismodule(v)) or was_class:  # "object" in JS speak
            self._queue_push(r, "obj", self.assign_ffid(v), self.make_signature(v))
            return
        if typ is list:
            self._queue_push(r, "list", self.assign_ffid(v), self.make_signature(v))
            return
        if hasattr(v, "__class__"):  # numpy generator can't be picked up without this
            self._queue_push(r, "class", self.assign_ffid(v), self.make_signature(v))
            return
        self._queue_push(r, "void", self.cur_ffid)

    # Same as call just without invoking anything, and args
    # would be null
    def get(self, r: int, ffid: int, keys: List, args: Tuple) -> Any:
        """Use call to get a specific property of a python object.
        That property is returned to NodeJS.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            keys (List): The keys to access the object.
            args (Tuple): Additional arguments.

        Returns:
            Any: The value of the property.

        """
        self.call(r, ffid, keys, [], {}, invoke=False)
        return None

    def inspect(self, r: int, ffid: int, keys: List, args: Tuple):
        """Inspect an object and send the representation to NodeJS.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            keys (List): The keys to access the object.
            args (Tuple): Additional arguments.

        """
        v = self.m[ffid]
        for key in keys:
            v = getattr(v, key, None) or v[key]
        s = repr(v)
        self._queue_push(r, "", s)

    # no ACK needed
    def free(self, r: int, ffid: int, key: str, args: List):
        """
        Free the resources associated with  foreign object reference IDs.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            key (str): The key for the operation.
            args (List[int]): List of foreign object reference IDs to free.

        """
        log_debug("free: %s, %s, %s, %s", r, ffid, key, args)
        log_debug(str(self))
        for i in args:
            if i not in self.m:
                continue
            log_debug(f"purged {i}")
            del self.m[i]
        log_debug(str(self))

    def make_signature(self, what: Any) -> str:
        """Generate a signature for an object.

        Args:
            what (Any): The object to generate the signature for.

        Returns:
            str: The generated signature.

        """
        if self.send_inspect:
            return repr(what)
        return ""

    def read(self):
        # Unused and commenting out
        # because apiin isn't defined.
        # data = apiin.readline()
        # if not data:
        #     exit()
        # j = json.loads(data)
        # return j
        pass

    def Set(self, r: int, ffid: int, keys: List, args: Tuple):
        """Set a value of an object.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            keys (List): The keys to access the object.
            args (Tuple): Additional arguments.

        """
        v = self.m[ffid]
        on, val = args
        for key in keys:
            if type(v) in (dict, tuple, list):
                v = v[key]
            elif hasattr(v, str(key)):
                v = getattr(v, str(key))
            else:
                try:
                    v = v[key]
                except LookupError as e:
                    raise LookupError(
                        f"Property '{fix_key(key)}' does not exist on {repr(v)}"
                    ) from e
        if type(v) in (dict, tuple, list, set):
            v[on] = val
        else:
            setattr(v, on, val)
        self._queue_push(r, "void", self.cur_ffid)

    def json_to_python(self, json_input, lookup_key):
        """Convert special JSON objects to Python methods"""
        iterator = None
        if isinstance(json_input, dict):
            iterator = json_input.items()
        elif isinstance(json_input, list):
            iterator = enumerate(json_input)
        else:
            return
        for k, v in iterator:
            if isinstance(v, dict) and (lookup_key in v):
                ffid = v[lookup_key]
                json_input[k] = self.config.new_proxy(ffid)
            else:
                self.json_to_python(v, lookup_key)

    def pcall(self, r: int, ffid: int, key: str, args: Tuple, set_attr: bool = False):
        """Call a method or set a value of an object.

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            key (str): The key to access the object.
            args (Tuple): Additional arguments.
            set_attr (bool): Whether to set an attribute of the object.

        """

        self.json_to_python(args, "ffid")
        pargs, kwargs = args
        if set_attr:
            self.Set(r, ffid, key, pargs)
        else:
            self.call(r, ffid, key, pargs, kwargs or {})

    def setval(self, r: int, ffid: int, key: str, args: Tuple):
        """Set a value of an object.

        (calls pcall, but with set_attr set to True.)

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            key (str): The key to access the object.
            args (Tuple): Additional arguments.

        """
        return self.pcall(r, ffid, key, args, set_attr=True)

    # This returns a primitive version (JSON-serialized) of the object
    # including arrays and dictionary/object maps, unlike what the .get
    # and .call methods do where they only return numeric/strings as
    # primitive values and everything else is an object refrence.
    def value(self, r: int, ffid: int, keys: List, args: Tuple):
        """Retrieve the primitive representation of an object,
        and send it back to Node.JS

        Args:
            r (int): The request ID.
            ffid (int): The foreign object reference ID.
            keys (List): The keys to access the object.
            args (Tuple): Additional arguments.

        """
        v = self.m[ffid]

        for key in keys:
            t = getattr(v, str(key), None)
            if t is None:
                v = v[key]  # If you get an error here, you called an undefined property
            else:
                v = t

        self._queue_push(r, "ser", v)

    def process_and_assign_reply_values(self, jsresponse: Dict[str, Any], wanted: Dict[str, Any]):
        """Assign FFIDs to any non-primitive objects within the wanted dictionary."""
        for request_id in jsresponse["val"]:
            ffid = jsresponse["val"][request_id]
            self.m[ffid] = wanted["wanted"][int(request_id)]
            # This logic just for Event Emitters
            try:
                if hasattr(self.m[ffid], "__call__"):
                    if inspect.ismethod(self.m[ffid]):
                        log_info("this is a method")
                    else:
                        setattr(self.m[ffid], "iffid", ffid)
            except Exception as e:  # pylint: disable=broad-except
                log_warning("There was an issue with , %s", e)  # pylint: disable=broad-except

    def onMessage(self, r: int, action: str, ffid: int, key: str, args: List):
        """Determine which action to preform based on the
         action string, and execute the action.

        Args:
            r (int): The request ID.
            action (str): The action to be executed.
            ffid (int): The foreign object reference ID.
            key (str): The key for the operation.
            args (List): List of arguments for the action.

        """
        # current valid acts:
        # length, get, setval,pcall, inspect, value, free
        try:
            return self.action_selector(action, r, ffid, key, args)
            # return getattr(self, action)(r, ffid, key, args)
        except Exception:  # pylint: disable=broad-except
            self._queue_push(r, "error", "", traceback.format_exc())

    def inbound(self, j: Dict[str, Any]):
        """Extract the message arguments from J, and call onMessage.

        Args:
            j (Dict[str, Any]): The incoming data as a dictionary.

        """
        log_info("PYI, %s", j)

        # print(j)
        # thread_id = threading.current_thread().ident
        # print('threadid',thread_id,"INBOUND PYI: ",j)
        return self.onMessage(j["r"], j["action"], j["ffid"], j["key"], j["val"])

    def get_pyobj_from_ffid(self, ffid: int) -> Any:
        """Get a python object stored the 'm' dictionary with ffid.

        Args:
            ffid(int): FFID of python object to get.

        Returns:
            Any - A (complex) Python Object of any type.

        """
        return self.m[ffid]

    async def inbound_a(self, j: Dict[str, Any]):
        """Extract the message arguments from J, and call onMessage.  asyncronous.

        Args:
            j (Dict[str, Any]): The incoming data as a dictionary.

        """
        await asyncio.to_thread(self.inbound, j)
