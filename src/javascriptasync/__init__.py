# This file contains all the exposed modules
import asyncio
from typing import Any, Coroutine, Optional, Callable, Union
from . import config
from .config import Config
from .logging import log_print,logs
from .proxy import Proxy

import threading, inspect, time, atexit, os, sys
from .errors import NoAsyncLoop

def init_js():
    '''Initalize the node.js bridge.'''
    log_print('Starting up js config.')
    Config('')

def kill_js():
    Config('').kill()
    print('killed js')


def require(name:str, version:Optional[str]=None)->Proxy:
    """
    Import an npm package. and return it as a Proxy.

    Args:
        name (str): The name of the npm package you want to import.
                    If using a relative import (starting with . or /),
                    it will load the file relative to where your calling script is.
        version (str, optional): The version of the npm package you want to install.
                                 Default is None.

    Returns:
        Proxy: The imported package or module, as a Proxy.
    """
    calling_dir = None
    conf=Config.get_inst()
    if name.startswith("."):
        # Some code to extract the caller's file path, needed for relative imports
        try:
            namespace = sys._getframe(1).f_globals
            cwd = os.getcwd()
            rel_path = namespace["__file__"]
            abs_path = os.path.join(cwd, rel_path)
            calling_dir = os.path.dirname(abs_path)
        except Exception:
            # On Notebooks, the frame info above does not exist, so assume the CWD as caller
            calling_dir = os.getcwd()

    return conf.global_jsi.require(name, version, calling_dir, timeout=900)

async def require_a(name:str, version:Optional[str]=None)->Proxy:
    """
    Asyncronously import an npm package as a Coroutine,. and return it as a Proxy.

    Args:
        name (str): The name of the npm package you want to import.
                    If using a relative import (starting with . or /),
                    it will load the file relative to where your calling script is.
        version (str, optional): The version of the npm package you want to install.
                                 Default is None.

    Returns:
        Proxy: The imported package or module, as a Proxy.
    """
    calling_dir = None
    conf=Config.get_inst()
    if name.startswith("."):
        # Some code to extract the caller's file path, needed for relative imports
        try:
            namespace = sys._getframe(1).f_globals
            cwd = os.getcwd()
            rel_path = namespace["__file__"]
            abs_path = os.path.join(cwd, rel_path)
            calling_dir = os.path.dirname(abs_path)
        except Exception:
            # On Notebooks, the frame info above does not exist, so assume the CWD as caller
            calling_dir = os.getcwd()
    coro=conf.global_jsi.require(name, version, calling_dir, timeout=900,coroutine=True)
    #req=conf.global_jsi.require
    return await coro

def get_console() -> Proxy:
    """
    Returns the console object from the JavaScript context.

    The console object can be used to print direct messages in your Node.js console from the Python context.
    It retrieves the console object from the global JavaScript Interface (JSI) stored in the Config singleton instance.

    Returns:
        Proxy: The JavaScript console object.
    """
    return Config.get_inst().global_jsi.console

def get_globalThis() -> Proxy:
    """
    Returns the globalThis object from the JavaScript context.

    The globalThis object is a standard built-in object in JavaScript, akin to 'window' in a browser or 'global' in Node.js.
    It provides a universal way to access the global scope in any environment. This function offers access to this object
    from the Python context.

    Returns:
        Proxy: The JavaScript globalThis object.
    """
    globalThis = Config.get_inst().global_jsi.globalThis
    return globalThis

def get_RegExp() -> Proxy:
    """
    Returns the RegExp (Regular Expression) object from the JavaScript context.

    Regular Expressions in JavaScript are utilized for pattern-matching and "search-and-replace" operations on text.
    This function retrieves the RegExp object and makes it accessible in the Python environment.

    Returns:
        Proxy: The JavaScript RegExp object.
    """
    return Config.get_inst().global_jsi.RegExp



def eval_js(js: str, timeout: int = 10) -> Any:
    """
    Evaluate JavaScript code within the current Python context.

    Parameters:
        js (str): The JavaScript code to evaluate.
        timeout (int): Maximum execution time for the JavaScript code in seconds (default is 10).

    Returns:
        Any: The result of the JavaScript evaluation.
    """
    frame = inspect.currentframe()
    
    conf=Config.get_inst()
    rv = None
    try:
        local_vars = {}
        for local in frame.f_back.f_locals:
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        rv = conf.global_jsi.evaluateWithContext(js, local_vars,  timeout=timeout,forceRefs=True)
    finally:
        del frame
    return rv


