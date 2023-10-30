from __future__ import annotations

# This file contains all the exposed modules
import asyncio
from typing import Any, Coroutine, Optional, Callable, Union
from . import config
from .config import Config
from .logging import log_print, logs
from .proxy import EventEmitterProxy

import threading, inspect, time, atexit, os, sys
from .errors import NoAsyncLoop


# You must use this Once decorator for an EventEmitterProxy in Node.js, otherwise
# you will not be able to off an emitter.
def On(emitter: EventEmitterProxy, event: str) -> Callable:
    """
    Decorator for registering a python function or coroutine as a listener for an EventEmitterProxy.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Callable: The decorated event handler function.

    Raises:
        NoAsyncLoop: If asyncio_loop is not set when using a coroutine handler.

    Example:
        .. code-block:: python

            @On(myEmitter, 'increment', asyncloop)
            async def handleIncrement(this, counter):

                pass
    """

    def decor(_fn):
        return emitter.on(event, _fn)

    return decor


# The extra logic for this once function is basically just to prevent the program
# from exiting until the event is triggered at least once.
def Once(emitter: EventEmitterProxy, event: str) -> Callable:
    """
    Decorator for registering a python function or coroutine as an one-time even listener for an EventEmitterProxy.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Callable: The decorated one-time event handler function.

    Raises:
        NoAsyncLoop: If asyncio_loop is not set when using a coroutine handler.

    Example:
        .. code-block:: python

            @Once(myEmitter, 'increment', asyncloop)
            async def handleIncrementOnce(this, counter):
                pass
    """

    def decor(fna):
        return emitter.once(event, fna)

    return decor


def off(emitter: EventEmitterProxy, event: str, handler: Union[Callable, Coroutine]):
    """
    Unregisters an event handler from an EventEmitterProxy.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy Proxy instance.
        event (str): The name of the event to unregister the handler from.
        handler (Callable or Coroutine): The event handler function to unregister.  Works with Coroutines too.

    """
    return emitter.off(event, handler)


def once(emitter: EventEmitterProxy, event: str) -> Any:
    """
    Listens for an event emitted once and returns a value when it occurs.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.

    """
    conf = Config.get_inst()
    val = conf.global_jsi.once(emitter, event, timeout=1000)
    return val


async def off_a(emitter: EventEmitterProxy, event: str, handler: Union[Callable, Coroutine]):
    """
    Asynchronously unregisters an event handler from an EventEmitterProxy.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to unregister the handler from.
        handler (Callable or Coroutine): The event handler function to unregister.

    """
    await emitter.off_a(event, handler, coroutine=True)


async def once_a(emitter: EventEmitterProxy, event: str) -> Any:
    """
    Asynchronously listens for an event emitted once and returns a value when it occurs.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.

    """
    conf = Config.get_inst()
    val = await conf.global_jsi.once(emitter, event, timeout=1000, coroutine=True)
    return val
