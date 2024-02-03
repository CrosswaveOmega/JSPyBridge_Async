from __future__ import annotations

import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Literal,
    Union,
)
import base64

from .errorsjs import (
    AsyncReminder,
    InvalidNodeOp,
)
from .events import EventLoop

from .core.jslogging import log_warning, log_debug, log_info, log_error


from .executor import Executor

if TYPE_CHECKING:
    from .configjs import JSConfig


INTERNAL_VARS = [
    "ffid",
    "node_op",
    "_ix",
    "_exe",
    "_pffid",
    "_children",
    "_pname",
    "_es6",
    "_asyncmode",
    "_resolved",
    "_ops",
    "_keys",
    "_inspected",
]


# "Proxy" classes get individually instantiated  for every thread and JS object
# that exists. It interacts with an Executor to communicate.
class Proxy:
    """
    "Proxy" classes get individually instantiated every thread and JS object
    that exists. It interacts with an Executor to communicate to the Node.JS instance
    on the other side of the bridge.

    Utilizes magic methods to determine which api calls to make, and is capable of
    operating in an single asyncio mode, when it "stacks" operations together
    instead of executing them right away, running them only when using the await keyword.


    Attributes:
        ffid (int): Foreign Object Reference ID.
        _exe (Executor): The executor for communication with JavaScript.
        _ix (int): Index.
        _pffid (int): Property foreign Object Reference ID.
        _pname (str): Property name.
        _es6 (bool): ES6 class flag.
        _asyncmode (bool): asyncronous stacking mode: Operations are assembled into a stack of NodeOp  objects.
        _resolved (dict): Resolved values.
        _keys (list): List of keys.
    """

    __slots__ = [
        "ffid",
        "node_op",
        "_ix",
        "_exe",
        "_pffid",
        "_children",
        "_pname",
        "_es6",
        "_asyncmode",
        "_resolved",
        "_ops",
        "_keys",
        "_inspected",
    ]

    def __init__(self, exe: Executor, ffid, prop_ffid=None, prop_name="", es6=False, amode=False):
        """
        Args:
            exe (Executor): The executor for communication with JavaScript.
            ffid (int): Foreign Object Reference ID.
            prop_ffid (int, optional): Property foreign Object Reference ID. Defaults to None.
            prop_name (str, optional): Property name. Defaults to "".
            es6 (bool, optional): ES6 class flag. Defaults to False.

        """
        log_info("new Proxy: %s, %s,%s,%s,%s", exe, ffid, prop_ffid, prop_name, es6)
        self.ffid = ffid
        self._exe: Executor = exe
        self._ix = 0
        #
        self._pffid = prop_ffid if (prop_ffid is not None) else ffid
        self._pname = prop_name
        self._es6 = es6
        self._resolved = {}
        self._ops = []
        self._children = {}
        self.node_op = False
        self._keys = None
        self._inspected = None
        self._asyncmode = amode

        log_debug("new Proxy init done: %s, %s,%s,%s,%s", exe, ffid, prop_ffid, prop_name, es6)

    def _config(self) -> JSConfig:
        """Access the JSConfig object reference within the executor."""
        return self._exe.config

    def _loop(self) -> EventLoop:
        """Access the EventLoop reference within the executor."""
        return self._exe.config.event_loop

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

    def _call(self, method: str, method_type: str, val: Any):
        """
        Helper function for processing the result of a call.

        Args:
            method (str): The method to call.
            method_type (str): The method type.
            val (Any): The value to call.

        Returns:
            Any: The result of the call.
        """

        log_debug("Proxy._call: %s, %s,%s,%s", "MT", method, method_type, val)
        result_val = None
        if method_type == "fn":
            result_val = Proxy(
                self._exe, val, prop_ffid=self.ffid, prop_name=method, amode=self._asyncmode
            )
        elif method_type == "class":
            result_val = Proxy(self._exe, val, es6=True, amode=self._asyncmode)
        elif method_type in ["obj", "inst"]:
            result_val = Proxy(self._exe, val, amode=self._asyncmode)
        elif method_type in ["obje", "inste"]:
            result_val = EventEmitterProxy(self._exe, val, amode=self._asyncmode)
        elif method_type == "void":
            result_val = None
        elif method_type == "py":
            result_val = self._exe.get(val)
        else:
            result_val = val
        return result_val

    async def getdeep(self):
        """
        GetDeep is an effort to reduce the number of asyncronous calls
        by doing a surface level query of all of an object proxyable attributes.
        """
        deepproxy = await self._exe.ipc_async("getdeep", self.ffid, None)
        log_info("getting deep copy")
        if deepproxy["key"] == "deepobj":
            for proxy in deepproxy["val"]:
                new_value = self._call(proxy["attr"], proxy["key"], proxy["val"])
                if isinstance(new_value, (Proxy, EventEmitterProxy)):
                    self._children[proxy["attr"]] = new_value

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
        log_debug("calling call_a.  Timeout: %d, Args: %s, Coro: %s", timeout, str(args), coroutine)
        if self._es6:
            methodtype, v = await self._exe.initPropAsync(self._pffid, self._pname, args)
        else:
            methodtype, v = await self._exe.callPropAsync(
                self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs
            )
        if methodtype == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, methodtype, v)

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
            m_t, v = self._exe.initProp(self._pffid, self._pname, args)
        else:
            m_t, v = self._exe.callProp(
                self._pffid, self._pname, args, timeout=timeout, forceRefs=forceRefs
            )
        log_info("call_s proxy, m_t:%s,v:%s.  Timeout: %d, Args: %s", m_t, v, timeout, str(args))
        if m_t == "fn":
            return Proxy(self._exe, v)
        return self._call(self._pname, m_t, v)

    def __call__(self, *args, timeout=10, forceRefs=False, coroutine=False):
        if self._asyncmode:
            return NodeOp(
                self,
                op="call",
                kwargs={
                    "args": args,
                    "timeout": timeout,
                    "forceRefs": forceRefs,
                    "coroutine": coroutine,
                },
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
        log_info(f" GETTING {attr}")
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
        if attr in self._children:
            return self._children[attr]
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
            raise AsyncReminder("you need to use an asyncronous iterator when in amode.")
        return self.init_iterator()

    def __next__(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        if self._asyncmode:
            raise AsyncReminder("you need to use an asyncronous iterator when in amode.")
        return self.next_item()

    def __aiter__(self):
        """
        Async variant of iterator.
        """
        self._ix = 0
        length = self.get_attr("length")
        if length is None:
            keys = self._exe.ipc("keys", self.ffid, "")
            self._keys = keys["keys"]
        return self

    # return the next awaitable
    async def __anext__(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        length = await self.get_a("length")
        if self._keys:
            if self._ix < len(self._keys):
                result = self._keys[self._ix]
                self._ix += 1
                return result
            raise StopAsyncIteration
        elif self._ix < length:
            result = await self.get_a(self._ix)
            self._ix += 1
            return result
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
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            if self._asyncmode:
                raise AsyncReminder("don't use in amode!  use .set instead!")
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
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            if self._asyncmode:
                return NodeOp(self, op="set", kwargs={"name": name, "value": value})
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

    def __contains__(self, key):
        """
        Check if a key is contained in the linked JavaScript object.

        Args:
            key (Any): The key to check.

        Returns:
            bool: True if the key is contained, otherwise False.
        """
        return self.contains_key(key)

    def valueOf(self):
        """
        Serialize the linked JavaScript object.

        Returns:
            Any: The "valueOf" value.
        """
        return self.get_value_of()

    def __str__(self):
        """
        Get a string representation of the linked JavaScript object via an inspect call

        Returns:
            str: The string representation.
        """
        return self.get_str()

    def __repr__(self):
        """
        Get a representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The representation.
        """
        return self.get_repr()

    def __json__(self):
        """
        Get a JSON representation of the linked JavaScript object.

        Returns:
            dict: The JSON representation.
        """
        return self.get_json()

    def __del__(self):
        """
        Free the linked JavaScript object.
        """
        return self.free()

    def get_s(self, attr):
        """
        Alias for get_attr.

        Get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        return self.get_attr(attr)

    def get_attr(self, attr):
        """
        Get an attribute of the linked JavaScript object.

        Args:
            attr (str): The attribute name.

        Returns:
            Any: The attribute value.
        """
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        req = self._exe.ipc("get", self._pffid, attr)
        method_type, val = req.key, req.val
        log_info("proxy.get_attr %s, method_type: %s, val %s", attr, method_type, val)
        return self._call(attr, method_type, val)

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
        return self.set_attr(name, value)

    def set_attr(self, name, value):
        """
        Set an attribute of the linked JavaScript object.

        Args:
            name (str): The attribute name.
            value (Any): The attribute value.

        Returns:
            bool: True if successful.
        """
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
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
        if attr == "new":
            return self._call(self._pname if self._pffid == self.ffid else "", "class", self._pffid)
        req = await self._exe.ipc_async("get", self._pffid, attr)
        method_type, val = req.key, req.val
        new_value = self._call(attr, method_type, val)
        if isinstance(new_value, (Proxy, EventEmitterProxy)):
            self._children[attr] = new_value
        return new_value

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
        if name in INTERNAL_VARS:
            object.__setattr__(self, name, value)
        else:
            log_debug("proxy.set_attr, call to setProp needed, name:%s, value:%s", name, value)
            return await self._exe.setPropAsync(self.ffid, name, value)

    def init_iterator(self):
        """
        Initialize an iterator.

        Returns:
            self: The iterator object.
        """
        self._ix = 0
        if self.length is None:
            keys = self._exe.ipc("keys", self.ffid, "")
            self._keys = keys["keys"]
        return self

    def next_item(self):
        """
        Get the next item from the iterator.

        Returns:
            Any: The next item.
        """
        log_debug("proxy.next_item")
        if self._keys:
            if self._ix < len(self._keys):
                result = self._keys[self._ix]
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
        log_debug("proxy.get_item %s", attr)

        req = self._exe.ipc("get", self.ffid, attr)
        method_type, val = req.key, req.val
        return self._call(attr, method_type, val)

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
        log_debug("proxy.set_item, name:%s, value:%s", name, value)
        return self._exe.setProp(self.ffid, name, value)

    async def get_item_a(self, attr):
        """
        Equivalent to a=self[attr]
        Get an item of the linked JavaScript object.

        Args:
            attr (str): The item name.

        Returns:
            Any: The item value.
        """
        log_debug("proxy.get_item %s", attr)
        req = await self._exe.ipc_async("get", self.ffid, attr)
        method_type, val = req.key, req.val

        return self._call(attr, method_type, val)

    async def set_item_a(self, name, value):
        """
        Equivalent to self[name]=value
        Set an item of the linked JavaScript object.

        Args:
            name (str): The item name.
            value (Any): The item value.

        Returns:
            bool: True if successful.
        """
        log_debug("proxy.set_item, name:%s, value:%s", name, value)
        return await self._exe.setPropAsync(self.ffid, name, value)

    def contains_key(self, key):
        """
        Check if a key is contained in the linked JavaScript object.

        Args:
            key (Any): The key to check.

        Returns:
            bool: True if the key is contained, otherwise False.
        """
        log_debug("proxy.contains_key, key:%s", key)
        return True if self[key] is not None else False

    def get_value_of(self):
        """
        Alias for get_dict.
          Serialize the linked JavaScript object into a python dictionary.

        Returns:
            Any: The Dictionary value that represents the Proxy on
             the Node.JS side.
        """
        return self.get_dict()

    def get_dict(self) -> dict:
        """
        Serialize the linked JavaScript object into a python dictionary.

        Returns:
            Any: The Dictionary value that represents the Proxy on
             the Node.JS side.
        """
        ser = self._exe.ipc("serialize", self.ffid, "")
        log_debug("proxy.get_value_of, %s", ser)
        return ser["val"]

    async def get_dict_a(self) -> dict:
        """
        Asyncronous version of get_dict.
        Serialize the linked JavaScript object into a python dictionary.

        Returns:
            Any: The Dictionary value that represents the Proxy on
             the Node.JS side.
        """
        ser = await self._exe.ipc_async("serialize", self.ffid, "")
        log_debug("proxy.get_value_of, %s", ser)
        return ser["val"]

    def get_blob(self) -> bytes:
        """
        Fetch the blob data associated with the current proxy object,
        decodes it from Base64,  and returns it as a `bytes` object.

        Returns:
            bytes: The decoded blob data.
        """
        ser = self._exe.ipc("blob", self.ffid, "")
        log_debug("proxy.get_blob, %s", ser)
        b64blob = ser["blob"]
        buffer_data = base64.b64decode(b64blob)

        return buffer_data

    async def get_blob_a(self) -> bytes:
        """
        Asynchronously fetches the blob data associated with the current proxy object,
          decodes it from Base64, and returns it as a `bytes` object.

        Returns:
            bytes: The decoded blob data.
        """
        ser = await self._exe.ipc_async("blob", self.ffid, "")
        log_debug("proxy.get_blob, %s", ser)
        b64blob = ser["blob"]
        buffer_data = base64.b64decode(b64blob)

        return buffer_data

    def get_str(self):
        """
        Get a string representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The string representation.
        """
        log_debug("proxy.get_str")
        outcome = self._exe.ipc("inspect", self.ffid, "str")
        return outcome.val

    def get_repr(self):
        """
        Get a representation of the linked JavaScript object via an inspect call.

        Returns:
            str: The representation.
        """
        log_debug("proxy.get_repr")

        outcome = self._exe.ipc("inspect", self.ffid, "repr")
        return outcome.val

    def get_json(self):
        """
        Get a JSON representation of the linked JavaScript object.

        Returns:
            dict: The JSON representation.
        """
        log_debug("proxy.get_json")
        return {"ffid": self.ffid}

    def free(self):
        """
        Free the linked JavaScript object, and any children it may have.
        """
        for _, v in self._children.items():
            v.free()
        self._exe.free(self.ffid)


class EventEmitterProxy(Proxy):

    """A unique type of Proxy made whenever an EventEmitter is returned,
    containing special wrapped on, off, and once functions that ensure the
    python side of the bridge knows that this particular proxy is for NodeJS
    events."""

    def on(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Register a python function or coroutine as a listener for this EventEmitter.

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator

        Example:
            .. code-block:: python

                def handleIncrement(this, counter):
                    print("Incremented", counter)
                    # Stop listening.
                    myEmitter.off( 'increment', handleIncrement)

                #assign callback handler.
                myEmitter.on('increment',handleIncrement)
        """
        config = self._config()

        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if config.node_emitter_patches:

            def handler(*args, **kwargs):
                listener(self, *args, **kwargs)

            listener = handler
        else:
            pass

        # print(s)
        # emitter.on(event, listener)
        # self.get("on").call_s(event, listener)
        self.get("on").call_s(event, listener)
        log_info(
            "On for: emitter %s, event %s, function %s, iffid %s",
            self,
            event,
            listener,
            getattr(listener, "iffid"),
        )

        # Persist the FFID for this callback object so it will get deregistered properly.

        ffid = getattr(listener, "iffid")
        setattr(listener, "ffid", ffid)

        self._loop().callbacks[ffid] = listener

        return listener

    async def on_a(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Asyncronous equivalent of on.

        Register a python function or coroutine as a listener for this EventEmitter.

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator
        Example:
            .. code-block:: python

                async def handleIncrement(this, counter):
                    print("Incremented", counter)
                    # Stop listening.
                    await myEmitter.off_a( 'increment', handleIncrement)

                await myEmitter.on_a("increment",handleIncrement)

        """
        config = self._config()

        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if config.node_emitter_patches:

            def handler(*args, **kwargs):
                listener(self, *args, **kwargs)

            listener = handler
        else:
            pass

        # print(s)
        # emitter.on(event, listener)
        # self.get("on").call_s(event, listener)
        onv = await self.get_a("on")
        await onv.call_a(event, listener)
        log_info(
            "On for: emitter %s, event %s, function %s, iffid %s",
            self,
            event,
            listener,
            getattr(listener, "iffid"),
        )

        # Persist the FFID for this callback object so it will get deregistered properly.

        ffid = getattr(listener, "iffid")
        setattr(listener, "ffid", ffid)

        self._loop().callbacks[ffid] = listener

        return listener

    def off_s(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Unregisters listener as a listener function from this EventEmitter.

        Args:
            event (str): The name of the event to unregister the handler from.
            handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.


        Example:
            .. code-block:: python

                myEmitter.off_s('increment', handleIncrement)
        """
        log_warning("Off for: emitter %s, event %s, function %s", self, event, listener)
        target_ffid = getattr(listener, "ffid")
        self.get_s("off").call_s(event, listener)

        del self._loop().callbacks[target_ffid]

    async def off_a(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Asyncronous variant of off_s.

        Unregisters listener as a listener function from this EventEmitter.

        Args:
            event (str): The name of the event to unregister the handler from.
            handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.


        Example:
            .. code-block:: python

                await myEmitter.off_a('increment', handleIncrement)
        """
        log_info("Async Off for: emitter %s, event %s, function %s", self, event, listener)
        target_ffid = getattr(listener, "ffid")
        await (await self.get_a("off")).call_a(event, listener)

        del self._loop().callbacks[target_ffid]

    def once(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Register a python function or coroutine as a one time event listener for this EventEmitter.
        Once it's called, the function will be Unregistered!

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator

        Example:
            .. code-block:: python
                def onceIncrement(this, *args):
                    print("Hey, I'm only called once !")
                myEmitter.once('increment', onceIncrement)
        """
        print("SUPER PROXY ONCE")
        config = self._config()
        i = hash(listener)

        def handler(*args, **kwargs):
            if config.node_emitter_patches:
                listener(self, *args, **kwargs)
            else:
                listener(*args, **kwargs)
            del config.event_loop.callbacks[i]

        log_info("once for: emitter %s, event %s, function %s", self, event, listener)
        output = self.get("once").call_s(event, listener)

        self._loop().callbacks[i] = handler
        return output

    async def once_a(self, event: str, listener: Union[Callable, Coroutine]):
        """
        Asyncronous equivalent of once.

        Register a python function or coroutine as a one time event listener for this EventEmitter.
        Once it's called, the function will be Unregistered!

        Args:
            event (str): The name of the event to listen for.
            listener: (Union[Callable,Coroutine]): The function or coroutine function assigned as the event listener.
        Returns:
            Callable: the listener arg passed in, for the @On Decorator

        Example:
            .. code-block:: python
                async def onceIncrement(this, *args):
                    print("Hey, I'm only called once !")
                await myEmitter.once_a('increment', onceIncrement)
        """
        print("SUPER PROXY ONCE")
        config = self._config()
        i = hash(listener)

        def handler(*args, **kwargs):
            if config.node_emitter_patches:
                listener(self, *args, **kwargs)
            else:
                listener(*args, **kwargs)
            del config.event_loop.callbacks[i]

        log_info("once for: emitter %s, event %s, function %s", self, event, listener)
        oncev = await self.get_a("once")
        output = await oncev.call_a(event, listener)
        # output = self.get("once").call_s(event, listener)

        self._loop().callbacks[i] = handler
        return output


INTERNAL_VARS_NODE = ["node_op", "_proxy", "_prev", "_op", "_kwargs", "_depth"]


class NodeOp:
    """Represents a Node operation for asynchronous execution.

    When the Proxy's ``_asyncmode`` attribute is set to True, it does not make calls
    to Node.js immediately, instead creating a stack of linked NodeOp objects that
    contains the kwargs for each call and a link to the previous NodeOp. Once the
    await keyword is used, this stack calls the aget, aset, and call_a elements
    of each returned proxy from the bottom up.

    Attributes:
        _proxy (Proxy): The Proxy object associated with this Node operation.
        _prev (NodeOp): The previous NodeOp in the operation stack.  None if it's the root node.
        _op (str, optional): The type of operation, such as 'get', 'set', or 'call'.
        _depth (int): The depth of this NodeOp chain
        _kwargs (dict, optional): The keyword arguments for the operation.

    """

    def __init__(
        self,
        proxy: Proxy = None,
        prev: NodeOp = None,
        op: Literal["get", "set", "call", "getitem", "setitem", "serialize"] = None,
        kwargs=None,
    ):
        self._proxy: Proxy = proxy
        self._prev: NodeOp = prev
        self._depth = 0
        if self._prev is not None:
            self._depth = self._prev._depth + 1
        self._op = op
        self._kwargs = kwargs
        self.node_op = True

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
        if self._op == "serialize":
            return await proxy.get_dict_a(**self._kwargs)
        raise InvalidNodeOp(f"Invalid Operation {self._op}!")

    def process_sync(self):
        """
        Called when the built NodeOp chain is awaited.
        Recursively process each node in the stack.
        """
        proxy = self._proxy
        if self._prev is not None:
            proxy = self._prev.process_sync()

        if self._op == "set":
            return proxy.set_s(**self._kwargs)
        if self._op == "get":
            return proxy.get_s(**self._kwargs)
        if self._op == "call":
            args = self._kwargs["args"]
            self._kwargs.pop("args")
            return proxy.call_s(*args, **self._kwargs)
        if self._op == "getitem":
            return proxy.get_item(**self._kwargs)
        if self._op == "setitem":
            return proxy.set_item(**self._kwargs)
        if self._op == "serialize":
            return proxy.get_dict(**self._kwargs)
        raise InvalidNodeOp(f"Invalid Operation {self._op}!")

    def __call__(self, *args, timeout=10, forceRefs=False, coroutine=False):
        return NodeOp(
            prev=self,
            op="call",
            kwargs={
                "args": args,
                "timeout": timeout,
                "forceRefs": forceRefs,
                "coroutine": coroutine,
            },
        )

    def __getattr__(self, attr):
        if attr in INTERNAL_VARS_NODE:
            raise InvalidNodeOp("Something is going wrong, please check your code.")
        print("get", attr)
        if self._depth > 10:
            log_error(traceback.format_stack(limit=25))
            raise InvalidNodeOp("The node chain has exceeded a depth of 10.  Check your code.")
        return NodeOp(prev=self, op="get", kwargs={"attr": attr})

    def __iter__(self):
        return NodeOp(prev=self, op="iter", kwargs={})

    def __next__(self):
        return NodeOp(prev=self, op="next", kwargs={})

    def __setattr__(self, name, value):
        if name in INTERNAL_VARS_NODE:
            object.__setattr__(self, name, value)
            return

        raise AsyncReminder("You should be using .set in amode!")

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

    async def set_item_a(self, name: str, value: Any) -> NodeOp:
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
        newnode = NodeOp(prev=self, op="setitem", kwargs={"name": name, "value": value})
        return await newnode.process()

    def __aiter__(self):
        """
        Async variant of iterator.
        """
        # Early proxy iteration...

        log_warning(
            "WARNING.  NODEOP CHAIN HAD TO TERMINATE SYNCRONOUSLY FOR ASYNCRONOUS ITERATOR!",
            exc_info=True,
        )

        proxy = self.process_sync()
        return proxy.__aiter__()

    async def valueOf(self):
        """asyncrounously call valueOf"""
        target_proxy = await self.process()
        return target_proxy.valueOf()

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
        return previous + f"[{self._op}, {self._depth}, {self._kwargs},P:{str(self._proxy)}]"
