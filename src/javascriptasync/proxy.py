from __future__ import annotations
import asyncio
import inspect
import time, threading, json, sys, os, traceback
from typing import Any, Callable, Coroutine, Literal, Optional, Tuple, Union
from . import config, json_patch

from .errors import JavaScriptError, NoAsyncLoop
from .events import EventLoop


from .util import generate_snowflake, SnowflakeMode
from .logging import logs, print_path_depth


class Executor:
    """
    This is the Executor, something that sits in the middle of the Bridge and is the interface for
    Python to JavaScript. This is also used by the bridge to call Python from Node.js.

    Attributes:
        conf (config.JSConfig): Reference to the active JSConfig object.
        loop (EventLoop): The event loop for handling JavaScript events.
        queue (callable): shortcut to EventLoop.queue_request
        i (int): A unique id for generating request ids.
        self.bridge(PyInterface): shortcut to EventLoop.pyi
    """

    def __init__(self, config_obj: config.JSConfig, loop: EventLoop):
        self.conf = config_obj
        self.loop = loop
        loop.pyi.executor = self
        self.queue = loop.queue_request
        self.i = 0
        self.bridge = self.loop.pyi

    def ipc(self, action, ffid, attr, args=None):
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

        r = generate_snowflake(self.i, SnowflakeMode.pyrid)  # unique request ts, acts as ID for response
        l = None  # the lock
        if action == "get":  # return obj[prop]
            l = self.queue(r, {"r": r, "action": "get", "ffid": ffid, "key": attr})
        if action == "init":  # return new obj[prop]
            l = self.queue(r, {"r": r, "action": "init", "ffid": ffid, "key": attr, "args": args})
        if action == "inspect":  # return require('util').inspect(obj[prop])
            l = self.queue(r, {"r": r, "action": "inspect", "ffid": ffid, "key": attr})
        if action == "serialize":  # return JSON.stringify(obj[prop])
            l = self.queue(r, {"r": r, "action": "serialize", "ffid": ffid})
        if action == "set":
            l = self.queue(r, {"r": r, "action": "set", "ffid": ffid, "key": attr, "args": args})
        if action == "keys":
            l = self.queue(r, {"r": r, "action": "keys", "ffid": ffid})

        if not l.wait(10):
            if not self.conf.event_thread:
                print(self.conf.dead)
            print("Timed out", action, ffid, attr, repr(self.conf.event_thread))
            raise Exception(f"Timed out accessing '{attr}'")
        res, barrier = self.loop.get_response_from_id(r)
        barrier.wait()
        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res

    async def ipc_async(self, action, ffid, attr, args=None):
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
        r = generate_snowflake(self.i, SnowflakeMode.pyrid)  # unique request ts, acts as ID for response
        l = None  # the lock
        amode = True
        aloop = asyncio.get_event_loop()
        if action == "get":  # return obj[prop]
            l = self.loop.queue_request(
                r, {"r": r, "action": "get", "ffid": ffid, "key": attr}, asyncmode=amode, loop=aloop
            )
        if action == "init":  # return new obj[prop]
            l = self.loop.queue_request(
                r, {"r": r, "action": "init", "ffid": ffid, "key": attr, "args": args}, asyncmode=amode, loop=aloop
            )
        if action == "inspect":  # return require('util').inspect(obj[prop])
            l = self.loop.queue_request(
                r, {"r": r, "action": "inspect", "ffid": ffid, "key": attr}, asyncmode=amode, loop=aloop
            )
        if action == "serialize":  # return JSON.stringify(obj[prop])
            l = self.loop.queue_request(r, {"r": r, "action": "serialize", "ffid": ffid}, asyncmode=amode, loop=aloop)
        if action == "set":
            l = self.loop.queue_request(
                r, {"r": r, "action": "set", "ffid": ffid, "key": attr, "args": args}, asyncmode=amode, loop=aloop
            )
        if action == "keys":
            l = self.loop.queue_request(r, {"r": r, "action": "keys", "ffid": ffid}, asyncmode=amode, loop=aloop)
        try:
            await asyncio.wait_for(l.wait(), timeout)
        except asyncio.TimeoutError as time_exc:
            if not self.conf.event_thread:
                print(self.conf.dead)
            print("Timed out", action, ffid, attr, repr(self.conf.event_thread))
            raise asyncio.TimeoutError(f"Timed out accessing '{attr}'") from time_exc

        res, barrier = self.loop.get_response_from_id(r)
        barrier.wait()
        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res

    def _prepare_pcall_request(self, ffid, action, attr, args, forceRefs):
        """
        Prepare the preliminary request for the pcall function.

        Args:
            ffid (int): Unknown purpose, needs more context.
            action (str): The action to be executed. (can be "get", "init", "inspect", "serialize", "set", "keys", or "call")
                        (NOTE: ONLY set, init, and call have been seen elsewhere in code!)
            attr (Any): Attribute to be passed into the 'key' field
            args (Tuple[Any]): Arguments for the action to be executed.
            forceRefs (bool): Whether to force refs.

        Returns:
            (dict, dict): The preliminary request packet and the dictionary of wanted non-primitive values.
        """
        wanted = {}
        self.ctr = 0
        callRespId, ffidRespId = generate_snowflake(self.i + 1, SnowflakeMode.pyrid), generate_snowflake(
            self.i + 2, SnowflakeMode.pyrid
        )
        self.i += 2
        self.expectReply = False
        # p=1 means we expect a reply back, not used at the moment, but
        # in the future as an optimization we could skip the wait if not needed
        packet = {"r": callRespId, "action": action, "ffid": ffid, "key": attr, "args": args}

        def ser(arg):
            if hasattr(arg, "ffid"):
                self.ctr += 1
                return {"ffid": arg.ffid}
            else:
                # Anything we don't know how to serialize -- exotic or not -- treat it as an object
                self.ctr += 1
                self.expectReply = True
                wanted[self.ctr] = arg
                return {"r": self.ctr, "ffid": ""}

        if forceRefs:
            _block, _locals = args
            packet["args"] = [args[0], {}]
            flocals = packet["args"][1]
            for k in _locals:
                v = _locals[k]
                if (type(v) is int) or (type(v) is float) or (v is None) or (v is True) or (v is False):
                    flocals[k] = v
                else:
                    flocals[k] = ser(v)
            packet["p"] = self.ctr
            payload = json.dumps(packet)
        else:
            payload = json.dumps(packet, default=ser)
            # A bit of a perf hack, but we need to add in the counter after we've already serialized ...
            payload = payload[:-1] + f',"p":{self.ctr}}}'

        return packet, payload, wanted, ffidRespId

    # forceRefs=True means that the non-primitives in the second parameter will not be recursively
    # parsed for references. It's specifcally for eval_js.
    async def pcallalt(
        self, ffid: int, action: str, attr: Any, args: Tuple[Any], *, timeout: int = 1000, forceRefs: bool = False
    ):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the foreign Object Reference ID, attribute, and arguments that Python would like to call. For each of the
        non-primitive objects in the arguments, in the preliminary request, we "request" an FFID from JS
        which is the authoritative side for FFIDs. Only it may assign them; we must request them. Once
        JS receives the pcall, it searches the arguments and assigns FFIDs for everything, then returns
        the IDs in a response. We use these IDs to store the non-primitive values into our ref map.
        On the JS side, it creates Proxy classes for each of the requests in the pcall, once they get
        destroyed, a free call is sent to Python where the ref is removed from our ref map to allow for
        normal GC by Python. Finally, on the JS side, it executes the function call without waiting for
        Python. An init/set operation on a JS object also uses pcall as the semantics are the same.

        Args:
            ffid (int): Unknown purpose, needs more context.
            action (str): The action to be executed. (can be "init", "set", or "call")
            attr (Any): Attribute to be passed into the 'key' field
            args (Tuple[Any]): Arguments for the action to be executed.
            timeout (int, optional): Timeout duration. Defaults to 1000.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            (Any, Any): The response key and value.
        """
        packet, payload, wanted, ffidRespId = self._prepare_pcall_request(ffid, action, attr, args, forceRefs)

        callRespId = packet["r"]

        l = self.loop.queue_request(callRespId, payload, asyncmode=True, loop=asyncio.get_event_loop())

        if self.expectReply:
            """If any non-primitives were sent, then
            we need to wait for a FFID assignment response if
            otherwise skip"""
            l2 = self.loop.await_response(ffidRespId, asyncmode=True, loop=asyncio.get_event_loop())
            try:
                await asyncio.wait_for(l2.wait(), timeout)
            except asyncio.TimeoutError:
                raise Exception("Execution timed out")

            pre, barrier = self.loop.get_response_from_id(ffidRespId)
            logs.debug("ProxyExec:callRespId:%s ffidRespId:%s", str(callRespId), str(ffidRespId))
            # pre, barrier = self.loop.responses[ffidRespId]
            # del self.loop.responses[ffidRespId]

            if "error" in pre:
                raise JavaScriptError(attr, pre["error"])

            for requestId in pre["val"]:
                ffid = pre["val"][requestId]
                self.bridge.m[ffid] = wanted[int(requestId)]
                # This logic just for Event Emitters
                try:
                    if hasattr(self.bridge.m[ffid], "__call__"):
                        if inspect.ismethod(self.bridge.m[ffid]):
                            logs.info("this is a method")
                        else:
                            setattr(self.bridge.m[ffid], "iffid", ffid)
                except Exception as e:
                    logs.warning("There was an in pcallalt, %s", e)
                    pass

            barrier.wait()
        now = time.time()
        logs.debug(
            "ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s",
            str(l),
            str(callRespId),
            str(ffidRespId),
            timeout,
        )
        try:
            await asyncio.wait_for(l.wait(), timeout)
        except asyncio.TimeoutError as time_exc:
            if not self.conf.event_thread:
                print(self.conf.dead)
            raise asyncio.TimeoutError(
                f"Call to '{attr}' timed out. Increase the timeout by setting the `timeout` keyword argument."
            ) from time_exc

        elapsed = time.time() - now
        logs.debug(
            "ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s, took: %s",
            str(l),
            str(callRespId),
            str(ffidRespId),
            timeout,
            elapsed,
        )

        res, barrier = self.loop.get_response_from_id(callRespId)
        # res, barrier = self.loop.responses[callRespId]
        # del self.loop.responses[callRespId]

        barrier.wait()

        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res["key"], res["val"]

    def pcall(
        self, ffid: int, action: str, attr: Any, args: Tuple[Any], *, timeout: int = 1000, forceRefs: bool = False
    ):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the foreign Object Reference ID, attribute and arguments that Python would like to call. For each of the
        non-primitive objects in the arguments, in the preliminary request we "request" an FFID from JS
        which is the authoritative side for FFIDs. Only it may assign them; we must request them. Once
        JS recieves the pcall, it searches the arguments and assigns FFIDs for everything, then returns
        the IDs in a response. We use these IDs to store the non-primitive values into our ref map.
        On the JS side, it creates Proxy classes for each of the requests in the pcall, once they get
        destroyed, a free call is sent to Python where the ref is removed from our ref map to allow for
        normal GC by Python. Finally, on the JS side it executes the function call without waiting for
        Python. A init/set operation on a JS object also uses pcall as the semantics are the same.
        Args:
            ffid (int): unique foreign object reference id.
            action (str): The action to be executed.   (can be "init", "set", or "call")
            attr (Any): attribute to be passed into the 'key' field
            args (Tuple[Any]): Arguments for the action to be executed.
            timeout (int, optional): Timeout duration. Defaults to 1000.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            (Any, Any): The response key and value.
        """

        packet, payload, wanted, ffidRespId = self._prepare_pcall_request(ffid, action, attr, args, forceRefs)

        callRespId = packet["r"]
        l = self.loop.queue_request(callRespId, payload)
        # We only have to wait for a FFID assignment response if
        # we actually sent any non-primitives, otherwise skip
        if self.expectReply:
            l2 = self.loop.await_response(ffidRespId)
            if not l2.wait(timeout):
                raise Exception("Execution timed out")
            # pre, barrier = self.loop.responses[ffidRespId]
            pre, barrier = self.loop.get_response_from_id(ffidRespId)
            logs.debug("ProxyExec:callRespId:%s ffidRespId:%s", str(callRespId), str(ffidRespId))

            # del self.loop.responses[ffidRespId]

            if "error" in pre:
                raise JavaScriptError(attr, pre["error"])

            for requestId in pre["val"]:
                ffid = pre["val"][requestId]
                self.bridge.m[ffid] = wanted[int(requestId)]
                # This logic just for Event Emitters
                try:
                    if hasattr(self.bridge.m[ffid], "__call__"):
                        if inspect.ismethod(self.bridge.m[ffid]):
                            logs.info("this is a method")
                        else:
                            setattr(self.bridge.m[ffid], "iffid", ffid)
                except Exception as e:
                    logs.warning("There was an issue in pcall, %s", e)
                    pass

            barrier.wait()
        now = time.time()
        logs.debug(
            "ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s",
            str(l),
            str(callRespId),
            str(ffidRespId),
            timeout,
        )

        if not l.wait(timeout):
            if not self.conf.event_thread:
                print(self.conf.dead)
            raise Exception(
                f"Call to '{attr}' timed out. Increase the timeout by setting the `timeout` keyword argument."
            )
        elapsed = time.time() - now
        logs.debug(
            "ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s, took: %s",
            str(l),
            str(callRespId),
            str(ffidRespId),
            timeout,
            elapsed,
        )
        res, barrier = self.loop.get_response_from_id(callRespId)
        # res, barrier = self.loop.responses[callRespId]
        # del self.loop.responses[callRespId]

        barrier.wait()

        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res["key"], res["val"]

    def getProp(self, ffid, method):
        """
        Get a property from a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to retrieve.

        Returns:
            tuple: The response key and value.
        """
        resp = self.ipc("get", ffid, method)
        return resp["key"], resp["val"]

    async def getPropAsync(self, ffid, method):
        """
        Get a property from a JavaScript object asyncronously

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to retrieve.

        Returns:
            tuple: The response key and value.
        """
        resp = self.ipc("get", ffid, method)
        return resp["key"], resp["val"]

    def setProp(self, ffid, method, val):
        """
        Set a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to set.
            val (Any): The value to set.

        Returns:
            bool: True if successful.
        """
        self.pcall(ffid, "set", method, [val])
        return True

    async def setPropAsync(self, ffid, method, val):
        """
        Set a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to set.
            val (Any): The value to set.

        Returns:
            bool: True if successful.
        """
        await self.pcallalt(ffid, "set", method, [val])
        return True

    def callProp(self, ffid, method, args, *, timeout=None, forceRefs=False):
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
        resp = self.pcall(ffid, "call", method, args, timeout=timeout, forceRefs=forceRefs)
        return resp

    def initProp(self, ffid, method, args):
        """
        Initialize a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to initialize.
            args (Tuple[Any]): Arguments for the initialization.

        Returns:
            tuple: The response key and value.
        """
        resp = self.pcall(ffid, "init", method, args)
        return resp

    async def callPropAsync(self, ffid, method, args, *, timeout=None, forceRefs=False):
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
        resp = await self.pcallalt(ffid, "call", method, args, timeout=timeout, forceRefs=forceRefs)
        return resp

    async def initPropAsync(self, ffid, method, args):
        """
        Initialize a property on a JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.
            method (str): The method to initialize.
            args (Tuple[Any]): Arguments for the initialization.

        Returns:
            tuple: The response key and value.
        """
        resp = await self.pcallalt(ffid, "init", method, args)
        return resp

    def inspect(self, ffid, mode):
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
        self.loop.freeable.append(ffid)

    def get(self, ffid):
        """
        Get a local JavaScript object.

        Args:
            ffid (int): Foreign Object Reference ID.

        Returns:
            Any: The JavaScript object.
        """
        return self.bridge.m[ffid]


