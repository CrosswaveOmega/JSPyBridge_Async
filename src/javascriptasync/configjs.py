"""
The core config class.
"""
from __future__ import annotations
import asyncio

import threading, inspect, time, atexit
from typing import List
from .proxy import Proxy
from .executor import Executor
from .events import EventLoop
from .pyi import PyInterface
from .core.jslogging import log_print, logs, print_path, log_warning
from .errorsjs import FatalJavaScriptError, NoConfigInitalized, NodeTerminated


class Null:
    """Dummy classed used to raise terminating exceptions"""

    def __getattr__(self, *args, **kwargs):
        raise NodeTerminated(
            "The JavaScript process has crashed. Please restart the runtime to access JS APIs."
        )


class JSConfig:
    """The configuration class for the JavaScript Bridge.

    This class is used to configure, manage, and facilitatie communication to an EventLoop,
    which filters data in/out to an active node subprocess.
    It also stores all objects necessary for execution of the runtime.

    Attributes:
        event_loop (EventLoop): The event loop to manage io between Python and node.js.
        event_thread (Thread): The thread running the `event_loop.loop` method.
        executor (Executor): The executor for JavaScript code execution.
        global_jsi (Proxy): The root interface to JavaScript with FFID 0.
        pyi (PyInterface): The active PyInterface
        node_emitter_patches (bool): Whether patches are needed for legacy node versions.
        state (int): current state of the runtime.
            0 is awaiting startup.
            1 is starting up.
            2 is active.
            3 is error state.
        manual_terminate (bool): true if the runtime must be terminated explicitly.
    """

    slots = [
        "event_loop",
        "event_thread",
        "pyi",
        "executor",
        "global_jsi",
        "node_emitter_patches",
        "error_stack",
        "state",
        "manual_terminate",
    ]

    def __init__(self, manual_terminate=False):
        """
        Initializes a new instance of JSConfig.

        It sets default values for the JavaScript runtime configuration.
        """
        # self.dead = (
        #     "\n** The Node process has crashed. Please restart the runtime to use JS APIs. **\n"
        # )
        self.event_loop: EventLoop = None
        self.event_thread: threading.Thread = None
        self.pyi: PyInterface = None
        self.executor: Executor = None
        self.global_jsi: Proxy = None
        self.node_emitter_patches: bool = False
        self.error_stack = None
        self.state: int = 0
        self.manual_terminate = manual_terminate

    def _startup_internal(self):
        self.error_stack = None

        self.event_loop: EventLoop = EventLoop(self)
        self.pyi: PyInterface = PyInterface(self)
        self.executor: Executor = Executor(self)

        # self.pyi.set_executor(self.executor)
        self.event_loop.start_connection()
        self.event_thread: threading.Thread = threading.Thread(
            target=self.event_loop.loop, args=(), daemon=True
        )
        self.event_thread.start()

        # # The "root" interface to JavaScript with FFID(Foreign Object Reference ID) 0
        self.global_jsi: Proxy = Proxy(self.executor, 0)
        self.node_emitter_patches: bool = False
        if not self.manual_terminate:
            atexit.register(self.terminate)

    def startup(
        self,
    ):
        """
        Starts a new JavaScript runtime environment.

        This method initializes the event loop, executor, and global_jsi for JavaScript execution.
        """
        if self.state == 0:
            self.state = 1
            self._startup_internal()
            # Give threads some time to run.
            time.sleep(0.2)
            self.state = 2

    async def startup_async(
        self,
    ):
        """
        Starts the JavaScript runtime environment in a non blocking manner.

        This method initializes the event loop, executor, and global_jsi for JavaScript execution.
        """
        if self.state == 0:
            self.state = 1
            self._startup_internal()
            # Give threads some time to run.
            await asyncio.sleep(0.2)
            self.state = 2

    def terminate(self):
        self.event_loop.on_exit()

    def throw_error_state(self, errorst: List[str]):
        self.state = 3
        self.error_stack = errorst
        self.terminate()

    def new_proxy(self, ffid: int) -> Proxy:
        """Create a new Proxy object with only the passed in ffid.

        Args:
            ffid(int): FFID of the newly initalized Proxy object.

        Returns:
            Proxy- a new Proxy object with the current executor and the target ffid.
        """
        proxy = Proxy(self.executor, ffid)
        return proxy

    def get_event_loop(self) -> EventLoop:
        """Return a reference to the active EventLoop used to
        interact with this particular JavaScript runtime.

        Return:
            EventLoop- reference to the initalized EventLoop.
        """
        return self.event_loop

    def push_job(self, job: str):
        """
        Push a job to the active EventLoop's queue.

        Args:
            job(str): String representing the job to push.

        """
        if not self.event_loop:
            raise NoConfigInitalized("event_loop of JSConfig was never set!")
        self.event_loop.queue.put(job)

    def get_pyi(self) -> PyInterface:
        """Get the PyInterface instance in use by this config."""
        return self.pyi

    def set_asyncio_loop(self, loop: asyncio.AbstractEventLoop):
        if self.pyi and self.event_loop:
            self.pyi.current_async_loop = loop

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
        self.pyi = None
        self.global_jsi = Null()
        self.state = 0

    def is_main_loop_active(self):
        """
        Checks if the main event loop is active.

        Returns:
            bool: True if the main event loop is active, False otherwise.
        """
        if not self.event_thread or self.event_loop:
            return False
        return self.event_thread.is_alive() and self.event_loop.active


