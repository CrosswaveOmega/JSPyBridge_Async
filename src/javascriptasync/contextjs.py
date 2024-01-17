import asyncio
import os
import sys
import inspect

from typing import Any, Optional

from .configjs import JSConfig
from .core.jslogging import log_print
from .proxy import Proxy
from .errorsjs import NoAsyncLoop


class JSContext:
    """
    experimental mode
    """

    __slots__ = ["config", "_imported", "_known_packages"]

    def __init__(self):
        """Initialize the JSContext and retrieve the Config instance."""
        # Config("NoStartup")
        self.config: JSConfig = JSConfig(manual_terminate=True)
        self._imported = {}
        self._known_packages = {}

    def __getattr__(self, __name: str) -> Any:
        if __name in self._imported:
            return self._imported[__name]
        raise AttributeError(f"No known package {__name}")

    def __getitem__(self, __name: str) -> Any:
        if __name in self._imported:
            return self._imported[__name]
        raise AttributeError(f"No known package {__name}")

    def __del__(self):
        keys = list(self._imported.keys())
        for k in keys:
            log_print("purging key ", k)
            del self._imported[k]
        self.kill_js()

    def init_js(self):
        """Initialize a new bridge to node.js if it does not already exist."""
        log_print("Starting up js config.")
        # self.config = Config("")
        self.config.startup()

    async def init_js_a(self):
        """Initialize a new node.js bridge if it does not already exist,
        and set the callback event loop to the current asyncio loop."""
        # self.config = Config("")

        await self.config.startup_async()

        self.config.set_asyncio_loop(asyncio.get_event_loop())

    async def set_async_loop(self):
        """Set the callback event loop to the current asyncio loop.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.
        """

        self.config.set_asyncio_loop(asyncio.get_event_loop())

    def kill_js(self):
        """Shut down the active NodeJS context."""
        if self.config.state != 2:
            return

        self.config.terminate()
        self.config.reset_self()
        print("killed js")

    def require(
        self, name: str, version: Optional[str] = None, store_as: Optional[str] = None
    ) -> Proxy:
        """
        Import an npm package, and return it as a Proxy.
        If the required package isn't found, then
        javascriptasync will install it within the librarywide node_modules folder.

        Args:
            name (str): The name of the npm package you want to import.
                        If using a relative import (starting with . or /),
                        it will load the file relative to where your calling script is.
            version (str, optional): The version of the npm package you want to install.
                                     Default is None.

        Returns:
            Proxy: The imported package or module, as a Proxy.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        if name in self._known_packages:
            proxyname = self._known_packages[name]
            return self._imported[proxyname]
        calling_dir = None
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
        require = self.config.global_jsi.get("require")
        proxy = require(name, version, calling_dir, timeout=900)
        if store_as:
            self._imported[store_as] = proxy
            self._known_packages[name] = store_as
        return proxy

    async def require_a(
        self,
        name: str,
        version: Optional[str] = None,
        amode: bool = False,
        store_as: Optional[str] = None,
    ) -> Proxy:
        """
        Asynchronously import an npm package and return it as a Proxy.
        If the required package isn't found, then
        javascriptasync will install it within the librarywide node_modules folder.

        Args:
            name (str): The name of the npm package you want to import.
                        If using a relative import (starting with . or /),
                        it will load the file relative to where your calling script is.
            version (str, optional): The version of the npm package you want to install.
                                     Default is None.
            amode(bool, optional): If the Proxy's async call stacking mode should be enabled.
                Default false.
            store_as(str,optional): Name to store this required module as within the context.  can be retrieved via context.[store_as]

        Returns:
            Proxy: The imported package or module, as a Proxy.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        if name in self._known_packages:
            proxyname = self._known_packages[name]
            return self._imported[proxyname]
        calling_dir = None
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
        coro = self.config.global_jsi.get("require").call_a(name, version, calling_dir, timeout=900)
        module = await coro
        if amode:
            module.toggle_async_chain(True)
            await module.getdeep()
        if store_as:
            self._imported[store_as] = module
            self._known_packages[name] = store_as
        return module

    def get_console(self) -> Proxy:
        """
        Returns the console object from the JavaScript context.

        The console object can be used to print direct messages in your Node.js console from the Python context.
        It retrieves the console object from the global JavaScript Interface (JSI) stored in the Config singleton instance.

        Returns:
            Proxy: The JavaScript console object.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        return self.config.global_jsi.console

    def get_globalThis(self) -> Proxy:
        """
        Returns the globalThis object from the JavaScript context.

        The globalThis object is a standard built-in object in JavaScript,
        akin to 'window' in a browser or 'global' in Node.js.
        It provides a universal way to access the global scope in any environment.
        This function offers access to this object
        from the Python context.

        Returns:
            Proxy: The JavaScript globalThis object.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        globalThis = self.config.global_jsi.globalThis
        return globalThis

    def get_RegExp(self) -> Proxy:
        """
        Returns the RegExp (Regular Expression) object from the JavaScript context.

        Regular Expressions in JavaScript are utilized for pattern-matching and
        "search-and-replace" operations on text.
        This function retrieves the RegExp object
        and makes it accessible in the Python environment.

        Returns:
            Proxy: The JavaScript RegExp object.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        return self.config.global_jsi.RegExp

    def eval_js(self, js: str, timeout: int = 10) -> Any:
        """
        Evaluate JavaScript code within the current Python context.

        Parameters:
            js (str): The JavaScript code to evaluate.
            timeout (int): Maximum execution time for the JavaScript code in seconds (default is 10).

        Returns:
            Any: The result of the JavaScript evaluation.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,  or if the bridge is still being initialization is in progress.

        """
        frame = inspect.currentframe()

        rv = None
        try:
            local_vars = {}
            for local in frame.f_back.f_locals:
                if not local.startswith("__"):
                    local_vars[local] = frame.f_back.f_locals[local]
            context = self.config.global_jsi.get_s("evaluateWithContext")

            rv = context.call_s(js, local_vars, timeout=timeout, forceRefs=True)
        finally:
            del frame
        return rv

    async def eval_js_a(self, js: str, timeout: int = 10, as_thread: bool = False) -> Any:
        """
        Asynchronously evaluate JavaScript code within the current Python context.

        Args:
            js (str): The asynchronous JavaScript code to evaluate.
            timeout (int, optional): Maximum execution time for JavaScript code in seconds.
                                     Defaults to 10 seconds.
            as_thread (bool, optional): If True, run JavaScript evaluation in a
                                       syncronous manner using asyncio.to_thread.
                                       Defaults to False.

        Returns:
            Any: The result of evaluating the JavaScript code.

        Raises:
            NoConfigInitialized: If `init_js` or `init_js_a` was not called prior,
            or if the bridge is still being initialization is in progress.

        """
        frame = inspect.currentframe()
        rv = None
        try:
            local_vars = {}
            locals = frame.f_back.f_locals

            for local in frame.f_back.f_locals:
                if not local.startswith("__"):
                    local_vars[local] = frame.f_back.f_locals[local]
            if not as_thread:
                context = self.config.global_jsi.get_s("evaluateWithContext")

                rv = context.call_s(js, local_vars, timeout=timeout, forceRefs=True, coroutine=True)
            else:
                print(local_vars)
                context = self.config.global_jsi.get_s("evaluateWithContext")
                rv = asyncio.to_thread(context, js, local_vars, timeout=timeout, forceRefs=True)
        finally:
            del frame
        return await rv
