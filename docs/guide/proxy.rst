

Require, and Proxy operations
=============================


Require API
^^^^^^^^^^^
.. automodule:: javascriptasync
   :members: require
   :undoc-members:
   :show-inheritance:
   :no-index:

Require NPM Packages
^^^^^^^^^^^^^^^^^^^^

NPM package names **must not start with '/' or include a period '.' in them!**

NPM packages are stored within an internal ``node_modules`` folder. If the specified package is not found in ``node_modules``, it will be installed via NPM. This installation only occurs once.

To explicitly install an NPM package, you can use the following command:

.. code-block:: bash
   :caption: Installing an NPM package

   python3 -m javascriptasync --install <npm package>

Require Local Files
^^^^^^^^^^^^^^^^^^^

You can also require modules from local files. Suppose you have the following file in the same directory as your Python script:

.. code-block:: javascript
   :caption: example.js

   function greet() {
       return "Hello world, greetings from Node.js!";
   }
   
   module.exports = { greet }

Then, in your running Python script, use the `require()` function with the name argument set to ``./example.js``:

.. code-block:: python
   :caption: example.py

   from javascriptasync import init_js, require
   init_js()
   examplejs = require('./example.js')
   print(examplejs.greet())

Proxy
-----

When you use the `require` function, it returns what this library refers to as a **Proxy** object.

The **Proxy** is a mutable object that stores a reference to a non-primitive object within the utilized JavaScript context, mapped to a unique **Foreign Object Reference ID** (FFID).

When you interact with Proxy objects by getting attributes, setting attributes, or calling functions, the Proxy object will make a call across the bridge through the built-in `object.__getattr__`, `object.__setattr__`, `object.__call__` magic methods, which is then processed by Node.JS and used by Python.

These magic methods are synchronous, but there is a special asyncio mode available, as described below.



Using Asyncio Mode
------------------


By default, every call to the Node.js Process in the library is **synchronous**. While this may not pose a significant issue for small scripts that generally only make one call across the bridge a time, it can become problematic in the context of python scripts which must run several tasks in an **asynchronous** manner.

Asynchronous programming in python is best handled by the `asyncio` library. `Asyncio <https://docs.python.org/3/library/asyncio.html>`_ is a Python library used to write and execute concurrent code using the await/async syntax.  It is well-suited for I/O-bound operations, network communication, and other asynchronous tasks.  

However, large cpu bound operations within an asyncronous task will **block** other asynchronous tasks from running.  Since the aformentioned "magic methods" are synchronous by default, *every single bridge call made by a Proxy object will block the entire event loop until it finishes*, undermining the benefits of asyncio.

To address this challenge, the library and it's classes offers async variants of it's functions and methods, usually denoted by an ``_a`` suffix.    Using asyncio in this context provides some substantial advantages:

1. **Non-blocking Execution:** With asyncio, you can execute multiple tasks concurrently without blocking the event loop. This is especially beneficial in scenarios where your Python application needs to interact with Node.js while continuing to perform other tasks simultaneously.

2. **Improved Responsiveness:** Asynchronous execution allows your application to remain responsive, even when performing I/O operations or waiting for responses from Node.js. This ensures a more interactive and efficient user experience.

3. **Optimal Resource Utilization:** asyncio efficiently manages system resources, minimizing wasted CPU cycles during idle times. It can scale to handle a large number of concurrent operations without consuming excessive system resources.

4. **Parallelism:** asyncio can execute multiple asynchronous tasks concurrently, harnessing the full potential of multi-core processors. This parallelism can significantly boost the performance of applications with high concurrency requirements.

For instance, `require` has an async variant in `require_a`, and `init_js` has an  async variant in `init_js_a`.  Both should be used within an async context.


.. automodule:: javascriptasync
   :members: require_a
   :undoc-members:
   :show-inheritance:
   :no-index:

.. automodule:: javascriptasync
   :members: init_js_a
   :undoc-members:
   :show-inheritance:
   :no-index:

(There's an additional benefit to using init_js_a, but that's for another guide.)

Moreover, Any Proxy function call can be transformed into an asyncio call via including the ``coroutine=True`` argument.

.. code-block:: python
    :caption: simple asyncio example.

    import asyncio
    from javascriptasync import init_js, require_a
    #Initalize the bridge.
    init_js()
    async def main():
        #Initalize the bridge inside the 
        
        # Require the 'chalk' module asynchronously
        chalk= await require_a("chalk")
        
        # Perform non-blocking 'red' operation
        red=await chalk.red("world!",coroutine=True)
        print("Hello", red)

    asyncio.run(main())



Async Call Stacking with Proxy
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In the library, the `Proxy` object not only provides asynchronous variants of its get/set/call methods, it has a togglable "Async Call Stacking" mode to transform a stack of magic method invocations into a single awaitable coroutine.

To fully grasp how this works, it's essential to understand how Proxy objects handle calls from the Python side of the bridge to the Node.js side of the bridge.

.. code-block:: python

    red = chalk.red("world!")
    #Equivalent to
    redprop = chalk.get_s('red')
    red = call_s("world!")

In this code, two synchronous (blocking) calls are made to Node.js. The first call retrieves a reference for the 'red' property (which is, in fact, a Proxy for the red method), and the second call invokes the newly referenced 'red' method with the argument "world."


You can make the call to the 'red' method asynchronous using the ``coroutine=True`` keyword.

.. code-block:: python

    red=await chalk.red("world!", coroutine=True)
    #Equivalent to
    redprop=chalk.get_s('red')
    await redprop.call_a("world!")

Here, we use the `await` keyword to ensure that calling the 'red' method does not block the event loop, allowing other asynchronous tasks to proceed. However, obtaining a reference for the 'red' property still necessitates a synchronous call to Node.js.

This is where the "Async Call Stacking" mode comes into play. To transform synchronous 'get' calls into their asynchronous variant when using the 'magic methods', you must first enable this mode on the individual Proxy objects using the `Proxy.toggle_async_stack(mode)` method.

.. code-block:: python
    :caption: Async Stacking Example

    chalk.toggle_async_stack(True)
    red=await chalk.red("world!")
    #Equivalent to
    red=await chalk.get_a('red').call_a("world!")

With Async Call Stacking enabled, no calls to Node.js are made until you use the `await` keyword. When the `await` keyword is used, each asynchronous operation is executed one after the other until the end of the stack is reached.

It is possible to enable Async Call Stacking in advance through `require_a`, if you set the ``amode`` argument to True.


.. code-block:: python
   :caption: Async Call Stacking example

   import asyncio
   from javascriptasync import init_js, require_a
   init_js()
   async def main():
       # Require the 'chalk' module asynchronously
       #while enabling Async Call Stacking
       chalk = await require_a("chalk",amode=True)
              
       # Perform a non-blocking 'red' operation
       red = await chalk.red("world!")
       print("Hello", red)

   asyncio.run(main())

