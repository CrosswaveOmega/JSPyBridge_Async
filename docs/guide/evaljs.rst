
Transferring data between Python and NodeJS
===========================================

Most of these documents focus on operating on NodeJS objects from the Python side of the bridge.

However, you can also preform operations on Python objects **from the NodeJS side** of 
the bridge as well!

.. code-block:: javascript
    :caption: overbridge.js

    async function overevent(myObject,countUntil,otherObj) {
        myObject['world'] = 'hello';
        console.log(myObject)
        for (let x = 0; x < countUntil; x++) {
            //You must await on every module call.
            await otherObj.append(x)
            await otherObj.myArray.append('A')
        }
        return 'it worked';
    }

    module.exports = {overevent};


.. code-block:: python
    :caption: callfromjs.py

    import javascriptasync
    javascriptasync.init_js()

    class MyOtherObject():
        def __init__(self) -> None:
            self.myArray=[]
        def append(self,i):
            self.myArray.append(i)

        countUntil = 9
        myObject = { 'hello': '','mylist':[1,4]}
        otherobj=MyOtherObject()
        overevt=javascriptasync.require('./over.js')
        result=overevt.overevent(myObject,countUntil, otherobj)
        print(countUntil,myArray,myObject,otherobj.myArray)

..code-block:: 
    :caption: output

    NodeJS: { hello: '', mylist: [ 1, 4 ], world: 'hello' }
    Python: 9 {'hello': '', 'mylist': [1, 4]} [0, 'A', 1, 'A', 2, 'A', 3, 'A', 4, 'A', 5, 'A', 6, 'A', 7, 'A', 8, 'A']

**Only non-primitive objects will be assigned a Foreign Object Reference ID.**
You have to await all calls made to a pythonside object from NodeJS.  



Expression evaluation
---------------------

You also use the `eval_js` function to evaluate JavaScript code
within the current Python context. 

`eval_js` preserves references in the python scope, passing them all
to NodeJS as references.


**Unique to this fork, you can set a timeout value on the python side.**


.. code-block:: python

    import javascriptasync
    javascriptasync.init_js()
    countUntil = 9
    myArray = [1]
    myObject = { 'hello': '' }

    output = javascript.eval_js('''
        myObject['world'] = 'hello'    
        for (let x = 0; x < countUntil; x++) {
            await myArray.append(2)
        }
        return 'it worked'
    ''', timeout=20)

    # If we look at myArray and myObject, we should see it updated
    print(output, myArray, myObject)

There's also an asyncrounous variant in `eval_js_a`.

.. code-block:: python

    import javascriptasync
    import asyncio
    async def main()
        javascriptasync.init_async()
        countUntil = 9
        myArray = [1]
        myObject = { 'hello': '' }

        # Make sure you await everywhere you expect a JS call !
        output = await javascript.eval_js_a('''
            myObject['world'] = 'hello'    
            for (let x = 0; x < countUntil; x++) {
                await myArray.append(2)
            }
            return 'it worked'
        ''', timeout=20)

        # If we look at myArray and myObject, we should see it updated
        print(output, myArray, myObject)
    asyncio.run(main())

