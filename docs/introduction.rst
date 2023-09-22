

Getting Started
===============

.. contents:: Go To:
    :local:


1: Installation
---------------

You can install this library via the PIP package manager.

.. code:: 

   python3 -m pip install -U javascriptasync


.. code:: 

   pip install -U javascriptasync

   
.. code:: 

   py -3 -m pip install -U javascriptasync

2: Install node.js
------------------

Since this library is a bridge between python and node.js, it follows that you need to install node.js.

Windows and MacOS
^^^^^^^^^^^^^^^^^
Visit https://nodejs.org/en/download and click on the relevant installer.

Linux
^^^^^
The easiest way to install node.js on a linux system is via nvm.

Just follow the instructions at the Node Version Manager (nvm) repository:
    https://github.com/nvm-sh/nvm

3: Start up the bridge 
----------------------

Unlike the original ``javascript`` library, ``javascriptasync`` does not
automatically initalize everything after importing. *You have to import and call the 
``init_js`` function to create a connection to a node.js subprocess.*

.. code:: python

    from javascriptasync import init_js
    init_js()


4: require
----------

After starting up the bridge, just use the library's ``require`` function.  
It's utilized in the same manner as within node.js, 
where you can pass in the name of an NPM package or module.

.. code:: python

    from javascriptasync import init_js, require
    init_js()
    chalk= require("chalk")
    red=chalk.red("world!")
    print("Hello", red)

``require`` can import npm packages **or** your own node.js module files via a relative import.  

Proxy
^^^^^

``require`` returns what this library refers to as a **Proxy** object.  

The **Proxy** is a mutatable object which stores a reference to some non-primitive object within the utilized JS context, 
mapped to a unique **Foreign Object Reference ID** (FFID).  

When you interact with Proxy objects as you would a regular object (getting attribues/setting attributes/calling functions), 
the library will reflect said operation through the active node.js connection 



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

4: utilizing asyncio  
--------------------

Every JavaScript operation is blocking by default.  While this isn't really a problem for small, synchronous scripts,
it is a problem for asyncio applications, where these operations could block your entire asyncio event_loop.

So this library provides asyncio compatible methods to compensate.

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

