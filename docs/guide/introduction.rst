

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
automatically initalize the bridge after you import the library

You have to import and call the `init_js` function to create a bridge connection to a node.js subprocess.

.. code:: python

    from javascriptasync import init_js
    init_js()


4: require
----------

After starting up the bridge,  use the library's `require` function to initalize 
any NodeJS packages or modules, and the library will return a `Proxy`.  

It's utilized in the same manner as within node.js, 
where you can pass in the name of an NPM package or module.

.. code:: python

    from javascriptasync import init_js, require
    init_js()
    chalk= require("chalk")
    red=chalk.red("world!")
    print("Hello", red)


- `require` can import npm packages **or** your own node.js module files via a relative import.  
- The newly returned `Proxy` object can be used as any other Python Object.  

Require and Proxys: :next:
