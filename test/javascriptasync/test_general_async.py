from javascriptasync import require, require_a, On, Once, off, once, eval_js, eval_js_a, init_js
from javascriptasync.logging import set_log_level
import logging
import pytest
import asyncio



# Define a class for testing
class TestJavaScriptLibrary:
    def __init__(self):
        self.demo=None


class TestJavaScriptLibraryASYNC:
    def __init__(self):
        self.demo=None

    def assertEquals(self, cond, val):
        assert cond == val

    def test_require(self):
        chalk = require("chalk")
        fs = require("fs")
        print("Hello", chalk.red("world!"))
        test = require("./test.js")

    def test_classes(self):
        DemoClass = require("./test.js").DemoClass
        self.demo = DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3))
        # New psuedo operator
        demo2 = DemoClass.new("blue", {"a": 3}, lambda v: self.assertEquals(v, 3))

        assert self.demo.ok()(1, 2, 3) == 6
        assert self.demo.toString() == '123!'
        assert self.demo.ok().x == 'wow'
        assert DemoClass.hello() == 'world'

    def test_iter(self):
        DemoClass = require("./test.js").DemoClass
        demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

        f = None
        for i in demo.array():
            print("i", i)
            f = i
        assert f.a == 3

        expect = ['x', 'y', 'z']
        for key in demo.object():
            assert key == expect.pop(0)

    def some_method(self, text):
        print("Callback called with", text)
        assert text == 'It works !'


    def test_events(self):
        @On(self.demo, "increment")
        def handler(this, fn, num, obj):
            print("Handler caled", fn, num, obj)
            if num == 7:
                off(self.demo, "increment", handler)

        @Once(self.demo, "increment")
        def onceIncrement(this, *args):
            print("Hey, I'm only called once !")

        self.demo.increment()

    def test_arrays(self):
        self.demo.arr[1] = 5
        self.demo.obj[1] = 5
        self.demo.obj[2] = self.some_method
        print("Demo array and object", self.demo.arr, self.demo.obj)

    def test_errors(self):
        try:
            self.demo.error()
            print("Failed to error")
            exit(1)
        except Exception as e:
            print("OK, captured error")

    def test_valueOf(self):
        a = self.demo.arr.valueOf()
        print("A", a)
        assert a[0] == 1
        assert a[1] == 5
        assert a[2] == 3
        print("Array", self.demo.arr.valueOf())

    def test_once(self):
        self.demo.wait()
        once(self.demo, "done")

    def test_assignment(self):
        self.demo.x = 3

    def test_eval(self):
        DemoClass = require("./test.js").DemoClass
        self.demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
        pythonArray = []
        pythonObject = {"var": 3}
        demo = self.demo
        # fmt: off
        print(eval_js('''
            for (let i = 0; i < 10; i++) {
                await pythonArray.append(i);
                pythonObject[i] = i;
            }
            pythonObject.var = 5;
            const fn = await demo.moreComplex()
            console.log('wrapped fn', await fn()); // Should be 3
            return 2
        '''))
        # fmt: on

        print("My var", pythonObject)

    def test_bigint(self):
        bigInt = eval_js('100000n')
        print(bigInt)

    def test_nullFromJsReturnsNone(self):
        assert self.demo.returnNull() is None
    def assertEquals(self, cond, val):
        assert cond == val

    async def atest_require(self):
        chalk = await require_a("chalk")
        fs = await require_a("fs")

        print("Hello", chalk.red("world!"))
        test = await require_a("./test.js")

    async def atest_classes(self):
        DemoClass = (await require_a("./test.js")).DemoClass
        self.demo = await DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3), coroutine=True)
        # New psuedo operator
        demo2 = await DemoClass.new("blue", {"a": 3}, lambda v: self.assertEquals(v, 3), coroutine=True)
        
        assert await self.demo.ok()(1, 2, 3,coroutine=True) == 6
        assert self.demo.toString() == '123!'
        assert self.demo.ok().x == 'wow'
        assert DemoClass.hello() == 'world'

    async def atest_iter(self):
        DemoClass = require("./test.js").DemoClass
        demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

        f = None
        for i in demo.array():
            print("i", i)
            f = i
        assert f.a == 3

        expect = ['x', 'y', 'z']
        for key in demo.object():
            assert key == expect.pop(0)

    async def atest_callback(self):
        await self.demo.callback(self.some_method,coroutine=True)

    async def atest_events(self):
        @On(self.demo, "increment")
        def handler(this, fn, num, obj):
            print("Handler caled", fn, num, obj)
            if num == 7:
                off(self.demo, "increment", handler)

        @Once(self.demo, "increment")
        def onceIncrement(this, *args):
            print("Hey, I'm only called once !")

        self.demo.increment()

    async def atest_arrays(self):
        self.demo.arr[1] = 5
        self.demo.obj[1] = 5
        self.demo.obj[2] = self.some_method
        print("Demo array and object", self.demo.arr, self.demo.obj)

    async def atest_errors(self):
        try:
            self.demo.error()
            print("Failed to error")
            exit(1)
        except Exception as e:
            print("OK, captured error")

    async def atest_valueOf(self):
        a = self.demo.arr.valueOf()
        print("A", a)
        assert a[0] == 1
        assert a[1] == 5
        assert a[2] == 3
        print("Array", self.demo.arr.valueOf())

    async def atest_once(self):
        self.demo.wait()
        once(self.demo, "done")

    async def atest_assignment(self):
        self.demo.x = 3

    async def atest_eval(self):
        DemoClass = require("./test.js").DemoClass
        self.demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
        pythonArray = []
        pythonObject = {"var": 3}
        demo = self.demo
        # fmt: off
        print('running')
        result=await eval_js_a('''
            for (let i = 0; i < 10; i++) {
                await pythonArray.append(i);
                pythonObject[i] = i;
            }
            pythonObject.var = 5;
            const fn = await demo.moreComplex()
            console.log('wrapped fn', await fn()); // Should be 3
            return 2
        ''')
        print(result)
        # fmt: on

        print("My var", pythonObject)

    async def atest_bigint(self):
        bigInt = eval_js('100000n')
        print(bigInt)

    async def atest_nullFromJsReturnsNone(self):
        assert self.demo.returnNull() is None

# Define the order of test methods
test_order = [
    "test_require",
    "test_classes",
    "test_iter",
    "test_events",
    "test_arrays",
    "test_errors",
    "test_valueOf",
    "test_once",
    "test_assignment",
    "test_eval",
    "test_bigint"
]
atestorder=[
    "atest_require",
    "atest_classes",
    "atest_iter",
    
    "atest_callback",
    
    "atest_events",
    "atest_arrays",
    "atest_errors",
    "atest_valueOf",
    "atest_once",
    "atest_assignment",
    "atest_eval",
    "atest_bigint",
    "atest_nullFromJsReturnsNone"
]

@pytest.mark.asyncio
async def test_my_coroutine():
    init_js()
    async_instance=TestJavaScriptLibraryASYNC()
    for test_name in test_order:
        print('testing sync',test_name)
        getattr(async_instance, test_name)()
    del async_instance.demo
    for test_name in atestorder:
        print('testing async',test_name)
        await getattr(async_instance, test_name)()
    del async_instance
    
    # test_instance = TestJavaScriptLibrary()
    # for test_name in test_order:
    #     print('testing ',test_name)
    #     getattr(test_instance, test_name)()
    # del async_instance.demo



if __name__ == "__main__":
    asyncio.run(test_my_coroutine())

    # Run all test methods in the specified order
    #pytest.main()