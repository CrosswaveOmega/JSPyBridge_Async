.. AsyncJavascriptBridge documentation master file, created by
   sphinx-quickstart on Sun Sep 17 12:53:41 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to AsyncJavascriptBridge's documentation!
=================================================

AsyncJavascriptBridge is a Python library that allows you to seamlessly run JavaScript code from within your Python applications with built in asyncio support, forked from the JSPyBridge library [here](https://github.com/extremeheat/JSPyBridge)

## Key Features

- Streamlined asyncio support: AsyncJavascriptBridge offers enhanced compatibility with asyncio applications, so each call/init to node.js won't block your asyncio event loop.
- Switch between Sync/Async JS calls with a single keyword: Only calls you want to be asyncronous will be asyncronous.
- Greater Control: set timeouts of each call with a single keyword!
- Improved code organization: With AsyncJavascriptBridge, the codebase has been refactored to ensure better structure, maintainability, and understandability.

## Getting Started

To get started with the library, just use 
```
pip install -U javascriptasync
```


.. toctree::
   :maxdepth: 2
   :caption: Contents:
   javascriptasync
   modules


Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
