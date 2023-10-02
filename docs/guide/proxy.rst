

Require, and Proxy operations
=============================


Require API
^^^^^^^^^^^
.. automodule:: javascriptasync
   :members: require, require_a
   :undoc-members:
   :show-inheritance:
   :no-index:


Proxy
^^^^^

`require` returns what this library refers to as a **Proxy** object.  

The **Proxy** is a mutatable object which stores a reference to some non-primitive object within the utilized JS context, 
mapped to a unique **Foreign Object Reference ID** (FFID).  

When you interact with Proxy objects as you would a regular object (getting attribues/setting attributes/calling functions), 
the library will reflect said operation through the active node.js connection.  


Calls are synchronous by default, but there is a special asyncio mode available, see below.


require NPM packages
^^^^^^^^^^^^^^^^^^^^

NPM package names **Do not start with '/' or include a period '.' in them!**

NPM packages are stored within an internal ``node_modules`` folder.  
If there is no package with that passed in name found in ``node_modules``, 
then the package will be installed via NPM.  This only happens one time.


``python3 -m javascriptasync --install <npm package>``


require Local Files 
^^^^^^^^^^^^^^^^^^^

You can also require modules from local files.  
Assume that you have the below file in the same directory as your python script.

.. code-block:: javascript
    :caption: example.js
    
    function greet() {
        return "Hello world, greetings from node.js!";
    }
    
    module.exports = { greet }


Then in your running python script, set the name arg of ``require()`` to ``./example.js``.

.. code-block:: python
    :caption: example.py

    from javascriptasync import init_js, require
    init_js()
    examplejs = require('./example.js')
    print(examplejs.greet())

utilizing asyncio  
--------------------

Every call to the Node.JS Process is blocking by default.  While this isn't really a problem for small, synchronous scripts,
it is a problem for asyncio applications, where these operations could block your entire asyncio event_loop.

``require_a()`` is a coroutine version of ``require()``

Any Proxy function call can be transformed into an asyncio call via including the ``coroutine=True`` argument.

.. code-block:: python
    :caption: simple asyncio example.

    import asyncio
    from javascriptasync import init_js, require_a
    init_js()
    async def main():
        chalk= await require_a("chalk")
        red=await chalk.red("world!",coroutine=True)
        print("Hello", red)

    asyncio.run(main())

Proxy Asyncio Stacking
^^^^^^^^^^^^^^^^^^^^^^

`Proxy` also has async variants of it's get/set/call methods, 
on top of a special "async operation stacking" system.

But to understand how to use it, 
you should get an idea about how Proxy objects make calls from the 
Python side of the bridge to the NodeJS side of the bridge.

Take the code block below as an example.

.. code-block:: python

    red=chalk.red("world!")
    #Equivalent to
    redprop=chalk.get_s('red')
    red=call_s("world!")

It makes two thread synchronous (blocking) calls to NodeJS.  
One to get a reference for the 'red' property (really a method),
and another to call the newly referenced 'red' method the "world" argument.

.. code-block:: python

    red=await chalk.red("world!", coroutine=True)
    #Equivalent to
    redprop=chalk.get_s('red')
    await redprop.call_a("world!")

Passing in the ``coroutine=True`` keyword argument simply tells `Proxy.call_s`
to return the coroutine variant specified
by `Proxy.call_a`, which is executed via the `await` keyword.

Getting a reference for the 'red' property still requires a synchronous call to node.js.  

It gets messy 

.. code-block:: python
    :caption: Async Stacking Example

    chalk.toggle_async_stack(True)
    red=await chalk.red("world!")
    #Equivalent to
    red=await chalk.get_a('red').call_a("world!")


In order to transform that synchronous 'get' call into an asyncronous function call,
you have to enable the Proxy's *Async Call Stacking* (sometimes called *Async Chaining*) mode
through the `Proxy.toggle_async_stack(mode)` method.  

With Async call stacking enabled, no calls to Node.JS are made until the await keyword is used, 
when each asyncrounous operation is preformed one after the other until the 
end of the stack is reached.


.. code-block:: python
    :caption: simple asyncio chaining example.

    import asyncio
    from javascriptasync import init_js, require_a
    init_js()
    async def main():
        chalk= await require_a("chalk")
        chalk.toggle_async_stack(True)
        red=await chalk.red("world!")
        print("Hello", red)

    asyncio.run(main())


NodeJS Event Emitters: :next:
