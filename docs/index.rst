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

- Streamlined asyncio support: AsyncJavascriptBridge offers enhanced compatibility with asyncio applications, 
   so each call/init to node.js won't block the rest of your asyncio event loop.
- Switch between Sync/Async JS calls with a single keyword.
- Greater Timeout Control.
- Built in Event Emitter support.
- Improved code organization: the codebase has been refactored to ensure better structure, maintainability, and understandability.

Getting Started
^^^^^^^^^^^^^^^

To get started with the library, just use 
.. code:: 

   pip install -U javascriptasync


Basic Terms
===========

Upon initalization, This library creates a "bridge" between your active Python Process and a 
NodeJS Process. 
- When Python needs to get data, set data, or invoke a function  that's within NodeJS, it will send a message across this bridge to a reciever object in NodeJS.
- This reciever object will process this message and preform the operation in NodeJS.
- When the operation is finished, the reciever sends a new message back across the bridge to Python indicating that it finished.


Guide
=====
.. toctree::
   :maxdepth: 2
   :caption: Guide

   guide/introduction
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
