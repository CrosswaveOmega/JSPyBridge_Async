import pytest
import asyncio
import pytest

"""

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
    "test_bigint",
]
atestorder = [
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
    "atest_nullFromJsReturnsNone",
    "asynctask_stop",
    "long_running_asynctask",
]


@pytest.mark.asyncio
async def test_my_coroutine():
    await init_js_a()

    set_log_level(logging.WARNING)

    async_instance = TestJavaScriptLibraryASYNC()
    for test_name in test_order:
        print("testing sync", test_name)
        getattr(async_instance, test_name)()
    for test_name in atestorder:
        print("testing async", test_name)
        await getattr(async_instance, test_name)()
    del async_instance

    # test_instance = TestJavaScriptLibrary()
    # for test_name in test_order:
    #     print('testing ',test_name)
    #     getattr(test_instance, test_name)()
    # del async_instance.demo
from javascriptasync import require, eval_js, init_js, init_js_a, eval_js_a, require_a
from javascriptasync.emitters import On, Once, off, once
from javascriptasync import AsyncTaskA, AsyncTaskUtils
from javascriptasync.logging import set_log_level
from javascriptasync.config import Config
import logging
import pytest
import asyncio
init_js()
@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    Config.get_inst().set_asyncio_loop(loop)
    yield loop
    loop.close()
def setup_demo(DemoClass):
    demo = DemoClass("blue", {"a": 3}, lambda v: assert_equals(v, 3))
    return demo

@pytest.fixture
def DemoClass():
    DemoClass = require("./test.js").DemoClass
    return DemoClass

@pytest.fixture
def demo():
    DemoClass = require("./test.js").DemoClass
    demo = DemoClass("blue", {"a": 3}, lambda v: assert_equals(v, 3))
    return demo

def assert_equals(cond, val):
    assert cond == val


def test_require():
    chalk = require("chalk")
    fs = require("fs")
    print("Hello", chalk.red("world!"))
    test = require("./test.js")


def test_classes(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    assert demo.ok()(1, 2, 3) == 6
    assert demo.toString() == "123!"
    assert demo.ok().x == "wow"
    assert DemoClass.hello() == "world"


def test_iter(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    f = None
    for i in demo.array():
        print("i", i)
        f = i
    assert f.a == 3

    expect = ["x", "y", "z"]
    for key in demo.object():
        assert key == expect.pop(0)


def some_method(text):
    print("Callback called with", text)
    assert text == "It works !"


def test_events(DemoClass,demo):
    # demo = setup_demo(DemoClass)

    @On(demo, "increment")
    def handler(this, fn, num, obj):
        print("Handler caled", fn, num, obj)
        if num == 7:
            off(demo, "increment", handler)

    @Once(demo, "increment")
    def onceIncrement(this, *args):
        print("Hey, I'm only called once !")

    demo.increment()


def test_arrays(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    demo.arr[1] = 5
    demo.obj[1] = 5
    demo.obj[2] = some_method
    print("Demo array and object", demo.arr, demo.obj)


def test_errors(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    try:
        demo.error()
        print("Failed to error")
        exit(1)
    except Exception as e:
        print("OK, captured error")


def test_valueOf(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    a = demo.arr.valueOf()
    print("This array: A", a)
    assert a[0] == 1
    assert a[1] == 2
    assert a[2] == 3
    print("Array", demo.arr.valueOf())


def test_once(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    demo.wait()
    once(demo, "done")


def test_assignment(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    demo.x = 3


def test_eval():
    DemoClass = require("./test.js").DemoClass
    demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
    pythonArray = []
    pythonObject = {"var": 3}
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


def test_bigint():
    bigInt = eval_js("100000n")
    print(bigInt)


def test_nullFromJsReturnsNone(DemoClass,demo):
    # demo = setup_demo(DemoClass)
    assert demo.returnNull() is None


@pytest.mark.asyncio
async def atest_require(event_loop):
    chalk = await require_a("chalk")
    fs = await require_a("fs")

    print("Hello", chalk.red("world!"))
    test = await require_a("./test.js")


@pytest.mark.asyncio
async def atest_classes(event_loop):
    DemoClass = (await require_a("./test.js")).DemoClass
    demo = await DemoClass("blue", {"a": 3}, lambda v: assert_equals(v, 3), coroutine=True)
    # New pseudo operator
    demo2 = await DemoClass.new("blue", {"a": 3}, lambda v: assert_equals(v, 3), coroutine=True)

    assert await demo.ok()(1, 2, 3, coroutine=True) == 6
    assert demo.toString() == "123!"
    assert demo.ok().x == "wow"
    assert DemoClass.hello() == "world"


@pytest.mark.asyncio
async def atest_iter(event_loop):
    DemoClass = require("./test.js").DemoClass
    demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

    f = None
    async for i in demo.array():
        print("i", i)
        f = i
    assert f.a == 3

    expect = ["x", "y", "z"]
    async for key in demo.object():
        assert key == expect.pop(0)


@pytest.mark.asyncio
async def atest_callback(event_loop,DemoClass,demo):
    # demo = setup_demo(DemoClass)
    await demo.callback(some_method, coroutine=True)


@pytest.mark.asyncio
async def atest_events(event_loop,demo):
    print("events start")
    @On(demo, "increment")
    @pytest.mark.asyncio
    async def handler(this, fn, num, obj):
        print("Handler called", fn, num, obj)
        if num == 7:
            print("off")
            demo.off("increment", handler)
            # off(self.demo, "increment", handler)

    @Once(demo, "increment")
    @pytest.mark.asyncio
    async def onceIncrement(this, *args):
        print("Hey, I'm only called once !")

    demo.increment()
    await asyncio.sleep(2)


@pytest.mark.asyncio
async def atest_arrays(event_loop,demo):
    # demo = setup_demo(DemoClass)
    demo.arr[1] = 5
    demo.obj[1] = 5
    demo.obj[2] = some_method
    print("Demo array and object", demo.arr, demo.obj)


@pytest.mark.asyncio
async def atest_errors(event_loop,demo):
    # demo = setup_demo(DemoClass)
    try:
        demo.error()
        print("Failed to error")
        exit(1)
    except Exception as e:
        print("OK, captured error")


@pytest.mark.asyncio
async def atest_valueOf(event_loop,demo):
    # demo = setup_demo(DemoClass)
    a = demo.arr.valueOf()
    print("A", a)
    assert a[0] == 1
    assert a[1] == 5
    assert a[2] == 3
    print("Array", demo.arr.valueOf())


@pytest.mark.asyncio
async def atest_once(event_loop,demo):
    # demo = setup_demo(DemoClass)
    demo.wait()
    once(demo, "done")


@pytest.mark.asyncio
async def atest_assignment(event_loop,demo):
    # demo = setup_demo(DemoClass)
    demo.x = 3


@pytest.mark.asyncio
async def atest_eval(event_loop):
    DemoClass = require("./test.js").DemoClass
    demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
    pythonArray = []
    pythonObject = {"var": 3}
    # fmt: off
    print('running')
    result = await eval_js_a('''
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


@pytest.mark.asyncio
async def atest_bigint(event_loop):
    bigInt = eval_js("100000n")
    print(bigInt)


@pytest.mark.asyncio
async def atest_nullFromJsReturnsNone(event_loop,demo):
    # demo = setup_demo(DemoClass)
    assert demo.returnNull() is None


@pytest.mark.asyncio
async def asynctask_stop(event_loop):
    @AsyncTaskA()
    @pytest.mark.asyncio
    async def routine(task):
        while not task.stopping:
            print(task)
            await task.sleep(1)

    await AsyncTaskUtils.start(routine)
    await asyncio.sleep(1)
    print("stop!")
    await AsyncTaskUtils.stop(routine)
    await asyncio.sleep(1)


@pytest.mark.asyncio
async def long_running_asynctask(event_loop):
    @AsyncTaskA()
    @pytest.mark.asyncio
    async def my_function(task):
        for i in range(0, 5):
            print(str(task), "this is a run ", i)
            await asyncio.sleep(0.4)
        print("TASK OVER.")

    print("corororo")
    await AsyncTaskUtils.start(my_function)
    for i in range(0, 3):
        print("MAIN LOOP")
        await asyncio.sleep(1)
    await asyncio.sleep(1)

'''
# Use the following command to run the tests:
# pytest -k test_my_coroutine
@pytest.mark.asyncio
async def test_my_coroutine():
    await init_js_a()

    set_log_level(logging.WARNING)

    for name, obj in locals().items():
        if name.startswith("test_") or name.startswith("atest_"):
            print(f"testing {name}")
            if asyncio.iscoroutinefunction(obj):
                await obj()
            else:
                obj()

"""



