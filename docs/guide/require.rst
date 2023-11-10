

Advanced Require Guide
======================


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

NPM packages are stored within a librarywide ``node_modules`` folder. 
If the specified package is not found in ``node_modules``, it will be installed via NPM. 
This installation only occurs once.

You can also install npm packages to javascriptasync's ``node_modules`` folder using the command below.

.. code-block:: bash
   :caption: Installing an NPM package

   python3 -m javascriptasync install <npm package>

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


Requiring NPM packages within local JS files
--------------------------------------------

While javascriptasync's `require` function is able to install new npm packages into it's library store for use through python, NodeJS modules retrieved using a relative path (ie, any local JavaScript files you may have) *are not able to use NPM packages installed through the library's* `require` *function.* 

Say you use `require` to install the lodash function with the intent to use it inside a local JS module.  

.. code-block:: javascript
   :caption: example.js
    
   const lodash = require('lodash');
   function example() {
        const numbers = [1, 5, 3, 7, 2, 8, 4, 6];
        const maxNumber = lodash.max(numbers);
        console.log('The maximum number is:', maxNumber);
   }
   module.exports = { example }


.. code-block:: python
   :caption: example.py

   from javascriptasync import init_js, require
   init_js()
   lodash=require('lodash')
   examplejs = require('./example.js')
   print(examplejs.example())


.. code-block:: 
   :caption: output

   > const lodash = require('lodash');
   Bridge Error: Cannot find module 'lodash'

Unfortunately, attempting to specify the correct path of the imported module isn't possible.
You need to use NPM to install lodash globally or relative to your main python script's current working directory.

For the latter, using:

.. code-block:: bash
   :caption: Installing an NPM package

   npm install <npm package>

For each package in your working directory should be sufficient.

However, `javascriptasync` offers a shortcut command to install NPM packages relative to your script's working directory, using the  ``hybridize add`` and ``hybridize install`` subcommands.


``hybridize add`` will add each file to a text file called 'nodemodules.txt', and ``hybridize install`` will install each package in this text file to your local directory.

.. code-block:: bash
   :caption: 

   python3 -m javascriptasync hybridize add lodash


.. code-block:: bash
   :caption: 

   python3 -m javascriptasync install