INTERNAL_VARS = ["ffid", "_ix", "_exe", "_pffid", "_pname", "_es6", "_asyncmode", "_resolved", "_ops", "_Keys"]


# "Proxy" classes get individually instantiated  for every thread and JS object
# that exists. It interacts with an Executor to communicate.
class Proxy(object):
    """
    "Proxy" classes get individually instantiated every thread and JS object
    that exists. It interacts with an Executor to communicate to the Node.JS instance
    on the other side of the bridge.

    Utilizes magic methods to determine which api calls to make, and is capable of
    operating in an single asyncio mode, when it "stacks" operations together
    instead of executing them right away, running them only with the await keyword
    and .


    Attributes:
        ffid (int): Foreign Object Reference ID.
        _exe (Executor): The executor for communication with JavaScript.
        _ix (int): Index.
        _pffid (int): Property foreign Object Reference ID.
        _pname (str): Property name.
        _es6 (bool): ES6 class flag.
        _asyncmode (bool): asyncronous stacking mode: Operations are assembled into a stack of NodeOp  objects.
        _resolved (dict): Resolved values.
        _Keys (list): List of keys.
    """

    def __init__(self, exe: Executor, ffid, prop_ffid=None, prop_name="", es6=False, amode=False):
        """
        Args:
            exe (Executor): The executor for communication with JavaScript.
            ffid (int): Foreign Object Reference ID.
            prop_ffid (int, optional): Property foreign Object Reference ID. Defaults to None.
            prop_name (str, optional): Property name. Defaults to "".
            es6 (bool, optional): ES6 class flag. Defaults to False.

        """
        logs.debug("new Proxy: %s, %s,%s,%s,%s", exe, ffid, prop_ffid, prop_name, es6)
        self.ffid = ffid
        self._exe: Executor = exe
        self._ix = 0
        #
        self._pffid = prop_ffid if (prop_ffid != None) else ffid
        self._pname = prop_name
        self._es6 = es6
        self._resolved = {}
        self._ops = []
        self._Keys = None
        self._asyncmode = amode

        logs.debug("new Proxy init done: %s, %s,%s,%s,%s", exe, ffid, prop_ffid, prop_name, es6)

    def _config(self):
        """Access the JSConfig object reference within the executor."""
        return self._exe.conf

    def _loop(self):
        """Access the EventLoop reference within the executor."""
        return self._exe.loop

    def toggle_async_chain(self, value: bool):
        """Alias for toggle_async_stack.
        Turn asyncio stacking on or off.

        Args:
            value (bool): set to True to enable asyncio stacking, False to disable.
        """
        self._asyncmode = value

    def toggle_async_stack(self, value: bool):
        """Turn asyncio stacking on or off

        Args:
            value (bool): set to True to enable asyncio stacking, False to disable.
        """
        self._asyncmode = value

    def _call(self, method, methodType, val):
        """
        Helper function for processing the result of a call.

        Args:
            method (str): The method to call.
            methodType (str): The method type.
            val (Any): The value to call.

        Returns:
            Any: The result of the call.
        """
        this = self

        logs.debug("Proxy._call: %s, %s,%s,%s", "MT", method, methodType, val)
        if methodType == "fn":
            return Proxy(self._exe, val, self.ffid, method, amode=self._asyncmode)
        if methodType == "class":
            return Proxy(self._exe, val, es6=True, amode=self._asyncmode)
        if methodType == "obj":
            return Proxy(self._exe, val, amode=self._asyncmode)
        if methodType == "inst":
            return Proxy(self._exe, val, amode=self._asyncmode)
        if methodType == "inste":
            return EventEmitterProxy(self._exe, val, amode=self._asyncmode)
        if methodType == "void":
            return None
        if methodType == "py":
            return self._exe.get(val)
        else:
            return val

    async def call_a(self, *args, timeout=10, forceRefs=False, coroutine=True):
        """
        Coroutine version of the __call__ method.

        Args:
            args: Arguments to pass to the method.
            timeout (int, optional): Timeout duration. Defaults to 10.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            Any: The result of the call.
        """
        logs.debug("calling call_a.  Timeout: %d, Args: %s", timeout, str(args))
        if self._es6:
            mT, v = await self._exe.initPropAsync(self._pffid, self._pname, args)
        else:
            mT, v = await self._exe.callPropAsync(self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs)
        if mT == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, mT, v)

    def call_s(self, *args, timeout=10, forceRefs=False, coroutine=False):
        """
        This function calls/inits a method across the bridge.

        Args:
            args: Arguments to pass to the method.
            timeout (int, optional): Timeout duration. Defaults to 10.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.
            coroutine (bool, optional): Whether to use coroutine. Defaults to False.

        Returns:
            Any: The result of the call.
        """
        if coroutine:
            return self.call_a(*args, timeout=timeout, forceRefs=forceRefs)

        if self._es6:
            mT, v = self._exe.initProp(self._pffid, self._pname, args)
        else:
            mT, v = self._exe.callProp(self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs)
        logs.info("call_s proxy, mT:%s,v:%s.  Timeout: %d, Args: %s", mT, v, timeout, str(args))
        if mT == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, mT, v)

    def __call__(self, *args, timeout=10, forceRefs=False, coroutine=False):
        if self._asyncmode:
            return NodeOp(
                self,
                op="call",
                kwargs={"args": args, "timeout": timeout, "forceRefs": forceRefs, "coroutine": coroutine},
            )
        return self.call_s(*args, timeout=timeout, forceRefs=forceRefs, coroutine=coroutine)

    def __getattr__(self, attr):
        """
        Get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        return self.get(attr)

    def get(self, attr):
        """
        Get an attribute of the linked JavaScript object, or begin a NodeOp
        chain if in asyncmode.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        if self._asyncmode:
            return NodeOp(self, op="get", kwargs={"attr": attr})
        return self.get_attr(attr)

    def __getitem__(self, attr):
        """
        Get an item of the linked JavaScript object.

        Args:
            attr (str): The item name.

        Returns:
            Any: The item value.
        """
        if self._asyncmode:
            return NodeOp(self, op="getitem", kwargs={"attr": attr})
        return self.get_item(attr)

    def __iter__(self):
        """
        Initalize an iterator

        Returns:
            self: The iterator object.
        """

        if self._asyncmode:
            raise Exception("you need to use an asyncronous iterator when in amode.")
            return NodeOp(self, op="iter", kwargs={})
        return self.init_iterator()

    def __next__(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        if self._asyncmode:
            raise Exception("you need to use an asyncronous iterator when in amode.")
            return NodeOp(self, op="next", kwargs={})
        return self.next_item()

    def __aiter__(self):
        """
        Async variant of iterator.
        """
        self._ix = 0
        logs.debug("proxy.init_iterator")
        length = self.get_attr("length")
        if length is None:
            self._Keys = self._exe.keys(self.ffid)
        return self

    # return the next awaitable
    async def __anext__(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        logs.debug("proxy.next_item")
        length = await self.get_a("length")
        if self._Keys:
            if self._ix < len(self._Keys):
                result = self._Keys[self._ix]
                self._ix += 1
                return result
            else:
                raise StopAsyncIteration
        elif self._ix < length:
            result = await self.get_a(self._ix)
            self._ix += 1
            return result
        else:
            raise StopAsyncIteration

    def __setattr__(self, name, value):
        """
        Set an attribute of the linked JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.
        """

        logs.debug("proxy.setattr, name:%s, value:%s", name, value)
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            if self._asyncmode:
                raise Exception("don't use this in amode!  use .set instead!")
            else:
                return self.set(name, value)

    def set(self, name, value):
        """
        Set an attribute of the linked JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.setattr, name:%s, value:%s", name, value)
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            if self._asyncmode:
                return NodeOp(self, op="set", kwargs={"name": name, "value": value})
            else:
                return self.set_attr(name, value)

    def __setitem__(self, name, value):
        """
        Set an item of the linked JavaScript object.

        Args:
            name (str): The item name.
            value (Any): The item value.

        Returns:
            bool: True if successful.
        """
        if self._asyncmode:
            return NodeOp(self, op="setitem", kwargs={"name": name, "value": value})
        return self.set_item(name, value)
        return self.set_item(name, value)
        logs.debug("proxy.setitem, name:%s, value:%s", name, value)
        return self._exe.setProp(self.ffid, name, value)

    def __contains__(self, key):
        """
        Check if a key is contained in the linked JavaScript object.

        Args:
            key (Any): The key to check.

        Returns:
            bool: True if the key is contained, otherwise False.
        """
        return self.contains_key(key)
        logs.debug("proxy.contains, key:%s", key)
        return True if self[key] is not None else False

    def valueOf(self):
        """
        Serialize the linked JavaScript object.

        Returns:
            Any: The "valueOf" value.
        """
        return self.get_value_of()
        ser = self._exe.ipc("serialize", self.ffid, "")

        logs.debug("proxy.valueOf, %s", ser)
        return ser["val"]

    def __str__(self):
        """
        Get a string representation of the linked JavaScript object via an inspect call

        Returns:
            str: The string representation.
        """
        return self.get_str()
        logs.debug("proxy.str")
        return self._exe.inspect(self.ffid, "str")

    def __repr__(self):
        """
        Get a representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The representation.
        """
        return self.get_repr()
        logs.debug("proxy.repr")
        return self._exe.inspect(self.ffid, "repr")

    def __json__(self):
        """
        Get a JSON representation of the linked JavaScript object.

        Returns:
            dict: The JSON representation.
        """
        return self.get_json()
        logs.debug("proxy.json")
        return {"ffid": self.ffid}

    def __del__(self):
        """
        Free the linked JavaScript object.
        """
        return self.free()
        logs.debug("proxy.del")
        self._exe.free(self.ffid)

    def get_s(self, attr):
        """
        Alias for get_attr.

        Get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        logs.debug("proxy.get_attr start %s", attr)
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        methodType, val = self._exe.getProp(self._pffid, attr)
        logs.debug("proxy.get_attr %s, methodType: %s, val %s", attr, methodType, val)
        return self._call(attr, methodType, val)

    def get_attr(self, attr):
        """
        Get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        logs.debug("proxy.get_attr start %s", attr)
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        methodType, val = self._exe.getProp(self._pffid, attr)
        logs.debug("proxy.get_attr %s, methodType: %s, val %s", attr, methodType, val)
        return self._call(attr, methodType, val)

    def set_s(self, name, value):
        """
        Alias for set_attr.

        Get an attribute of the linked JavaScript object.
        Syncronous.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """

    def set_attr(self, name, value):
        """
        Set an attribute of the linked JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.set_attr, name:%s, value:%s", name, value)
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            logs.debug("proxy.set_attr, call to setProp needed, name:%s, value:%s", name, value)
            return self._exe.setProp(self.ffid, name, value)

    async def get_a(self, attr):
        """
        Asyncronous equivalent to get(attr).
        Asynchronously get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.

        """
        logs.debug("proxy.get_async start %s", attr)
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        methodType, val = await self._exe.getPropAsync(self._pffid, attr)
        logs.debug("proxy.get_async %s, methodType: %s, val %s", attr, methodType, val)
        return self._call(attr, methodType, val)

    async def set_a(self, name, value):
        """

        Asyncronous equivalent to set_attr(name,value).
        Asynchronously set an attribute of the linked JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.

        """
        logs.debug("proxy.set_attr, name:%s, value:%s", name, value)
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            logs.debug("proxy.set_attr, call to setProp needed, name:%s, value:%s", name, value)
            return await self._exe.setPropAsync(self.ffid, name, value)

    def init_iterator(self):
        """
        Initialize an iterator.

        Returns:
            self: The iterator object.
        """
        self._ix = 0
        logs.debug("proxy.init_iterator")
        if self.length is None:
            self._Keys = self._exe.keys(self.ffid)
        return self

    def next_item(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        logs.debug("proxy.next_item")
        if self._Keys:
            if self._ix < len(self._Keys):
                result = self._Keys[self._ix]
                self._ix += 1
                return result
            else:
                raise StopIteration
        elif self._ix < self.length:
            result = self[self._ix]
            self._ix += 1
            return result
        else:
            raise StopIteration

    def get_item(self, attr):
        """
        equivalent to a=self[attr]
        Get an item of the linked JavaScript object.

        Args:
            attr (str): The item name.

        Returns:
            Any: The item value.
        """
        logs.debug("proxy.get_item %s", attr)
        methodType, val = self._exe.getProp(self.ffid, attr)
        return self._call(attr, methodType, val)

    def set_item(self, name, value):
        """

        equivalent to self[name]=a
        Set an item of the linked JavaScript object.

        Args:
            name (str): The item name.
            value (Any): The item value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.set_item, name:%s, value:%s", name, value)
        return self._exe.setProp(self.ffid, name, value)

    async def get_item_a(self, attr):
        """
        equivalent to a=self[attr]
        Get an item of the linked JavaScript object.

        Args:
            attr (str): The item name.

        Returns:
            Any: The item value.
        """
        logs.debug("proxy.get_item %s", attr)
        methodType, val = await self._exe.getPropAsync(self.ffid, attr)
        return self._call(attr, methodType, val)

    async def set_item_a(self, name, value):
        """

        equivalent to self[name]=a
        Set an item of the linked JavaScript object.

        Args:
            name (str): The item name.
            value (Any): The item value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.set_item, name:%s, value:%s", name, value)
        return await self._exe.setPropAsync(self.ffid, name, value)

    def contains_key(self, key):
        """
        Check if a key is contained in the linked JavaScript object.

        Args:
            key (Any): The key to check.

        Returns:
            bool: True if the key is contained, otherwise False.
        """
        logs.debug("proxy.contains_key, key:%s", key)
        return True if self[key] is not None else False

    def get_value_of(self):
        """
        Serialize the linked JavaScript object.

        Returns:
            Any: The "valueOf" value.
        """
        ser = self._exe.ipc("serialize", self.ffid, "")
        logs.debug("proxy.get_value_of, %s", ser)
        return ser["val"]
    
    def get_dict(self)->dict:
        """
        Serialize a linked JavaScript object into a python dictionary.

        Returns:
            Any: The "valueOf" value.
        """
        ser = self._exe.ipc("serialize", self.ffid, "")
        logs.debug("proxy.get_value_of, %s", ser)
        return ser["val"]
    
    async def get_dict_a(self)->dict:
        """
        Serialize a linked JavaScript object into a python dictionary.

        Returns:
            Any: The "valueOf" value.
        """
        ser = await self._exe.ipc_async("serialize", self.ffid, "")
        logs.debug("proxy.get_value_of, %s", ser)
        print()
        return ser["val"]

    def get_str(self):
        """
        Get a string representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The string representation.
        """
        logs.debug("proxy.get_str")
        return self._exe.inspect(self.ffid, "str")

    def get_repr(self):
        """
        Get a representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The representation.
        """
        logs.debug("proxy.get_repr")
        return self._exe.inspect(self.ffid, "repr")

    def get_json(self):
        """
        Get a JSON representation of the linked JavaScript object.

        Returns:
            dict: The JSON representation.
        """
        logs.debug("proxy.get_json")
        return {"ffid": self.ffid}

    def free(self):
        """
        Free the linked JavaScript object.
        """
        logs.debug("proxy.free")
        self._exe.free(self.ffid)


class EventEmitterProxy(Proxy):
    """A unique type of Proxy made whenever an EventEmitter is returned,
    containing special wrapped on, off, and once functions that ensure the
    python side of the bridge knows that it's functions have been set as
    listeners."""

    def on(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Register a python function or coroutine as a listener for this EventEmitter.

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator

        """
        conf = self._config()

        print("SUPER PROXY ON")
        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if conf.node_emitter_patches:

            def handler(*args, **kwargs):
                listener(self, *args, **kwargs)

            listener = handler
        else:
            pass

        # print(s)
        print(inspect.iscoroutinefunction(listener))
        # emitter.on(event, listener)
        self.get("on").call_s(event, listener)
        logs.info(
            "On for: emitter %s, event %s, function %s, iffid %s", "s", event, listener, getattr(listener, "iffid")
        )

        # Persist the FFID for this callback object so it will get deregistered properly.

        ffid = getattr(listener, "iffid")
        setattr(listener, "ffid", ffid)

        self._loop().callbacks[ffid] = listener
        print("cleared on.")
        return listener

    def off(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Unregisters listener as a listener function from this EventEmitter.

        Args:
            event (str): The name of the event to unregister the handler from.
            handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.


        Example:
            .. code-block:: python

                off(myEmitter, 'increment', handleIncrement)
        """
        print("SUPER PROXY OFF")
        self.get("off").call_s(event, listener)

        del self._loop().callbacks[getattr(listener, "ffid")]

    async def off_a(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Unregisters listener as a listener function from this EventEmitter.

        Args:
            event (str): The name of the event to unregister the handler from.
            handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.


        Example:
            .. code-block:: python

                off(myEmitter, 'increment', handleIncrement)
        """
        print("SUPER PROXY OFF")
        await self.get_a("off").call_a(event, listener)

        del self._loop().callbacks[getattr(listener, "ffid")]

    def once(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Register a python function or coroutine as a one time event listener for this EventEmitter.
        Once it's called, the function will be Unregistered!

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator

        """
        print("SUPER PROXY ONCE")
        conf = self._config()
        i = hash(listener)

        def handler(*args, **kwargs):
            if conf.node_emitter_patches:
                listener(self, *args, **kwargs)
            else:
                listener(*args, **kwargs)
            del conf.event_loop.callbacks[i]

        output = self.get("once").call_s(event, listener)

        self._loop().callbacks[i] = handler
        return output


INTERNAL_VARS_NODE = ["_proxy", "_prev", "_op", "_kwargs", "_depth"]


class NodeOp:
    """Represents a Node operation for asynchronous execution.

    When the Proxy's ``_asyncmode`` attribute is set to True, it does not make calls
    to Node.js immediately, instead creating a stack of linked NodeOp objects that
    contains the kwargs for each call and a link to the previous NodeOp. Once the
    await keyword is used, this stack calls the aget, aset, and call_a elements
    of each returned proxy from the bottom up.

    Attributes:
        _proxy (Proxy, optional): The Proxy object associated with this Node operation.
        _prev (NodeOp, optional): The previous NodeOp in the operation stack.  None if it's the root node.
        _op (str, optional): The type of operation, such as 'get', 'set', or 'call'.
        _depth (int): The depth of this NodeOp chain
        _kwargs (dict, optional): The keyword arguments for the operation.

    """

    def __init__(
        self,
        proxy: Proxy = None,
        prev=None,
        op: Literal["get", "set", "call", "getitem", "setitem"] = None,
        kwargs=None,
    ):
        self._proxy: Proxy = proxy
        self._prev: NodeOp = prev
        self._depth = 0
        if self._prev != None:
            self._depth = self._prev._depth + 1
        self._op = op
        self._kwargs = kwargs

    def __await__(self):
        return self.process().__await__()

    async def process(self):
        """
        Called when the built NodeOp chain is awaited.
        Recursively process each node in the stack.
        """
        proxy = self._proxy
        if self._prev is not None:
            proxy = await self._prev.process()

        if self._op == "set":
            return await proxy.set_a(**self._kwargs)
        if self._op == "get":
            return await proxy.get_a(**self._kwargs)
        if self._op == "call":
            args = self._kwargs["args"]
            self._kwargs.pop("args")
            return await proxy.call_a(*args, **self._kwargs)
        if self._op == "getitem":
            return await proxy.get_item_a(**self._kwargs)
        if self._op == "setitem":
            return await proxy.set_item_a(**self._kwargs)
        raise Exception(f"Invalid Operation {self._op}!")

    def __call__(self, *args, timeout=10, forceRefs=False, coroutine=False):
        return NodeOp(
            prev=self,
            op="call",
            kwargs={"args": args, "timeout": timeout, "forceRefs": forceRefs, "coroutine": coroutine},
        )

    def __getattr__(self, attr):
        return NodeOp(prev=self, op="get", kwargs={"attr": attr})

    def __iter__(self):
        return NodeOp(prev=self, op="iter", kwargs={})

    def __next__(self):
        return NodeOp(prev=self, op="next", kwargs={})

    def __setattr__(self, name, value):
        if name in INTERNAL_VARS_NODE:
            object.__setattr__(self, name, value)
            return

        raise Exception("don't use this in amode!  use .set instead!")

    def __getitem__(self, attr):
        return NodeOp(prev=self, op="getitem", kwargs={"attr": attr})

    def __setitem__(self, name, value):
        return NodeOp(prev=self, op="setitem", kwargs={"name": name, "value": value})

    def get(self, attr):
        """
        Set the current node to get an attribute of the linked JavaScript object
        down the line.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.

        """
        return NodeOp(prev=self, op="get", kwargs={"attr": attr})

    def set(self, name: str, value: Any) -> NodeOp:
        """
        equivalent to object.value=newval

        Sets the attribute 'name' to the specified 'value' for the current node.

        Args:
            name (str): The name of the attribute to be set.
            value (Any): The value to assign to the specified attribute.

        Returns:
            NodeOp: the Next representing the operation of setting an attribute.
                This operation is applied to the current node and includes information
                about the attribute name and its assigned value.

        """
        return NodeOp(prev=self, op="set", kwargs={"name": name, "value": value})

    # def __contains__(self, key):
    #     return NodeOp(prev=self,op='contains',kwargs={'key':key})

    # def valueOf(self):
    #     return NodeOp(prev=self,op='valueOf',kwargs={})
    def __repr__(self):
        """
        View a representation of the operation chain to be processed as a coroutine.

        Returns:
            str: The representation.
        """
        previous = ""
        if self._prev is not None:
            previous = repr(self._prev) + ">"
        return previous + f"[{self._op}, {self._depth}, {self._kwargs},{str(self._proxy)}]"
