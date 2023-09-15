# This file contains all the exposed modules
import asyncio
from typing import Coroutine
from . import config
from .config import Config
from .logging import log_print,logs
import threading, inspect, time, atexit, os, sys


def init_js():
    log_print('Starting up js config.')
    Config('')

def kill_js():
    Config('').kill()
    print('killed js')


def require(name, version=None):
    #print('require')
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

async def require_a(name, version=None):
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
    log_print('here')
    coro=conf.global_jsi.require(name, version, calling_dir, timeout=900,coroutine=True)
    #req=conf.global_jsi.require
    return await coro


def get_console():
    '''
    This function returns the console object from the JavaScript context which can be used to print 
    direct messages in your Node.js console from the Python context. It does so by grabbing the console 
    object from the global JavaScript Interface (JSI) stored in the Config singleton instance.

    '''
    return Config.get_inst().global_jsi.console  # TODO: Remove this in 1.0
def get_globalThis():
    '''
     This function returns the globalThis object from the JavaScript context. The globalThis object is 
    a standard built-in object in JavaScript, similar to window in a browser or global in Node.js. 
    It's used as a universal way to access the global scope in any environment. This function provides 
    a way to access this object from the Python context.

    '''
    globalThis = Config.get_inst().global_jsi.globalThis
    return globalThis
def get_RegExp():
    '''
    This function returns the RegExp (Regular Expression) object from the JavaScript context. Regular 
    Expressions in JavaScript are used to perform pattern-matching and "search-and-replace" functions 
    on text. This function returns this RegExp object to the Python environment.
    '''
    return Config.get_inst().global_jsi.RegExp


def eval_js(js,  timeout=10):
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

async def eval_js_a(js,  timeout=10, as_thread=False)->Coroutine:
    frame = inspect.currentframe()
    
    conf=Config.get_inst()
    rv = None
    try:
        local_vars = {}
        locals=frame.f_back.f_locals
        
        for local in frame.f_back.f_locals:
            #print('localv',local,frame.f_back.f_locals[local])
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
    def decor(fn):
        conf=Config.get_inst() 
        fn.is_async_task = True
        t = conf.event_loop.newTaskThread(fn)
        if start:
            t.start()

    return decor
def AsyncTaskA():
    def decor(fn):
        conf=Config.get_inst() 
        fn.is_async_task = True


        return fn
        # t = conf.event_loop.newTask(fn)
        # if start:
        #     t.start()

    return decor

class AsyncTaskUtils:
    @staticmethod
    async def start(method):
        conf=Config.get_inst()
        await conf.event_loop.startTask(method)
    @staticmethod
    async def stop(method):
        conf=Config.get_inst()
        await conf.event_loop.stopTask(method)
    @staticmethod
    async def abort(method,killAfter:float=0.5):
        conf=Config.get_inst()
        await conf.event_loop.abortTask(method,killAfter)

class ThreadUtils:
    @staticmethod
    def start(method):
        conf=Config.get_inst()
        conf.event_loop.startThread(method)
    @staticmethod
    def stop(method):
        conf=Config.get_inst()
        conf.event_loop.stopThread(method)
    @staticmethod
    def abort(method,killAfter:float=0.5):
        conf=Config.get_inst()
        conf.event_loop.abortThread(method,killAfter)

# You must use this Once decorator for an EventEmitter in Node.js, otherwise
# you will not be able to off an emitter.
def On(emitter, event):
    # log_print("On", emitter, event,onEvent)
    def decor(_fn):
        
        conf=Config.get_inst()
        # Once Colab updates to Node 16, we can remove this.
        # Here we need to manually add in the `this` argument for consistency in Node versions.
        # In JS we could normally just bind `this` but there is no bind in Python.
        if conf.node_emitter_patches:

            def handler(*args, **kwargs):
                _fn(emitter, *args, **kwargs)

            fn = handler
        else:
            fn = _fn
        
        emitter.on(event, fn)
        s=str(repr(emitter)).replace("\n",'')
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
        return fn

    return decor


# The extra logic for this once function is basically just to prevent the program
# from exiting until the event is triggered at least once.
def Once(emitter, event):
    def decor(fn):
        i = hash(fn)

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


def off(emitter, event, handler):
    emitter.off(event, handler)
    
    conf=Config.get_inst()
    del conf.event_loop.callbacks[getattr(handler, "ffid")]


def once(emitter, event):
    
    conf=Config.get_inst()
    val = conf.global_jsi.once(emitter, event, timeout=1000)
    return val