class Config:

    """

    This class is a singleton container for managing a JSConfig instance.
    It ensures that only one instance
    of JSConfig is created and provides methods for accessing and controlling it.

    Attributes:
        _instance (JSConfig): The instance of the JSConfig class.
        _initalizing (bool): Flag indicating whether initialization is in progress.


    """

    _instance: JSConfig = None
    _initalizing = False
    _reset = False

    def __init__(self, arg="none"):
        """
        Initializes the Config class and JSConfig instance.

        Args:
            arg: unused.

        """
        frame = inspect.currentframe()
        last_path = print_path(frame.f_back)
        logs.debug("attempted init:[%s]", last_path)
        if (not Config._instance and not Config._initalizing) or Config._reset:
            self._instance: JSConfig = JSConfig()
            Config._reset = False
            Config._initalizing = True
            instance = JSConfig()
            Config._instance = instance
            if arg != "NoStartup":
                Config._instance.startup()
            Config._initalizing = False
        elif Config._initalizing:
            frame = inspect.currentframe()
            lp = print_path(frame)
            log_warning(lp)
            log_print(f"attempted init during initalization:[{lp}]")

    def kill(self):
        """
        Stops the JSConfig event loop and resets the instance.

        Raises:
            Exception: If JSConfig is not initialized or initialization is in progress.
        """
        if not Config._instance:
            raise NoConfigInitalized(
                "Never initalized JSConfig, please call javascriptasync.init_js()"
                + "somewhere in your code first!"
            )
        elif Config._initalizing:
            raise NoConfigInitalized("Still initalizing JSConfig, please wait!")
        if Config._instance.state == 2:
            Config._instance.terminate()
            Config._instance.reset_self()

        Config._reset = True

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
            NoConfigInitalized: If JSConfig is not initialized or initialization is in progress.
        """
        if not Config._instance:
            raise NoConfigInitalized(
                "Never initalized JSConfig, please call "
                + "javascriptasync.init_js() somewhere in your code first!"
            )
        elif Config._initalizing:
            raise NoConfigInitalized("Still initalizing JSConfig, please wait!")
        if Config._instance.state == 3:
            raise FatalJavaScriptError("FatalError", Config._instance.error_stack)
        return Config._instance

    @classmethod
    def assign_asyncio_loop(cls, asyncio_loop: asyncio.AbstractEventLoop):
        """
        Checks if JSConfig is initialized, and ensure PYI has a coroutine event loop to utilize.
        Args:
            asyncio_loop: the event loop to set up
        Returns:
            JSConfig: The JSConfig instance.

        Raises:
            Exception: If JSConfig is not initialized or initialization is in progress.
        """
        if not Config._instance:
            raise NoConfigInitalized(
                "Never initalized JSConfig, please call "
                + "javascriptasync.init_js() somewhere in your code first!"
            )
        elif Config._initalizing:
            raise NoConfigInitalized("Still initalizing JSConfig, please wait!")
        Config._instance.set_asyncio_loop(asyncio_loop)

    def __getattr__(self, attr):
        if hasattr(Config, attr):
            return getattr(Config, attr)
        else:
            if hasattr(Config._instance, attr):
                return getattr(Config._instance, attr)
            raise NoConfigInitalized("Tried to get attr on instance object that does not exist.")

    def __setattr__(self, attr, val):
        if hasattr(Config, attr):
            return setattr(Config, attr, val)
        else:
            if hasattr(Config._instance, attr):
                return setattr(Config._instance, attr, val)
            raise NoConfigInitalized("Tried to set attr on instance object that does not exist.")