def test_context():
    import os
    import time
    import logging
    from javascriptasync import JSContext
    from javascriptasync.emitters import On, off, Once, once
    from javascriptasync.logging import setup_logging, get_filehandler
    context=JSContext()
    context.init_js()
    console = context.get_console()  # TODO: Remove this in 1.0
    testmodule = context.require("./test.js",store_as='NEW')
    DemoClass=context.NEW.DemoClass

    chalk, fs = context.require("chalk"), context.require("fs")

    console.log("Hello", chalk.red("world!"))
    fs.writeFileSync("HelloWorld.txt", "hi!")

    demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
    demo2 = DemoClass.new("blue", {"a": 3}, lambda v: print("Should be 3", v))

    print(demo.ok()(1, 2, 3))
    print(demo.ok().x)
    print(demo.toString())
    print("Hello ", DemoClass.hello())

    console.log(demo.other(demo2), demo.array(), demo.array()["0"])

    for i in demo.array():
        print("i", i)

    def some_method(*args):
        print("Callback called with", args)

    demo.callback(some_method)

    @On(demo, "increment")
    def handler(this, fn, num, obj):
        print("Handler caled", fn, num, obj)
        if num == 7:
            off(demo, "increment", handler)

    @Once(demo, "increment")
    def onceIncrement(this, *args):
        print("Hey, I'm only called once !")

    demo.increment()
    time.sleep(0.5)

    demo.arr[1] = 5
    demo.obj[1] = 5
    demo.obj[2] = some_method
    print("Demo array and object", demo.arr, demo.obj)

    try:
        demo.error()
        print("Failed to error")
        exit(1)
    except Exception as e:
        print("OK, captured error")

    print("Array", demo.arr.valueOf())

    demo.wait()
    once(demo, "done")

    demo.x = 3

    pythonArray = []
    pythonObject = {"var": 3}

    # fmt: off
    print(context.eval_js('''
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

    print("OK, we can now exit")
    del context
    


if __name__ == "__main__":
    test_context()
