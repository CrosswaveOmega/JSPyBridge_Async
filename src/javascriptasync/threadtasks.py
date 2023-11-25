
from __future__ import annotations

import time, threading, json, sys
from typing import Any, Callable, Dict, List, Tuple

from . import pyi, config
from queue import Queue
from weakref import WeakValueDictionary
from typing import Callable
from .core.abc import (
    ThreadTaskStateBase,
)
from .core.jslogging import(
    log_debug,
    log_print,
)

class ThreadState(ThreadTaskStateBase):
    """
    Represents the state of a wrapped "AsyncThread" function.

    This should be the first parameter to all wrapped "AsyncThread" functions.

    Attributes:
        stopping (bool): When this is set to true, the "AsyncThread" function should stop.
        sleep (function): Alias for the wait function.
    """

    def __init__(self):
        self.stopping: bool = False
        self.sleep: Callable = self.wait

    def wait(self, sec: float):
        """
        Wait for a specified duration, and will automatically exit the process once self.stopping is true.

        Args:
            sec (float): The duration to wait in seconds.
        """

        stop_time = time.time() + sec
        while time.time() < stop_time and not self.stopping:
            time.sleep(0.2)
        if self.stopping:
            # This feels unsafe, but it works for threads.
            # Will remove when I find something I consider safer.
            sys.exit(1)

class ThreadGroup():
    """
    Class which merges state, handler, and thread into one easy package.

    Attributes:
        state (ThreadState): Represents the state of a wrapped "AsyncThread" function.
        handler (Callable): A callable function.
        thread (Thread): Instance of threading.Thread.
    """
    def __init__(self, handler: Callable, *args):
        """
        Initialize the ThreadGroup object.

        Args:
            handler (Callable): A callable function.
            *args: Variable length argument list.
        """
        self.state = ThreadState()
        self.handler = handler
        self.thread = threading.Thread(target=handler, args=(self.state, *args), daemon=True)
        log_debug(
            "EventLoop: adding Task Thread. state=%s. handler=%s, args=%s",
             str(self.state), str(handler), args
        )

    def check_handler(self, handler: Callable) -> bool:
        """
        Check if the provided handler is the same as the instance's handler.

        Args:
            handler (Callable): A callable function to be checked.

        Returns:
            bool: True if the handlers are the same, False otherwise.
        """
        if self.handler == handler:
            return True
        return False

    def start_thread(self):
        """
        Start the thread of the instance.
        """
        self.thread.start()

    def stop_thread(self):
        """
        Stop the thread of the instance by setting the 'stopping' attribute of 'state' to True.
        """
        log_debug("EventLoop: stopping thread with handler %s", str(self.handler))
        self.state.stopping = True

    def abort_thread(self, kill_after: float = 0.5):
        """
        Abort the thread of the instance after a specified time or instantly if the thread is not alive anymore.

        Args:
            kill_after (float, optional): The time after which the thread should be aborted. Defaults to 0.5.
        """
        self.state.stopping = True
        killTime = time.time() + kill_after
        log_debug(
            "EventLoop: aborting thread with handler %s, kill time %f",
            str(self.handler),
            (kill_after))
        while self.thread.is_alive():
            time.sleep(0.2)
            if time.time() < killTime:
                self.thread._stop()

    def terminate_thread(self):
        """
        Terminate the thread of the instance instantly irrespective of whether it's alive or not.
        """
        log_debug("Terminating thread with handler %s", str(self.handler))
        self.thread._stop()

    def is_thread_alive(self):
        return self.thread.is_alive()