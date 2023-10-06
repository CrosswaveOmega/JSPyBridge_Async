

Getting Started
===============

This guide covers the essential steps to get started with the ``javascriptasync`` library, from installation to initiating communication between Python and Node.js.

.. contents:: Go To:
    :local:


1: Installation
---------------

You can install the ``javascriptasync`` library via the Python package manager, pip. 
Open your terminal and run one of the following commands:

For Python 3:

.. code-block:: bash

   python3 -m pip install -U javascriptasync

For Python 2 or Python 3:

.. code-block:: bash

   pip install -U javascriptasync

If you prefer using a specific Python version (e.g., Python 3), you can use the following command:

.. code-block:: bash

   py -3 -m pip install -U javascriptasync


2: Install Node.js
------------------

As ``javascriptasync`` serves as a bridge between Python and Node.js, 
you must have Node.js installed on your system. 
The installation process varies depending on your operating system:

**Windows and MacOS:**

Visit the official Node.js website at 
[https://nodejs.org/en/download](https://nodejs.org/en/download) 
and download the installer for your platform. Follow the installation instructions provided.

**Linux:**

The recommended way to install Node.js on Linux 
is by using Node Version Manager (nvm). 
You can follow the instructions on the 
nvm repository at [https://github.com/nvm-sh/nvm](https://github.com/nvm-sh/nvm).


3: Initializing the Bridge
--------------------------

Unlike the original ``javascript`` library, ``javascriptasync`` 
does not automatically set up the bridge upon import. 
You must explicitly initialize the bridge using the `init_js` function.

.. code-block:: python

   from javascriptasync import init_js
   init_js()




4: Using `require` for Communication
--------------------------------------


After initializing the bridge, you can use the `require` function to create connections 
to Node.js packages or modules. The `require` function returns a `Proxy` object.

A `Proxy` object in ``javascriptasync`` is akin to a Python class,
but with a unique behavior. When you access its properties or methods,
it transparently communicates with Node.js across the bridge to fetch 
the equivalent Node.js values and functionality.


.. code:: python

    from javascriptasync import init_js, require
    init_js()
    
    # Import an NPM package (chalk in this case)
    chalk= require("chalk")
    # Use the returned `Proxy` object as if it were a Python object
    red=chalk.red("world!")
    print("Hello", red)

- The require function can import NPM packages or your custom Node.js module files via relative imports.
- The returned Proxy object can be manipulated like any other Python object, and when you interact with its properties or methods, it seamlessly communicates with Node.js to retrieve the corresponding values or functionality.

