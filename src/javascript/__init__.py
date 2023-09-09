# This file contains all the exposed modules
import asyncio
from . import config
from .config import myst
from .logging import log_print,logs
import threading, inspect, time, atexit, os, sys


def init():
    log_print('Starting up js config.')
    config.Config('')




def require(name, version=None):
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

    return config.Config('').global_jsi.require(name, version, calling_dir, timeout=900)

async def require_a(name, version=None):
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
    log_print('here')
    coro=asyncio.to_thread(config.Config('').global_jsi.require(name, version, calling_dir, timeout=900))
    #req=config.Config('').global_jsi.require
    return await coro


# console = config.Config('').global_jsi.console  # TODO: Remove this in 1.0
# globalThis = config.Config('').global_jsi.globalThis
# RegExp = config.Config('').global_jsi.RegExp


def eval_js(js,  timeout=10):
    frame = inspect.currentframe()
    rv = None
    try:
        local_vars = {}
        for local in frame.f_back.f_locals:
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        rv = config.Config('').global_jsi.evaluateWithContext(js, local_vars,  timeout=timeout,forceRefs=True)
    finally:
        del frame
    return rv

async def eval_js_a(js,  timeout=10):
    frame = inspect.currentframe()
    rv = None
    try:
        local_vars = {}
        locals=frame.f_back.f_locals
        
        for local in frame.f_back.f_locals:
            #print('localv',local,frame.f_back.f_locals[local])
            if not local.startswith("__"):
                local_vars[local] = frame.f_back.f_locals[local]
        rv = await asyncio.to_thread(config.global_jsi.evaluateWithContext,js, local_vars, timeout=timeout,forceRefs=True)
    finally:
        del frame
    return rv

def AsyncTask(start=False):
    def decor(fn):
        fn.is_async_task = True
        t = config.Config('').event_loop.newTaskThread(fn)
        if start:
            t.start()

    return decor


# start = config.Config('').event_loop.startThread
# stop = config.Config('').event_loop.stopThread
# abort = config.Config('').event_loop.abortThread

# You must use this Once decorator for an EventEmitter in Node.js, otherwise
# you will not be able to off an emitter.
def On(emitter, event):
    # log_print("On", emitter, event,onEvent)
    def decor(_fn):
        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if config.Config('').node_emitter_patches:

            def handler(*args, **kwargs):
                _fn(emitter, *args, **kwargs)

            fn = handler
        else:
            fn = _fn

        emitter.on(event, fn)
        # We need to do some special things here. Because each Python object
        # on the JS side is unique, EventEmitter is unable to equality check
        # when using .off. So instead we need to avoid the creation of a new
        # PyObject on the JS side. To do that, we need to persist the FFID for
        # this object. Since JS is the autoritative side, this FFID going out
        # of refrence on the JS side will cause it to be destoryed on the Python
        # side. Normally this would be an issue, however it's fine here.
        ffid = getattr(fn, "iffid")
        setattr(fn, "ffid", ffid)
        config.Config('').event_loop.callbacks[ffid] = fn
        return fn

    return decor


# The extra logic for this once function is basically just to prevent the program
# from exiting until the event is triggered at least once.
def Once(emitter, event):
    def decor(fn):
        i = hash(fn)

        def handler(*args, **kwargs):
            if config.Config('').node_emitter_patches:
                fn(emitter, *args, **kwargs)
            else:
                fn(*args, **kwargs)
            del config.Config('').event_loop.callbacks[i]

        emitter.once(event, handler)
        config.Config('').event_loop.callbacks[i] = handler

    return decor


def off(emitter, event, handler):
    emitter.off(event, handler)
    del config.Config('').event_loop.callbacks[getattr(handler, "ffid")]


def once(emitter, event):
    val = config.Config('').global_jsi.once(emitter, event, timeout=1000)
    return val
