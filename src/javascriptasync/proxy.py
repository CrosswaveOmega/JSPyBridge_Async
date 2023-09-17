from __future__ import annotations
import asyncio
import time, threading, json, sys, os, traceback
from typing import Any, Tuple
from . import config, json_patch

from .errors import JavaScriptError
from .events import EventLoop


from .logging import logs

class Executor:
    """
    This is the Executor, something that sits in the middle of the Bridge and is the interface for
    Python to JavaScript. This is also used by the bridge to call Python from Node.js

    Attributes:
        conf (config.JSConfig): Reference to the active JSConfig object.
        loop (EventLoop): The event loop for handling JavaScript events.
        queue (callable): shortcut to EventLoop.queue_request
        i (int): A unique id for generating request ids.
        self.bridge(PyInterface): shortcut to EventLoop.pyi
    """
    def __init__(self, config_obj:config.JSConfig,loop:EventLoop):
        self.conf=config_obj
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
            ffid (int): The function ID.
            attr (Any): Attribute to be passed into the key field
            args (Any, optional): Additional parameters for init and set actions
        
        Returns:
            res: The response after executing the action.
        """
        self.i += 1
        r = self.i  # unique request ts, acts as ID for response
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
        res, barrier = self.loop.responses[r]
        del self.loop.responses[r]
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
        callRespId, ffidRespId = self.i + 1, self.i + 2
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
                if (
                    (type(v) is int)
                    or (type(v) is float)
                    or (v is None)
                    or (v is True)
                    or (v is False)
                ):
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
    async def pcallalt(self, ffid:int, action:str, attr:Any, args:Tuple[Any], *, timeout:int=1000, forceRefs:bool=False):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the function ID, attribute, and arguments that Python would like to call. For each of the
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
        packet, payload, wanted, ffidRespId= self._prepare_pcall_request(ffid, action, attr, args, forceRefs)
        
        callRespId= packet["r"]
        
        l = self.loop.queue_request(callRespId, payload, asyncmode=True, loop=asyncio.get_event_loop())
        #print('asymc',payload,l)
        # We only have to wait for a FFID assignment response if
        # we actually sent any non-primitives, otherwise skip
        if self.expectReply:
            l2 = self.loop.await_response(ffidRespId, asyncmode=True, loop=asyncio.get_event_loop())
            try:
                await asyncio.wait_for(l2.wait(), timeout)
            except asyncio.TimeoutError:
                raise Exception("Execution timed out")
            pre, barrier = self.loop.responses[ffidRespId]
            logs.debug("ProxyExec:callRespId:%s ffidRespId:%s",str(callRespId),str(ffidRespId))

            del self.loop.responses[ffidRespId]

            if "error" in pre:
                raise JavaScriptError(attr, pre["error"])

            for requestId in pre["val"]:
                ffid = pre["val"][requestId]
                self.bridge.m[ffid] = wanted[int(requestId)]
                # This logic just for Event Emitters
                try:
                    if hasattr(self.bridge.m[ffid], "__call__"):
                        setattr(self.bridge.m[ffid], "iffid", ffid)
                except Exception:
                    pass

            barrier.wait()
        now=time.time()
        logs.debug("ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s",str(l),str(callRespId),str(ffidRespId),timeout)
        try:
            await asyncio.wait_for(l.wait(), timeout)
        except asyncio.TimeoutError:
            if not self.conf.event_thread:
                print(self.conf.dead)
            raise Exception(
                f"Call to '{attr}' timed out. Increase the timeout by setting the `timeout` keyword argument."
            )
           
        elapsed=(time.time()-now)
        logs.debug("ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s, took: %s",str(l),str(callRespId),str(ffidRespId),timeout,elapsed)

        res, barrier = self.loop.responses[callRespId]
        del self.loop.responses[callRespId]

        barrier.wait()

        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res["key"], res["val"]
    def pcall(self, ffid:int, action:str, attr:Any, args:Tuple[Any], *, timeout:int=1000, forceRefs:bool=False):
        """
        This function does a two-part call to JavaScript. First, a preliminary request is made to JS
        with the function ID, attribute and arguments that Python would like to call. For each of the
        non-primitive objects in the arguments, in the preliminary request we "request" an FFID from JS
        which is the authoritative side for FFIDs. Only it may assign them; we must request them. Once
        JS recieves the pcall, it searches the arguments and assigns FFIDs for everything, then returns
        the IDs in a response. We use these IDs to store the non-primitive values into our ref map.
        On the JS side, it creates Proxy classes for each of the requests in the pcall, once they get
        destroyed, a free call is sent to Python where the ref is removed from our ref map to allow for
        normal GC by Python. Finally, on the JS side it executes the function call without waiting for
        Python. A init/set operation on a JS object also uses pcall as the semantics are the same.
        Args:
            ffid (int): unique function id.
            action (str): The action to be executed.   (can be "init", "set", or "call") 
            attr (Any): attribute to be passed into the 'key' field
            args (Tuple[Any]): Arguments for the action to be executed.
            timeout (int, optional): Timeout duration. Defaults to 1000.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.
        
        Returns:
            (Any, Any): The response key and value.
        """
        wanted = {}
        self.ctr = 0
        callRespId, ffidRespId = self.i + 1, self.i + 2
        self.i += 2
        self.expectReply = False
        # p=1 means we expect a reply back, not used at the meoment, but
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
                if (
                    (type(v) is int)
                    or (type(v) is float)
                    or (v is None)
                    or (v is True)
                    or (v is False)
                ):
                    flocals[k] = v
                else:
                    flocals[k] = ser(v)
            packet["p"] = self.ctr
            payload = json.dumps(packet)
        else:
            payload = json.dumps(packet, default=ser)
            # a bit of a perf hack, but we need to add in the counter after we've already serialized ...
            payload = payload[:-1] + f',"p":{self.ctr}}}'

        l = self.loop.queue_request(callRespId, payload)
        # We only have to wait for a FFID assignment response if
        # we actually sent any non-primitives, otherwise skip
        if self.expectReply:
            l2 = self.loop.await_response(ffidRespId)
            if not l2.wait(timeout):
                raise Exception("Execution timed out")
            pre, barrier = self.loop.responses[ffidRespId]
            logs.debug("ProxyExec:callRespId:%s ffidRespId:%s",str(callRespId),str(ffidRespId))

            del self.loop.responses[ffidRespId]

            if "error" in pre:
                raise JavaScriptError(attr, pre["error"])

            for requestId in pre["val"]:
                ffid = pre["val"][requestId]
                self.bridge.m[ffid] = wanted[int(requestId)]
                # This logic just for Event Emitters
                try:
                    if hasattr(self.bridge.m[ffid], "__call__"):
                        setattr(self.bridge.m[ffid], "iffid", ffid)
                except Exception:
                    pass

            barrier.wait()
        now=time.time()
        logs.debug("ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s",str(l),str(callRespId),str(ffidRespId),timeout)

        if not l.wait(timeout):
            if not self.conf.event_thread:
                print(self.conf.dead)
            raise Exception(
                f"Call to '{attr}' timed out. Increase the timeout by setting the `timeout` keyword argument."
            )
        elapsed=(time.time()-now)
        logs.debug("ProxyExec: lock:%s,callRespId:%s ffidRespId:%s, timeout:%s, took: %s",str(l),str(callRespId),str(ffidRespId),timeout,elapsed)

        res, barrier = self.loop.responses[callRespId]
        del self.loop.responses[callRespId]

        barrier.wait()

        if "error" in res:
            raise JavaScriptError(attr, res["error"])
        return res["key"], res["val"]

    def getProp(self, ffid, method):
        """
        Get a property from a JavaScript object.

        Args:
            ffid (int): Function ID.
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
            ffid (int): Function ID.
            method (str): The method to set.
            val (Any): The value to set.

        Returns:
            bool: True if successful.
        """
        self.pcall(ffid, "set", method, [val])
        return True

    def callProp(self, ffid, method, args, *, timeout=None, forceRefs=False):
        """
        Call a property on a JavaScript object.

        Args:
            ffid (int): Function ID.
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
            ffid (int): Function ID.
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
            ffid (int): Function ID.
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
            ffid (int): Function ID.
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
            ffid (int): Function ID.
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
            ffid (int): Function ID.

        Returns:
            list: The list of keys.
        """
        return self.ipc("keys", ffid, "")["keys"]

    def free(self, ffid):
        """
        Free a local JavaScript object.

        Args:
            ffid (int): Function ID.
        """
        self.loop.freeable.append(ffid)

    def get(self, ffid):
        """
        Get a local JavaScript object.

        Args:
            ffid (int): Function ID.

        Returns:
            Any: The JavaScript object.
        """
        return self.bridge.m[ffid]




INTERNAL_VARS = ["ffid", "_ix", "_exe", "_pffid", "_pname", "_es6", "_resolved", "_Keys"]

# "Proxy" classes get individually instanciated for every thread and JS object
# that exists. It interacts with an Executor to communicate.
class Proxy(object):
    """
    "Proxy" classes get individually instanciated for every thread and JS object
    that exists. It interacts with an Executor to communicate.

    They're essentially references to objects on the JavaScript side of the bridge.

    Attributes:
        ffid (int): Function ID.
        _exe (Executor): The executor for communication with JavaScript.
        _ix (int): Index.
        _pffid (int): Property function ID.
        _pname (str): Property name.
        _es6 (bool): ES6 class flag.
        _resolved (dict): Resolved values.
        _Keys (list): List of keys.
    """
    def __init__(self, exe, ffid, prop_ffid=None, prop_name="", es6=False):
        """
        Args:
            exe (Executor): The executor for communication with JavaScript.
            ffid (int): Function ID.
            prop_ffid (int, optional): Property function ID. Defaults to None.
            prop_name (str, optional): Property name. Defaults to "".
            es6 (bool, optional): ES6 class flag. Defaults to False.

        """
        logs.debug("new Proxy: %s, %s,%s,%s,%s", exe,ffid,prop_ffid,prop_name,es6)
        self.ffid = ffid
        self._exe:Executor = exe
        self._ix = 0
        #
        self._pffid = prop_ffid if (prop_ffid != None) else ffid
        self._pname = prop_name
        self._es6 = es6
        self._resolved = {}
        self._Keys = None
        
        logs.debug("new Proxy init done: %s, %s,%s,%s,%s", exe,ffid,prop_ffid,prop_name,es6)

    def _call(self, method, methodType, val):
        """
        Helper function for processing the result of a calls.

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
            return Proxy(self._exe, val, self.ffid, method)
        if methodType == "class":
            return Proxy(self._exe, val, es6=True)
        if methodType == "obj":
            return Proxy(self._exe, val)
        if methodType == "inst":
            return Proxy(self._exe, val)
        if methodType == "void":
            return None
        if methodType == "py":
            return self._exe.get(val)
        else:
            return val
        
    async def coro_call(self, *args, timeout=10, forceRefs=False):
        """
        Coroutine version of the __call__ method.

        Args:
            args: Arguments to pass to the method.
            timeout (int, optional): Timeout duration. Defaults to 10.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.

        Returns:
            Any: The result of the call.
        """
        logs.debug("calling coro_call.  Timeout: %d, Args: %s", timeout, str(args))
        if self._es6:
            mT,v=await self._exe.initPropAsync(self._pffid, self._pname, args)
        else:
            mT,v=await self._exe.callPropAsync(
                self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs
            )
        if mT == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, mT, v)
    def __call__(self, *args, timeout=10, forceRefs=False,coroutine=False):
        """
        Use this proxy to call a method across the bridge.

        Args:
            args: Arguments to pass to the method.
            timeout (int, optional): Timeout duration. Defaults to 10.
            forceRefs (bool, optional): Whether to force refs. Defaults to False.
            coroutine (bool, optional): Whether to use coroutine. Defaults to False.

        Returns:
            Any: The result of the call.
        """
        if coroutine:
            return self.coro_call( *args, timeout=timeout, forceRefs=forceRefs)
        logs.debug("calling __call__.  Timeout: %d, Args: %s", timeout, str(args))
        if self._es6:
            mT,v=self._exe.initProp(self._pffid, self._pname, args)
        else:
            mT,v=self._exe.callProp(
                self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs
            )
        '''mT, v = (
            self._exe.initProp(self._pffid, self._pname, args)
            if self._es6
            else self._exe.callProp(
                self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs
            )
        )'''
        if mT == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, mT, v)

    def __getattr__(self, attr):
        """
            Get an attribute of the JavaScript object.

            Args:
                attr (str): The attribute name.

            Returns:
                Any: The attribute value.
        """
        # Special handling for new keyword for ES5 classes
        
        logs.debug("proxy.get_attr start %s", attr)
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        methodType, val = self._exe.getProp(self._pffid, attr)
        logs.debug("proxy.get_attr %s, methodType: %s, val %s", attr,methodType,val)
        return self._call(attr, methodType, val)

    def __getitem__(self, attr):
        """
        Get an item of the JavaScript object.

        Args:
            attr (str): The item name.

        Returns:
            Any: The item value.
        """
        logs.debug("proxy.get_item %s", attr)
        methodType, val = self._exe.getProp(self.ffid, attr)
        return self._call(attr, methodType, val)

    def __iter__(self):
        """
        Initalize an iterator
        Returns:
            self: The iterator object.
        """
        self._ix = 0
        logs.debug("proxy. __iter__")
        if self.length == None:
            self._Keys = self._exe.keys(self.ffid)
        return self

    def __next__(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        logs.debug("proxy. __next__")
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

    def __setattr__(self, name, value):
        """
        Set an attribute of the JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.setattr, name:%s, value:%s",name,value)
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            
            logs.debug("proxy.setattr, call to setProp needed, name:%s, value:%s",name,value)
            return self._exe.setProp(self.ffid, name, value)

    def __setitem__(self, name, value):
        """
        Set an item of the JavaScript object.

        Args:
            name (str): The item name.
            value (Any): The item value.

        Returns:
            bool: True if successful.
        """
        logs.debug("proxy.setitem, name:%s, value:%s",name,value)
        return self._exe.setProp(self.ffid, name, value)

    def __contains__(self, key):
        """
        Check if a key is contained in the JavaScript object.

        Args:
            key (Any): The key to check.

        Returns:
            bool: True if the key is contained, otherwise False.
        """
        logs.debug("proxy.contains, key:%s",key)
        return True if self[key] is not None else False

    def valueOf(self):
        """
        Serialize the JavaScript object.

        Returns:
            Any: The "valueOf" value.
        """
        ser = self._exe.ipc("serialize", self.ffid, "")
        
        logs.debug("proxy.valueOf, %s",ser)
        return ser["val"]

    def __str__(self):
        """
        Get a string representation of the JavaScript object via an inspect call

        Returns:
            str: The string representation.
        """
        logs.debug("proxy.str")
        return self._exe.inspect(self.ffid, "str")

    def __repr__(self):
        """
        Get a representation of the JavaScript object via an inspect call.

        Returns:
            str: The representation.
        """
        logs.debug("proxy.repr")
        return self._exe.inspect(self.ffid, "repr")

    def __json__(self):
        """
        Get a JSON representation of the JavaScript object.

        Returns:
            dict: The JSON representation.
        """
        logs.debug("proxy.json")
        return {"ffid": self.ffid}

    def __del__(self):
        """
        Free the JavaScript object.
        """
        logs.debug("proxy.del")
        self._exe.free(self.ffid)

