'''
The core config class.
'''
from __future__ import annotations
import asyncio
import os
from .proxy import Proxy,Executor
from .events import EventLoop
from .logging import log_print,logs, print_path
from .errors import NoConfigInitalized
import threading, inspect, time, atexit, sys
class Null:
    def __getattr__(self, *args, **kwargs):
        raise Exception(
            "The JavaScript process has crashed. Please restart the runtime to access JS APIs."
        )


class JSConfig(object):
    '''A configuration class for managing JavaScript runtime settings.

    This class is used to configure and manage the JavaScript runtime environment.

    Attributes:
        event_loop (EventLoop): The event loop for JavaScript execution.
        event_thread (Thread): The thread running the `event_loop.loop` method.
        executor (Executor): The executor for JavaScript code execution.
        global_jsi (Proxy): The root interface to JavaScript with FFID 0.
        fast_mode (bool): Whether to enable fast mode for JavaScript execution.
        node_emitter_patches (bool): Whether patches are needed for legacy node versions.
        dead (str): message for when the node.js process crashes.
    '''


    def __init__(self):
        """
        Initializes a new instance of JSConfig.

        It sets default values for the JavaScript runtime configuration.
        """
        self.dead="\n** The Node process has crashed. Please restart the runtime to use JS APIs. **\n"
        self.event_loop: EventLoop = None
        self.event_thread: threading.Thread = None
        self.executor: Executor = None
        self.global_jsi: Proxy = None
        self.fast_mode: bool = False
        self.node_emitter_patches: bool = False

    def startup(self):
        """
        Starts the JavaScript runtime environment.

        This method initializes the event loop, executor, and global_jsi for JavaScript execution.
        """
        self.event_loop: EventLoop = EventLoop(self)
        self.event_thread: threading.Thread = threading.Thread(target=self.event_loop.loop, args=(), daemon=True)
        self.event_thread.start()

        self.executor: Executor = Executor(self, self.event_loop)
        # # The "root" interface to JavaScript with FFID 0
        self.global_jsi: Proxy = Proxy(self.executor, 0)
        self.fast_mode: bool = False
        self.node_emitter_patches: bool = False
        atexit.register(self.event_loop.on_exit)


    def check_node_patches(self):
        """
        Checks if node patches are needed and updates node_emitter_patches accordingly.
        """
        if self.global_jsi.needsNodePatches():
            self.node_emitter_patches = True

    def reset_self(self):
        """
        Resets all attributes to None, except for global_jsi which will throw an error.
        """
        self.event_loop = None
        self.event_thread = None
        self.executor = None
        self.global_jsi = Null()
        self.fast_mode = False

    def is_main_loop_active(self):
        """
        Checks if the main event loop is active.

        Returns:
            bool: True if the main event loop is active, False otherwise.
        """
        if not self.event_thread or self.event_loop:
            return False
        return self.event_thread.is_alive() and self.event_loop.active


class classproperty:
    def __init__(self,func):
        self.fget=func
    def __get__(self,instance,owner):
        return self.fget(owner)
class Config:
    """

    This class is a singleton container for managing a JSConfig instance. It ensures that only one instance
    of JSConfig is created and provides methods for accessing and controlling it.

    Attributes:
        _instance (JSConfig): The instance of the JSConfig class.
        _initalizing (bool): Flag indicating whether initialization is in progress.

    
    """

    _instance = None
    _initalizing=False
    def __init__(self, arg='none'):
        """
        Initializes the Config class and JSConfig instance.

        Args:
            arg: Description of the argument (replace with a meaningful description).
            asyncmode (bool, optional): Whether to enable asynchronous mode. Defaults to False.

        Raises:
            Exception: If JSConfig is not initialized or initialization is in progress.
        """
        frame=inspect.currentframe()
        last_path=print_path(frame.f_back)
        logs.debug(f'attempted init:[{last_path}]')
        if not Config._instance and not Config._initalizing:
            Config._initalizing=True
            instance = JSConfig()
            Config._instance = instance
            Config._instance.startup()
            Config._initalizing=False
        elif Config._initalizing:
            frame=inspect.currentframe()
            lp=print_path(frame)
            logs.warning(lp)
            log_print(f'attempted init during initalization:[{lp}]')
    def kill(self):
        """
        Stops the JSConfig event loop and resets the instance.

        Raises:
            Exception: If JSConfig is not initialized or initialization is in progress.
        """
        if not Config._instance:
            raise NoConfigInitalized("Never initalized JSConfig, please call javascriptasync.init_js() somewhere in your code first!")
        elif Config._initalizing:
            raise NoConfigInitalized("Still initalizing JSConfig, please wait!")
        Config._instance.event_loop.on_exit()
        Config._instance=None
    @classmethod
    def inst(cls):
        """
        Returns the JSConfig instance.

        Returns:
            JSConfig: The JSConfig instance.

        """
        return Config._instance
    @classmethod
    def get_inst(cls):
        """
        Checks if JSConfig is initialized and returns the instance.

        Returns:
            JSConfig: The JSConfig instance.

        Raises:
            Exception: If JSConfig is not initialized or initialization is in progress.
        """
        if not Config._instance:
            raise NoConfigInitalized("Never initalized JSConfig, please call javascriptasync.init_js() somewhere in your code first!")
        elif Config._initalizing:
            raise NoConfigInitalized("Still initalizing JSConfig, please wait!")
        return Config._instance


    def __getattr__(self, attr):
        if hasattr(Config,attr):
            return getattr(Config,attr)
        else:
            if hasattr(Config._instance,attr):
                return getattr(Config._instance,attr)
            raise NoConfigInitalized('Tried to get attr on instance object that does not exist.')
    def __setattr__(self, attr,val):
        if hasattr(Config,attr):
            return setattr(Config,attr,val)
        else:
            if hasattr(Config._instance,attr):
                return setattr(Config._instance,attr,val)
            raise NoConfigInitalized('Tried to set attr on instance object that does not exist.')

