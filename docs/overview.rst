Overview
============

This bridge works through standard input/output pipes, there are no native modules and the 
communication can happen through anywhere--either pipes or network sockets.

But before then, the library needs to initalize a JSConfig object though ``init_js()``

JSConfig
========

JSConfig is a big container class which initalizes all the subcomponents needed for this bridge to work.
It creates a new **EventLoop**, initalizes the EventLoop's IO ``event_thread``, creates an **Executor**, and the 
global JavaScript Interface Proxy  ``global_jsi``.

All the code for starting up and stopping the bridge is here.

Proxy
=====

The **Proxy** is a mutatable object which stores a reference to some Non-primitive object on the JS side of the bridge, 
mapped to a unique **Foreign Object Reference IDs** (FFID).

Interacting with Proxy in the same way as a Python object will make a request to the bridge.  
By default, **all of these requests are thread synchronous,** unless you utilize the ``coroutine=True`` kwarg in an init or call operation.

When the proxy object is destoryed on one side of the bridge, its refrence is removed
from the other side of the bridge. 

EventLoop
=========

The EventLoop brokers IO requests between your python context and the node.js Connection.  

Input is queued up here, sent to the ConnectionClass at the start of each loop iteration, and brokers the output
back to the function/task which made the request.  


Executor
========

The middleman between Python and the Bridge.  The Executor formats a dictionary containing the details for 
each operation the node process will preform. 


For every property access, there is a communication protocol that allows one side to access the
access properties on the other side, and also complete function calls. 

Non-primitive values are sent as **Foreign Object Reference IDs** (FFID). These FFIDs
exist in a map on both sides of the bridge, and map numeric IDs with a object reference. 



On the opposite side to the one which holds a reference, this FFID is assigned to a Proxy object.
In JS, a ES6 proxy is used, and in Python, the proxy is a normal class with custom `__getattr__` 
and other magic methods. Each proxy property access is mirrored on the other side of the bridge. 

Proxy objects on both sides of the bridge are GC tracked. In JavaScript, all python Proxy objects
are registered to a FinalizationRegistry. In Python, `__del__` is used to track the Proxy object's
destruction. When the proxy object is destoryed on one side of the bridge, its refrence is removed
from the other side of the bridge. This means you don't have to deal with memory management.
