# from . 
import util
import inspect, importlib
import os, sys, json, types
import socket
from proxy import Executor, Proxy

def python(method):
    return importlib.import_module(method, package=None)

def fileImport(moduleName, absolutePath):
    spec = importlib.util.spec_from_file_location(moduleName, absolutePath)
    foo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foo)
    return foo

class DemoClass:
    """Some doc"""
    def __init__(self, var):
        self.var = var

    def get(self, update):
        return self.var + update

    def nested(self):
        def some():
            return 3
        return some

    def arr(self):
        return [1,2,4]

    def barr(self):
        return bytearray()

    def dic(self):
        return {
            'x': {
                'y': 4,
                'z': [5,6,7,8,None]
            }
        }

def add(demoClas1, demoClas2):
    # print("dc", demoClas1, demoClas2)
    return demoClas1.var + demoClas2.var

class Bridge:
    m = {
        0: {
            'python': python,
            'demo': DemoClass,
            'add': add,
            'open': open,
            'fileImport': fileImport
        }
    }
    cur_ffid = 0

    def __init__(self, ipc):
        self.ipc = ipc
        self.q = lambda r, key, val, sig='': self.ipc.queue({ 'r': r, 'key': key, 'val': val, 'sig': sig })
        self.executor = Executor(self)

    def assign_ffid(self, what):
        self.cur_ffid += 1
        self.m[self.cur_ffid] = what
        return self.cur_ffid

    def length(self, r, ffid, key, args):
        l = len(self.m[ffid])
        self.q(r, 'num', l)
        
    def init(self, r, ffid, key, args):
        v = self.m[ffid](*args)
        ffid = self.assign_ffid(v)
        self.q(r, 'inst', ffid)

    def call(self, r, ffid, keys, args, invoke=True):
        v = self.m[ffid]
        # print("r=>", v, ffid, keys, args)
        for key in keys:
            # print("V", type(v), key)
            t = getattr(v, str(key), None)
            # print('v',v)
            if t is None:
                v = v[key] # 🚨 If you get an error here, you called an undefined property
            else:
                v = t
        # Classes when called will return void, but we need to return
        # object to JS.
        was_class = False
        if invoke:
            if inspect.isclass(v):
                was_class = True
            v = v(*args)
        typ = type(v)
        # print("typ", v, typ, inspect.isclass(v), inspect.ismodule(v))
        if typ is str:
            self.q(r, 'string', v)
            return
        if typ is int or typ is float or (v is None):
            self.q(r, 'int', v)
            return
        if inspect.isclass(v) or isinstance(v, type):
            # We need to increment FFID 
            self.q(r, 'class', self.assign_ffid(v), util.make_signature(v))
            return
        if callable(v): # anything with __call__
            self.q(r, 'fn', self.assign_ffid(v), util.make_signature(v))
            return
        if (typ is dict) or (inspect.ismodule(v)) or was_class: # "object" in JS speak
            self.q(r, 'obj', self.assign_ffid(v), util.make_signature(v))
            return
        if typ is list:
            self.q(r, 'list', self.assign_ffid(v), util.make_signature(v))
            return
        if repr(typ).startswith('<class'):  # numpy generator for some reason can't be picked up...
            self.q(r, 'class', self.assign_ffid(v), util.make_signature(v))
            return
        # print("VOID", v, '\n', type(v), isinstance(v, (type)), inspect.isgenerator(v), inspect.isgeneratorfunction(v), inspect.isclass(v),inspect.ismethod(v), inspect.isfunction(v))
        self.q(r, 'void', self.cur_ffid)

    # Same as call just without invoking anything, and args
    # would be null
    def get(self, r, ffid, keys, args):
        o = self.call(r, ffid, keys, [], invoke=False)
        # print("Got", self, r, ffid, keys, args, o)
        return o

    def inspect(self, r, ffid, keys, args):
        v = self.m[ffid]
        for key in keys:
            # print("ke, v", key, v)
            v = getattr(v, key, None) or v[key]
        s = util.make_signature(v)
        self.q(r, '', s)
    def free(self, r, ffid, key, args):
        # print("Free", ffid, key, args)
        del self.m[ffid]
        self.q(r, '', True)

    # def make_fn(self, name, jfid):
    #     def handler(this, *args, **kwargs):
    #         print("Got called with", args, kwargs)
    #         print('alphabet', this.alphabet)
    #         hargs = []
    #         self.cur_ffid += 1
    #         argsid = self.cur_ffid
    #         self.m[self.cur_ffid] = args
    #         self.cur_ffid += 1
    #         kwargsid = self.cur_ffid
    #         self.m[self.cur_ffid] = kwargs
    #         self.ipc.send({ 'c': 'jsi', 'action': 'call', 'ffid': jfid, 'args': [argsid, kwargsid] })

    #     return handler

    # def makeclass(self, r, ffid, keys, args):
    #     className = args['name']
    #     extends = args['extends']
    #     superclasses = []
    #     for extend in extends:
    #         superclass.append(self.m[extend['ffid']])

    #     methods = {}
    #     for method in args['methods']:
    #         print("method",method)
    #         methods[method['name']] = self.make_fn(method['name'], method['jfid'])
        
    #     return type(args['name'], tuple(superclasses), methods)

    def make(self, r, ffid, key, args):
        self.cur_ffid += 1
        self.m[self.cur_ffid] = Proxy(self.executor, self.cur_ffid)
        self.ipc.queue({ 'r': r, 'val': self.cur_ffid })

    def queue_request(self, request_id, payload, timeout=None):
        payload['c'] = 'jsi'
        self.ipc.queue(payload)

    def read(self):
        data = apiin.readline()
        if not data:
            exit()
        j = json.loads(data)
        return j

    def onMessage(self, r, action, ffid, key, args):
        nargs = []
        if args:
            for arg in args:
                # print("-ARG", arg)
                if isinstance(arg, dict) and ('ffid' in arg):
                    nargs.append(self.m[arg['ffid']])
                else:
                    nargs.append(arg)
                # print("\nj", args)
        # print("Calling....", action)
        return getattr(self, action)(r, ffid, key, nargs)

class Ipc:
    def queue(self, what):
        # print("Sending", what)
        # sys.stderr.write(json.dumps(what) + '\n')
        apiout.write(json.dumps(what) + '\n')
        apiout.flush()

ipc = Ipc()
bridge = Bridge(ipc)
apiin = apiout = None
# print("FD", os.environ['NODE_CHANNEL_FD'])

# The communication stuffs

# This is the communication thread which allows us to send and
# recieve different messages at the same time.
def com_io():
    global apiin, apiout
    fd = int(os.environ['NODE_CHANNEL_FD'])
    if sys.platform == 'win32':
        apiin = os.fdopen(fd, 'r')
        apiout = os.fdopen(fd+1, 'w')
    else:
        api = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
        apiin = api.makefile('r')
        apiout = api.makefile('w')
    while True:
        data = apiin.readline()
        if not data:
            break
        j = json.loads(data)
        bridge.onMessage(j['r'], j['action'], j['ffid'], j['key'], j['val'])

com_io()

# com_thread = threading.Thread(target=com_io, args=(), daemon=False)
# com_thread.start()