# This file contains all the exposed modules
import asyncio
from typing import Any, Coroutine, Optional, Callable, Union
from . import config
from .config import Config
from .logging import log_print, logs
from .proxy import Proxy

import threading, inspect, time, atexit, os, sys
from .errors import NoAsyncLoop


def init_js():
    """Initalize a new bridge to node.js if it does not already exist."""

    log_print("Starting up js config.")
    Config("")


async def init_js_a():
    """Initalize a new node.js bridge if it does not already exist,
    and set the callback event loop to the current asyncio loop."""
    Config("")
    conf = Config.get_inst()

    conf.set_asyncio_loop(asyncio.get_event_loop())


async def set_async_loop():
    """Set the callback event loop to the current asyncio loop.

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """
    conf = Config.get_inst()
    conf.set_asyncio_loop(asyncio.get_event_loop())


def kill_js():
    Config("").kill()
    print("killed js")


def require(name: str, version: Optional[str] = None) -> Proxy:
    """
    Import an npm package, and return it as a Proxy.

    Args:
        name (str): The name of the npm package you want to import.
                    If using a relative import (starting with . or /),
                    it will load the file relative to where your calling script is.
        version (str, optional): The version of the npm package you want to install.
                                 Default is None.

    Returns:
        Proxy: The imported package or module, as a Proxy.


    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """
    calling_dir = None
    conf = Config.get_inst()
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


async def require_a(name: str, version: Optional[str] = None, amode: bool = False) -> Proxy:
    """
    Asyncronously import an npm package and return it as a Proxy.

    Args:
        name (str): The name of the npm package you want to import.
                    If using a relative import (starting with . or /),
                    it will load the file relative to where your calling script is.
        version (str, optional): The version of the npm package you want to install.
                                 Default is None.
        amode(bool, optional): If the Proxy's async call stacking mode should be enabled.
            Default false.

    Returns:
        Proxy: The imported package or module, as a Proxy.


    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """
    calling_dir = None
    conf = Config.get_inst()
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
    coro = conf.global_jsi.require(name, version, calling_dir, timeout=900, coroutine=True)
    # req=conf.global_jsi.require
    module = await coro
    if amode:
        module._asyncmode = True
    return module


def get_console() -> Proxy:
    """
    Returns the console object from the JavaScript context.

    The console object can be used to print direct messages in your Node.js console from the Python context.
    It retrieves the console object from the global JavaScript Interface (JSI) stored in the Config singleton instance.

    Returns:
        Proxy: The JavaScript console object.

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

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

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

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

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

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

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """
    frame = inspect.currentframe()

    conf = Config.get_inst()
    rv = None
    try:
        local_vars = {}
        for local in frame.f_back.f_locals:
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        rv = conf.global_jsi.evaluateWithContext(js, local_vars, timeout=timeout, forceRefs=True)
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

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """
    frame = inspect.currentframe()
    conf = Config.get_inst()
    rv = None
    try:
        local_vars = {}
        locals = frame.f_back.f_locals

        for local in frame.f_back.f_locals:
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        if not as_thread:
            rv = conf.global_jsi.evaluateWithContext(js, local_vars, timeout=timeout, forceRefs=True, coroutine=True)
        else:
            rv = asyncio.to_thread(conf.global_jsi.evaluateWithContext, js, local_vars, timeout=timeout, forceRefs=True)
    finally:
        del frame
    return await rv


def AsyncThread(start=False):
    """
    A decorator for creating a psuedo-asynchronous task out of a syncronous function.

    Args:
        start (bool, optional): Whether to start the task immediately. Default is False.

    Returns:
        callable: A decorator function for creating asynchronous tasks.

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """

    def decor(fn):
        conf = Config.get_inst()
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

    Raises:
        NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

    """

    def decor(fn):
        conf = Config.get_inst()
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
    async def start(method: Coroutine):
        """
        Start an asyncio task.

        Args:
            method (Coroutine): The coroutine to start as an asyncio task.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        conf = Config.get_inst()
        await conf.event_loop.startTask(method)

    @staticmethod
    async def stop(method: Coroutine):
        """
        Stop an asyncio task.

        Args:
            method (Coroutine): The coroutine representing the task to stop.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.
        """
        conf = Config.get_inst()
        await conf.event_loop.stopTask(method)

    @staticmethod
    async def abort(method: Coroutine, killAfter: float = 0.5):
        """
        Abort an asyncio task.

        Args:
            method (Coroutine): The coroutine representing the task to abort.
            killAfter (float, optional): The time (in seconds) to wait before forcefully killing the task. Default is 0.5 seconds.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        conf = Config.get_inst()
        await conf.event_loop.abortTask(method, killAfter)


class ThreadUtils:
    """
    Utility class for managing threads through the library.
    """

    @staticmethod
    def start(method: Callable):
        """
        Assign a method to a thread, and start that thread.

        Args:
            method (Callable): The function to execute in a separate thread.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        conf = Config.get_inst()
        conf.event_loop.startThread(method)

    @staticmethod
    def stop(method: Callable):
        """
        Stop the thread that was assigned the passed in function. Please try to utilize this instead of abort() in general situations.

        Args:
            method (Callable): The function representing the thread to stop.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.
        """
        conf = Config.get_inst()
        conf.event_loop.stopThread(method)

    @staticmethod
    def abort(method: Callable, kill_after: float = 0.5):
        """
        Abort the thread that was assigned the passed in function.
        Use if you want to make sure that a thread has stopped, but please try to use stop() instead for general use.

        Args:
            method (Callable): The function representing the thread to abort.
            kill_after (float, optional): The time (in seconds) to wait before forcefully killing the thread. Default is 0.5 seconds.

        Raises:
            NoConfigInitalized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        conf = Config.get_inst()
        conf.event_loop.abortThread(method, kill_after)


# from javascriptasync.emitters import On, Once, off,once,off_a,once_a
