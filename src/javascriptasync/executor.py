from __future__ import annotations
from typing import TYPE_CHECKING
import asyncio
import time
from typing import Any, Dict, Tuple

from .json_patch import CustomJSONCountEncoder

from .core.abc import EventObject

if TYPE_CHECKING:
    from .configjs import JSConfig

from .errorsjs import BridgeTimeoutAsync, JavaScriptError, BridgeTimeout


# from .config import JSConfig
from .util import generate_snowflake, SnowflakeMode
from .core.jslogging import log_debug, log_info
from .core.abc import Request


class Executor:
    """
    This is the Executor, something that sits in the middle of the Bridge and is the interface for
    Python to JavaScript. This is also used by the bridge to call Python from Node.js.

    Attributes:
        config (JSConfig): Reference to the active JSConfig object.
        i (int): A unique id for generating request ids.

    """

    def __init__(self, config_obj: JSConfig):
        """
        Initializer for the executor.

        Args:
            config_obj (JSConfig): JSConfig object reference.

        Attributes:
            config (JSConfig): The active JSConfig object.
            i (int): A unique id for generating request ids.
        """
        self.config: JSConfig = config_obj

        self.i = 0

    def ipc(self, action: str, ffid: int, attr: Any, args=None) -> Request:
        """
        Interacts with JavaScript context based on specified actions.

        Args:
            action (str): The action to be taken (can be "get", "init", "inspect", "serialize", "set", "keys").
                            (Only 'get','inspect','serialize',and 'keys' are used elsewhere in code though.).
            ffid (int): The foreign Object Reference ID.
            attr (Any): Attribute to be passed into the key field
            args (Any, optional): Additional parameters for init and set actions

        Returns:
            res: The response after executing the action.
        """
        self.i += 1

        r = generate_snowflake(
            self.i, SnowflakeMode.pyrid
        )  # unique request ts, acts as ID for response
        l = None  # the lock
        req: Request = Request.create_by_action(r, action, ffid, attr, args)
        l = self.config.event_loop.queue_request(r, req)

        if not l.wait(10):
            l.timeout_flag()
            raise BridgeTimeout(f"Timed out accessing '{attr}'", action, ffid, attr)
        res = l.get_data()

        if res.error_state():
            raise JavaScriptError(attr, res["error"])
        return res

    async def ipc_async(self, action: str, ffid: int, attr: Any, args=None) -> Request:
        """
        Async Variant of ipc.  Interacts with JavaScript context based on specified actions.

        Args:
            action (str): The action to be taken (can be "get", "init", "inspect", "serialize", "set", "keys").
                            (Only 'get','inspect','serialize',and 'keys' are used elsewhere in code though.).
            ffid (int): The foreign Object Reference ID.
            attr (Any): Attribute to be passed into the key field
            args (Any, optional): Additional parameters for init and set actions

        Returns:
            res: The response after executing the action.
        """
        timeout = 10
        self.i += 1
        r = generate_snowflake(
            self.i, SnowflakeMode.pyrid
        )  # unique request ts, acts as ID for response
        l = None  # the lock

        req: Request = Request.create_by_action(r, action, ffid, attr, args)
        l = await self.config.event_loop.queue_request_a(r, req)
        try:
            await asyncio.wait_for(l.wait(), timeout)
        except asyncio.TimeoutError as time_exc:
            l.timeout_flag()
            raise asyncio.TimeoutError(
                f"{ffid},{action}:Timed out accessing '{attr}'"
            ) from time_exc
        res = l.get_data()

        if res.error_state():
            raise JavaScriptError(attr, res["error"])
        return res

    def _prepare_pcall_request(
        self, request: Request, forceRefs: bool = False
    ) -> Tuple[Dict[str, Any], str, Dict[int, Any], int]:
        """
        Prepare the preliminary request for the pcall function.

        Args:
            request (Request):request object generated for the pcall method.  contains:
                ffid (int): Foreign Object Reference ID.
                action (str): The action to be executed. (can be "get", "init", "inspect", "serialize", "set", "keys", or "call")
                            (NOTE: ONLY set, init, and call have been used with Pcall!)
                attr (Any): Attribute to be passed into the 'key' field
                args (Tuple[Any]): Arguments for the action to be executed.
            forceRefs (bool): Whether to force references to python side objects passed into args.
                              Used for evaluateWithContext.

        Returns:
            (dict, str, dict,int): The preliminary request packet and the dictionary of wanted non-primitive values.
        """
        # ffid: int, action: str, attr: Any, args: Tuple[Any],
        wanted = {}
        call_resp_id, ffid_resp_id = generate_snowflake(
            self.i + 1, SnowflakeMode.pyrid
        ), generate_snowflake(self.i + 2, SnowflakeMode.pyrid)
        self.i += 2
        # self.ctr = 0
        # self.expectReply = False
        # p=1 means we expect a reply back, not used at the moment, but
        # in the future as an optimization we could skip the wait if not needed
        request.r = call_resp_id
        # packet = {"r": call_resp_id, "action": action, "ffid": ffid, "key": attr, "args": args}
        # Using it's own encoder to slim down on size.

        # for a in args:  print(a,type(a))
        encoder = CustomJSONCountEncoder()
        if forceRefs:
            payload = encoder.encode_refs(request, request.args)
        else:
            # use a custom json encoder.
            payload = encoder.encode(request)
        wanted = encoder.get_wanted()

        return request, payload, wanted, ffid_resp_id

    def _process_expected_reply(
        self, packet: Request, wanted: Dict[str, Any], lock: EventObject, ffid_resp_id: int
    ):
        """ """
        pre = lock.get_data()
        log_info(
            "ProxyExec got response: call_resp_id:%s ffid_resp_id:%s, %s",
            str(packet.r),
            str(ffid_resp_id),
            pre,
        )

        if pre.error_state():
            raise JavaScriptError(packet.key, pre["error"])

        self.config.pyi.process_and_assign_reply_values(pre, wanted)

        # barrier.wait()

    # forceRefs=True means that the non-primitives in the second parameter will not be recursively
    # parsed for references. It's specifcally for eval_js.
    async def pcallalt(self, request: Request, *, timeout: int = 1000, forceRefs: bool = False):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the foreign Object Reference ID, attribute and arguments Python wants to call.
        For each of the non-primitive objects in the arguments,
        in the preliminary request we "request" an FFID from JS
        which is the authoritative side for FFIDs.
        Only it may assign them; we must request them. Once
        JS recieves the pcall, it searches the arguments and assigns FFIDs for everything,
        hen returns the IDs in a response.
        We use these IDs to store the non-primitive values into our ref map.
        On the JS side, it creates Proxy classes for each of the requests in the pcall,
        once they get destroyed, a free call is sent to Python
        where the ref is removed from our ref map to allow for
        normal GC by Python. Finally, on the JS side it executes
        the function call without waiting for Python.
        A init/set operation on a JS object also uses pcall as the semantics are the same.
        Args:

            request (Request): A Request object containing:
                ffid (int): unique foreign object reference id.
                action (str): The action to be executed.   (can be "init", "set", or "call")
                attr (Any): attribute to be passed into the 'key' field
                args (Tuple[Any]): Arguments for the action to be executed.
            timeout (int, optional): Timeout duration. Defaults to 1000.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            (Any, Any): The response key and value.
        """
        packet, payload, wanted, ffid_resp_id = self._prepare_pcall_request(request, forceRefs)

        # call_resp_id = packet["r"]

        l = await self.config.event_loop.queue_request_a(packet.r, payload)

        if wanted["exp_reply"]:
            # If any non-primitives were sent, then
            # we need to wait for a FFID assignment response if
            # otherwise skip

            l2 = await self.config.event_loop.await_response_a(ffid_resp_id)
            try:
                await asyncio.wait_for(l2.wait(), timeout)
            except asyncio.TimeoutError as e:
                l2.timeout_flag()
                raise BridgeTimeoutAsync(
                    f"Expected reply with ffid '{ffid_resp_id}' on '{request.key}' timed out.",
                    action=request.action,
                    ffid=request.ffid,
                    attr=request.key,
                ) from e
            self._process_expected_reply(packet, wanted, l2, ffid_resp_id)

        now = time.time()

        try:
            # print(timeout)
            await asyncio.wait_for(l.wait(), timeout)
        except asyncio.TimeoutError as time_exc:
            l.timeout_flag()

            print("elapsed is", time.time() - now)
            raise BridgeTimeoutAsync(
                f"Call to '{request.key}' timed out.",
                action=request.action,
                ffid=request.ffid,
                attr=request.key,
            ) from time_exc

        log_debug(
            "ProxyExec: lock:%s,call_resp_id:%s ffid_resp_id:%s, timeout:%s, took: %s",
            str(l),
            str(packet.r),
            str(ffid_resp_id),
            timeout,
            time.time() - now,
        )

        res = l.get_data()

        if res.error_state():
            raise JavaScriptError(request.key, res["error"])
        return res["key"], res["val"]

    def pcall(self, request: Request, *, timeout: int = 1000, forceRefs: bool = False):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the foreign Object Reference ID, attribute and arguments Python wants to call.
        For each of the non-primitive objects in the arguments,
        in the preliminary request we "request" an FFID from JS
        which is the authoritative side for FFIDs.
        Only it may assign them; we must request them. Once
        JS recieves the pcall, it searches the arguments and assigns FFIDs for everything,
        hen returns the IDs in a response.
        We use these IDs to store the non-primitive values into our ref map.
        On the JS side, it creates Proxy classes for each of the requests in the pcall,
        once they get destroyed, a free call is sent to Python
        where the ref is removed from our ref map to allow for
        normal GC by Python. Finally, on the JS side it executes
        the function call without waiting for Python.
        A init/set operation on a JS object also uses pcall as the semantics are the same.
        Args:

            request (Request): A Request object containing:
                ffid (int): unique foreign object reference id.
                action (str): The action to be executed.   (can be "init", "set", or "call")
                attr (Any): attribute to be passed into the 'key' field
                args (Tuple[Any]): Arguments for the action to be executed.
            timeout (int, optional): Timeout duration. Defaults to 1000.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            (Any, Any): The response key and value.
        """
        # ffid: int, action: str, attr: Any, args: Tuple[Any]
        packet, payload, wanted, ffid_resp_id = self._prepare_pcall_request(request, forceRefs)

        # call_resp_id = packet["r"]
        l = self.config.event_loop.queue_request(packet.r, payload)
        # We only have to wait for a FFID assignment response if
        # we actually sent any non-primitives, otherwise skip
        if wanted["exp_reply"]:
            l2 = self.config.event_loop.await_response(ffid_resp_id)

            if not l2.wait(timeout):
                l2.timeout_flag()
                raise BridgeTimeout(
                    f"Call to '{request.key}' timed out.",
                    action=request.action,
                    ffid=request.ffid,
                    attr=request.key,
                )

            self._process_expected_reply(packet, wanted, l2, ffid_resp_id)

        now = time.time()

        log_debug(
            "ProxyExec: lock:%s,call_resp_id:%s ffid_resp_id:%s, timeout:%s",
            str(l),
            str(packet.r),
            str(ffid_resp_id),
            timeout,
        )
        if not l.wait(timeout):
            l.timeout_flag()
            print("elapsed is", time.time() - now)
            raise BridgeTimeout(
                f"Call to '{request.key}' timed out.",
                action=request.action,
                ffid=request.ffid,
                attr=request.key,
            )
        elapsed = time.time() - now
        log_debug(
            "ProxyExec: lock:%s,call_resp_id:%s ffid_resp_id:%s, timeout:%s, took: %s",
            str(l),
            str(packet.r),
            str(ffid_resp_id),
            timeout,
            elapsed,
        )
        res = l.get_data()

        if res.error_state():
            raise JavaScriptError(request.key, res["error"])
        return res["key"], res["val"]

    def getProp(self, ffid: int, method: str):
        """
        Get a property from a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to retrieve.

        Returns:
            tuple: The response key and value.
        """

        # print("getprop","get", ffid:int, method:str)
        resp = self.ipc("get", ffid, method)
        return resp["key"], resp["val"]

    async def getPropAsync(self, ffid: int, method: str):
        """
        Get a property from a JavaScript object asyncronously

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method/property to retrieve.

        Returns:
            tuple: The response key and value.
        """
        resp = await self.ipc_async("get", ffid, method)
        return resp["key"], resp["val"]

    def setProp(self, ffid: int, method: str, val: Any):
        """
        Set a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to set.
            val (Any): The value to set.

        Returns:
            bool: True if successful.
        """
        r = Request.create_for_pcall(ffid, "set", method, [val])
        self.pcall(r)
        return True

    async def setPropAsync(self, ffid: int, method: str, val: Any):
        """
        Set a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to set.
            val (Any): The value to set.

        Returns:
            bool: True if successful.
        """
        r = Request.create_for_pcall(ffid, "set", method, [val])
        await self.pcallalt(r)
        return True

    def callProp(self, ffid: int, method: str, args: Tuple[Any], *, timeout=None, forceRefs=False):
        """
        Call a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to call.
            args (Tuple[Any]): Arguments for the call.
            timeout (int, optional): Timeout duration. Defaults to None.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            tuple: The response key and value.
        """
        # print("PROP",ffid, "call", method, args, timeout, forceRefs)
        r = Request.create_for_pcall(ffid, "call", method, args)
        resp = self.pcall(r, timeout=timeout, forceRefs=forceRefs)
        return resp

    def initProp(self, ffid: int, method: str, args: Tuple[Any]):
        """
        Initialize a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to initialize.
            args (Tuple[Any]): Arguments for the initialization.

        Returns:
            tuple: The response key and value.
        """
        r = Request.create_for_pcall(ffid, "init", method, args)
        resp = self.pcall(r)
        return resp

    async def callPropAsync(
        self, ffid: int, method: str, args: Tuple[Any], *, timeout=None, forceRefs=False
    ):
        """
        Call a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to call.
            args (Tuple[Any]): Arguments for the call.
            timeout (int, optional): Timeout duration. Defaults to None.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            tuple: The response key and value.
        """
        r = Request.create_for_pcall(ffid, "call", method, args)
        resp = await self.pcallalt(r, timeout=timeout, forceRefs=forceRefs)
        return resp

    async def initPropAsync(self, ffid: int, method: str, args: Tuple[Any]):
        """
        Initialize a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to initialize.
            args (Tuple[Any]): Arguments for the initialization.

        Returns:
            tuple: The response key and value.
        """
        r = Request.create_for_pcall(ffid, "init", method, args)
        resp = await self.pcallalt(r)
        return resp

    def inspect(self, ffid: int, mode: str):
        """
        Inspect a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            mode (str): The inspection mode (e.g., "str", "repr").

        Returns:
            Any: The inspected value.
        """
        resp = self.ipc("inspect", ffid, mode)
        return resp["val"]

    def keys(self, ffid):
        """
        Get the keys of a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.

        Returns:
            list: The list of keys.
        """
        return self.ipc("keys", ffid, "")["keys"]

    def free(self, ffid):
        """
        Free a local JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
        """
        self.config.event_loop.free_ffid(ffid)

    def get(self, ffid):
        """
        Get a local JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.

        Returns:
            Any: The JavaScript object.
        """
        return self.config.pyi.get_pyobj_from_ffid(ffid)