async def eval_js_a(js: str, timeout: int = 10, as_thread: bool = False) -> Any:
    """
    Asynchronously evaluate JavaScript code within the current Python context.

    Args:
        js (str): The asynchronous JavaScript code to evaluate.
        timeout (int, optional): Maximum execution time for JavaScript code in seconds.
                                 Defaults to 10 seconds.
        as_thread (bool, optional): If True, run JavaScript evaluation in a syncronous manner using asyncio.to_thread.
                                   Defaults to False.

    Returns:
        Any: The result of evaluating the JavaScript code.
    """
    frame = inspect.currentframe()
    conf=Config.get_inst()
    rv = None
    try:
        local_vars = {}
        locals=frame.f_back.f_locals
        
        for local in frame.f_back.f_locals:
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        if not as_thread:
            rv = conf.global_jsi.evaluateWithContext(js, local_vars, timeout=timeout,forceRefs=True,coroutine=True)
        else:
            rv = asyncio.to_thread(conf.global_jsi.evaluateWithContext,js, local_vars, timeout=timeout,forceRefs=True)
    finally:
        del frame
    return await rv

def AsyncTask(start=False):
    """
    A decorator for creating a psuedo-asynchronous task out of a syncronous function.

    Args:
        start (bool, optional): Whether to start the task immediately. Default is False.

    Returns:
        callable: A decorator function for creating asynchronous tasks.
    """
    def decor(fn):
        conf=Config.get_inst() 
        fn.is_async_task = True
        t = conf.event_loop.newTaskThread(fn)
        if start:
            t.start()

    return decor
def AsyncTaskA():
    """
    A decorator for marking coroutines as asynchronous tasks.

    Returns:
        callable: A decorator function for marking functions as asynchronous tasks.
    """
    def decor(fn):
        conf=Config.get_inst() 
        fn.is_async_task = True
        return fn
        # t = conf.event_loop.newTask(fn)
        # if start:
        #     t.start()

    return decor

class AsyncTaskUtils:
    """
    Utility class for managing asyncio tasks through the library.
    """
    @staticmethod
    async def start(method:Coroutine):
        """
        Start an asyncio task.

        Args:
            method (Coroutine): The coroutine to start as an asyncio task.
        """
        conf=Config.get_inst()
        await conf.event_loop.startTask(method)
    @staticmethod
    async def stop(method:Coroutine):
        """
        Stop an asyncio task.

        Args:
            method (Coroutine): The coroutine representing the task to stop.
        """
        conf=Config.get_inst()
        await conf.event_loop.stopTask(method)
    @staticmethod
    async def abort(method:Coroutine,killAfter:float=0.5):
        """
        Abort an asyncio task.

        Args:
            method (Coroutine): The coroutine representing the task to abort.
            killAfter (float, optional): The time (in seconds) to wait before forcefully killing the task. Default is 0.5 seconds.

        """
        conf=Config.get_inst()
        await conf.event_loop.abortTask(method,killAfter)

class ThreadUtils:
    """
    Utility class for managing threads through the library.
    """
    @staticmethod
    def start(method:Callable):
        """
        Assign a method to a thread, and start that thread.

        Args:
            method (Callable): The function to execute in a separate thread.
        """
        conf=Config.get_inst()
        conf.event_loop.startThread(method)
    @staticmethod
    def stop(method:Callable):
        """
        Stop the thread that was assigned the passed in function.

        Args:
            method (Callable): The function representing the thread to stop.
        """
        conf=Config.get_inst()
        conf.event_loop.stopThread(method)
    @staticmethod
    def abort(method:Callable,killAfter:float=0.5):
        """
        Abort Stop the thread that was assigned the passed in function.

        Args:
            method (Callable): The function representing the thread to abort.
            killAfter (float, optional): The time (in seconds) to wait before forcefully killing the thread. Default is 0.5 seconds.
        """
        conf=Config.get_inst()
        conf.event_loop.abortThread(method,killAfter)

