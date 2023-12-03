.. AsyncJavascriptBridge documentation master file, created by
   sphinx-quickstart on Sun Sep 17 12:53:41 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to AsyncJavascriptBridge's documentation!
=================================================

``javascriptasync`` is a Python library that allows you to seamlessly run JavaScript code from within your 
Python applications with built in asyncio support, forked from the JSPyBridge library [here](https://github.com/extremeheat/JSPyBridge)

It began as a simple modification to allow JSPyBridge to utilize asyncio coroutines on the Python side,
however this ended up requiring an overhaul of the Python side to provide for a
greater degree of control over how calls are made across the bridge.

Key Features
============

- Seamless asyncio support: JavaScript calls do not block your asyncio event loop.
- Simple switch between Sync and Async JavaScript calls using a single keyword.
- Enhanced timeout control.
- Built-in Event Emitter support.
- Improved code organization: The codebase has been refactored for better structure, maintainability, and understandability.

Getting Started
^^^^^^^^^^^^^^^

To get started with the library, just use 
.. code:: 

   pip install -U javascriptasync


Basic Terms
===========

Initialization
--------------

When you initialize this library, it establishes a "bridge" between your active Python process and a Node.js process. The bridge allows Python to communicate with Node.js seamlessly.

Communication Flow
------------------

The communication flow between Python and Node.js involves the following steps:

1. Python sends a message across the bridge to a receiver object in Node.js when it needs to retrieve data, set data, invoke a function, or something else in Node.js.
2. The Node.js receiver processes the message and performs the requested operation.
3. Once the operation is complete, the receiver sends a response message back to Python via the bridge, indicating that it has finished.

Guide
=====
.. toctree::
   :maxdepth: 2
   :caption: Guide

   guide/introduction
   guide/require
   guide/proxy
   guide/eventemitters
   guide/threadtasks
   guide/evaljs

Table of contents
=================
.. toctree::
   :maxdepth: 1
   :caption: Contents:

   javascriptasync
   overview
   modules


Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
