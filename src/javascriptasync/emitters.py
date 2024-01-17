from __future__ import annotations
from typing import TYPE_CHECKING

# This file contains all the exposed modules
import asyncio
from typing import Any, Coroutine, Optional, Callable, Union
from .configjs import Config
from .core.jslogging import log_print, logs
from .proxy import EventEmitterProxy


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
    return emitter.off_s(event, handler)


def once(emitter: EventEmitterProxy, event: str) -> Any:
    """

    Not to be confused with the similarly named `EventEmitterProxy.once` method.

    Wrapper for the `events.once` function in Node.JS:

    In NodeJS, events.once creates a `Promise` that is fulfilled when the `EventEmitter`
    emits the given event or that is rejected if the `EventEmitter` emits `'error'` while waiting.
    The `Promise` will resolve with an array of all the arguments emitted to the
    given event.

    In Python, this will block the main thread until this promise is recieved.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.


    Example:
        .. code-block:: python
            wait() {
                setTimeout(() => {
                this.emit('done');
                }, 400);
            }
            @Once(myEmitter, 'increment', asyncloop)
            async def handleIncrementOnce(this, counter):
                pass
            val= once(myEmitter, "done")
    """
    conf = Config.get_inst()
    val = emitter._exe.config.global_jsi.once(emitter, event, timeout=1000)
    return val


async def off_a(emitter: EventEmitterProxy, event: str, handler: Union[Callable, Coroutine]):
    """
    Asynchronously unregisters an event handler from an EventEmitterProxy.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to unregister the handler from.
        handler (Callable or Coroutine): The event handler function to unregister.

    """
    await emitter.off_a(event, handler)


async def once_a(emitter: EventEmitterProxy, event: str) -> Any:
    """

    Not to be confused with the similarly named `EventEmitterProxy.once` method.

    Asyncronous wrapper for the `events.once` function in Node.JS:

    In NodeJS, events.once creates a `Promise` that is fulfilled when the `EventEmitter`
    emits the given event or that is rejected if the `EventEmitter` emits `'error'` while waiting.
    The `Promise` will resolve with an array of all the arguments emitted to the
    given event.

    In Python, this will just wait until the promise is recieved.

    Args:
        emitter (EventEmitterProxy): The EventEmitterProxy instance.
        event (str): The name of the event to listen for.

    Returns:
        Any: The value emitted when the event occurs.


    Example:
        .. code-block:: python

            #defined on nodejs side:
            #wait() {setTimeout(() => {this.emit('done');}, 400);}
            val= once(myEmitter, "done")
    """
    conf = Config.get_inst()
    val = await emitter._exe.config.global_jsi.once(emitter, event, timeout=1000, coroutine=True)
    return val
