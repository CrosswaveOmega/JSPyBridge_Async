import asyncio
import os
from .logging import log_print,logs, print_path

import threading, inspect, time, atexit, sys
class Null:
    def __getattr__(self, *args, **kwargs):
        raise Exception(
            "The JavaScript process has crashed. Please restart the runtime to access JS APIs."
        )


class JSConfig(object):
    event_loop = None
    event_thread = None
    executor = None
    # # The "root" interface to JavaScript with FFID 0
    global_jsi = None
    # # Currently this breaks GC
    fast_mode:bool = False
    # # Whether we need patches for legacy node versions
    node_emitter_patches:bool = False
    async_mode:bool=False
    def __init__(self):
        self.async_mode=False
        from . import proxy
        #if self.event_loop:     return  # Do not start event loop again
        self.event_loop:None #events.EventLoop = events.EventLoop()
        self.event_thread:None #threading.Thread = threading.Thread(target=self.event_loop.loop, args=(), daemon=True)
        #self.event_thread.start()
        self.executor:proxy.Executor = None# proxy.Executor(self.event_loop)
        # # The "root" interface to JavaScript with FFID 0
        self.global_jsi:proxy.Proxy =None# proxy.Proxy(self.executor, 0)
        self.fast_mode:bool=False
        # Whether we need patches for legacy node versions
        self.node_emitter_patches:bool=False

    def startup(self):
        from . import proxy, events
        import threading, inspect, time, atexit, sys
        self.event_loop:events.EventLoop = events.EventLoop(self)
        self.event_thread:threading.Thread = threading.Thread(target=self.event_loop.loop, args=(), daemon=True)
        self.event_thread.start()
        self.executor:proxy.Executor = proxy.Executor(self,self.event_loop)
        # # The "root" interface to JavaScript with FFID 0
        self.global_jsi:proxy.Proxy = proxy.Proxy(self.executor, 0)
        self.fast_mode:bool=False
        # Whether we need patches for legacy node versions
        self.node_emitter_patches:bool=False
        atexit.register(self.event_loop.on_exit)


    def check_node_patches(self):

        if self.global_jsi.needsNodePatches():
            self.node_emitter_patches = True
    def reset_self(self):
        '''set everything to None'''
        self.event_loop = None
        self.event_thread = None
        self.executor = None


        self.global_jsi = Null()
        # Currently this breaks GC
        self.fast_mode = False

    def is_main_loop_active(self):
        if not self.event_thread or self.event_loop:
            return False
        return self.event_thread.is_alive() and self.event_loop.active


    dead = "\n** The Node process has crashed. Please restart the runtime to use JS APIs. **\n"

class classproperty:
    def __init__(self,func):
        self.fget=func
    def __get__(self,instance,owner):
        return self.fget(owner)
class Config:
    '''Singleton Container for JSConfig.'''

    _instance = None
    _initalizing=False
    _asyncmode=False
    def __init__(self, arg, asyncmode=False):
        
        frame=inspect.currentframe()
        last_path=print_path(frame.f_back)
        logs.debug(f'attempted init:[{last_path}]')
        if not Config._instance and not Config._initalizing:
            Config._initalizing=True
            Config._asyncmode=asyncmode
            instance = JSConfig()
            Config._instance = instance
            if not Config._asyncmode:
                log_print(Config._asyncmode)
                Config._instance.startup()
                Config._initalizing=False
        elif Config._initalizing:
            frame=inspect.currentframe()
            lp=print_path(frame)
            logs.warning(lp)
            log_print(f'attempted init during initalization:[{lp}]')
    def kill(self):
        if not Config._instance:
            raise Exception("Never initalized JSConfig, please call javascriptasync.init_js() somewhere in your code first!")
        elif Config._initalizing:
            raise Exception("Still initalizing JSConfig, please wait!")
        Config._instance.event_loop.on_exit()
        Config._instance=None
    @classmethod
    def inst(cls):
        return Config._instance
    @classmethod
    def get_inst(cls):
        '''
        Check if Config._instance was initalized and ready.
        '''
        if not Config._instance:
            raise Exception("Never initalized JSConfig, please call javascriptasync.init_js() somewhere in your code first!")
        elif Config._initalizing:
            raise Exception("Still initalizing JSConfig, please wait!")
        return Config._instance

    def ms(self):
        return Config._instance

    def __getattr__(self, attr):
        if hasattr(Config,attr):
            return getattr(Config,attr)
        else:
            if hasattr(Config._instance,attr):
                return getattr(Config._instance,attr)
            raise Exception('Tried to get attr on instance object that does not exist.')
    def __setattr__(self, attr,val):
        if hasattr(Config,attr):
            return setattr(Config,attr,val)
        else:
            if hasattr(Config._instance,attr):
                return setattr(Config._instance,attr,val)
            raise Exception('Tried to set attr on instance object that does not exist.')


myst:JSConfig=None