# You must use this Once decorator for an EventEmitter in Node.js, otherwise
# you will not be able to off an emitter.
def On(emitter: object, event: str, asyncio_loop: Optional[asyncio.BaseEventLoop] = None) -> Callable:
    """
    Decorator for registering an event handler with an EventEmitter.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to listen for.
        asyncio_loop (Optional[asyncio.BaseEventLoop]): The asyncio event loop (required for coroutine handlers).

    Returns:
        Callable: The decorated event handler function.

    Raises:
        NoAsyncLoop: If asyncio_loop is not set when using a coroutine handler.

    Example:
        
        @On(myEmitter, 'increment', asyncloop)
        async def handleIncrement(this, counter):
            
            pass
    """
    def decor(_fn):
        conf=Config.get_inst()
        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if conf.node_emitter_patches:
            def handler(*args, **kwargs):
                _fn(emitter, *args, **kwargs)

            fnb = handler
        else:
            fnb = _fn
        # If fn is a coroutine, call this.
        if inspect.iscoroutinefunction(fnb):
            #Wrap around run_coroutine_threadsafe
            if asyncio_loop==None:
                raise NoAsyncLoop("in @On, asyncio_loop wasn't set!")
            def wraparound(*args, **kwargs):
                asyncio.run_coroutine_threadsafe(fnb(*args, **kwargs), asyncio_loop)
            fn=wraparound
        else:
            fn=fnb
        s=str(repr(emitter)).replace("\n",'')
        print(s)
        print(inspect.iscoroutinefunction(fn))
        emitter.on(event, fn)
        logs.info("On for: emitter %s, event %s, function %s, iffid %s",s,event,fn,getattr(fn, "iffid"))
        # We need to do some special things here. Because each Python object
        # on the JS side is unique, EventEmitter is unable to equality check
        # when using .off. So instead we need to avoid the creation of a new
        # PyObject on the JS side. To do that, we need to persist the FFID for
        # this object. Since JS is the autoritative side, this FFID going out
        # of refrence on the JS side will cause it to be destoryed on the Python
        # side. Normally this would be an issue, however it's fine here.
        ffid = getattr(fn, "iffid")
        setattr(fn, "ffid", ffid)
        
        conf.event_loop.callbacks[ffid] = fn
        print('cleared on.')
        return fn

    return decor


# The extra logic for this once function is basically just to prevent the program
# from exiting until the event is triggered at least once.
def Once(emitter: object, event: str, asyncio_loop: Optional[asyncio.BaseEventLoop] = None) -> Callable:
    
    """
    Decorator for registering a one-time event handler with an EventEmitter.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to listen for.
        asyncio_loop (Optional[asyncio.BaseEventLoop]): The asyncio event loop (required for coroutine handlers).

    Returns:
        Callable: The decorated one-time event handler function.

    Raises:
        NoAsyncLoop: If asyncio_loop is not set when using a coroutine handler.

    Example:

        @Once(myEmitter, 'increment', asyncloop)
        async def handleIncrementOnce(this, counter):
        
            pass
    """
    def decor(fna):
        i = hash(fna)
        if inspect.iscoroutinefunction(fna):
            if asyncio_loop==None:
                raise NoAsyncLoop("in @Off, asyncio_loop wasn't set!")
            def wraparound(*args, **kwargs):
                asyncio.run_coroutine_threadsafe(fna(*args, **kwargs), asyncio_loop)
            fn=wraparound
        else:
            fn=fna
        conf=Config.get_inst()
        def handler(*args, **kwargs):
            if conf.node_emitter_patches:
                fn(emitter, *args, **kwargs)
            else:
                fn(*args, **kwargs)
            del conf.event_loop.callbacks[i]

        emitter.once(event, handler)
        
        conf.event_loop.callbacks[i] = handler

    return decor


def off(emitter: object, event: str, handler: Union[Callable,Coroutine]):
    """
    Unregisters an event handler from an EventEmitter.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to unregister the handler from.
        handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.

    Example:
        off(myEmitter, 'increment', handleIncrement)
    """
    emitter.off(event, handler)
    conf=Config.get_inst()
    del conf.event_loop.callbacks[getattr(handler, "ffid")]


def once(emitter: object, event: str)->Any:
    """
    Listens for an event emitted once and returns a value when it occurs.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.

    Example:
        val = once(myEmitter, 'increment')
    """
    conf=Config.get_inst()
    val = conf.global_jsi.once(emitter, event, timeout=1000)
    return val


async def off_a(emitter: object, event: str, handler: Union[Callable,Coroutine]):
    """
    Asynchronously unregisters an event handler from an EventEmitter.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to unregister the handler from.
        handler (Callable or Coroutine): The event handler function to unregister.

    Example:
        await off_a(myEmitter, 'increment', handleIncrement)
    """
    await emitter.off(event, handler, coroutine=True)
    conf=Config.get_inst()
    del conf.event_loop.callbacks[getattr(handler, "ffid")]

async def once_a(emitter: object, event: str)->Any:
    """
    Asynchronously listens for an event emitted once and returns a value when it occurs.

    Args:
        emitter (object): The EventEmitter instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.

    Example:
        val = await once_a(myEmitter, 'increment')
    """
    conf=Config.get_inst()
    val = await conf.global_jsi.once(emitter, event, timeout=1000,  coroutine=True)
    return val
