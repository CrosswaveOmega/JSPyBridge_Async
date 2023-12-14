from javascriptasync import require, require_a, eval_js, eval_js_a, init_js, init_js_a
import javascriptasync
from javascriptasync.emitters import On, Once, off, once, once_a
from javascriptasync import AsyncTaskA, AsyncTaskUtils
from javascriptasync.logging import set_log_level
from javascriptasync.config import Config
import logging
import pytest
import asyncio

init_js()

@pytest.mark.asyncio
class TestJavaScriptLibraryASYNC:
    @pytest.fixture(autouse=True)
    async def setUp_teardown(self) -> None: 
        loop = asyncio.get_running_loop()
        Config.get_inst().set_asyncio_loop(loop)
        module = await require_a("./test.js",amode=True)
        DemoClass = module.DemoClass
        self.demo = await DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3))

        yield
        print("done.")

    def assertEquals(self, cond, val):
        assert cond == val
        
    def some_method(self, text):
        print("Callback called with", text)
        assert text == "It works !"

    @pytest.mark.asyncio
    async def test_a_require(self):
        chalk = await require_a("chalk",amode=True)
        fs = await require_a("fs")
        red=await chalk.red("world!") 
        print("Hello", red)
        test = await require_a("./test.js")

    @pytest.mark.asyncio
    async def test_a_classes(self):
        DemoClass = (await require_a("./test.js")).DemoClass
        self.demo = await DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3), coroutine=True)
        # New psuedo operator
        demo2 = await DemoClass.new("blue", {"a": 3}, lambda v: self.assertEquals(v, 3), coroutine=True)

        assert await self.demo.ok()(1, 2, 3, coroutine=True) == 6
        assert self.demo.toString() == "123!"
        assert self.demo.ok().x == "wow"
        assert DemoClass.hello() == "world"

    @pytest.mark.asyncio
    async def test_a_iter(self):
        DemoClass = (await require_a("./test.js",amode=True)).get_s('DemoClass')
        demo = await DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

        f = None
        print(demo.array());
        async for i in demo.array():
            print("i", i)
            f = i
        a=await f.a
        assert a == 3

        expect = ["x", "y", "z"]
        async for key in demo.object():
            assert key == expect.pop(0)

    @pytest.mark.asyncio
    async def test_a_callback(self):
        await self.demo.callback(self.some_method, coroutine=True)

    @pytest.mark.asyncio
    async def test_a_events(self):
        module = await require_a("./test.js",amode=True)
        DemoClass = module.DemoClass
        self.demo = await DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3))
        print("events start")

        async def handler(this, fn, num, obj):
            print("Handler called", fn, num, obj)
            if num == 7:
                print("off")
                await self.demo.off_a("increment", handler)
                #off(self.demo, "increment", handler)

        await self.demo.on_a("increment",handler)

        async def onceIncrement(this, *args):
            print("Hey, I'm only called once !")
        self.demo.once("increment",onceIncrement)
        await self.demo.increment()
        await asyncio.sleep(2)

    @pytest.mark.asyncio
    async def test_a_arrays(self):
        await self.demo.arr.set_item_a(1,5)
        await self.demo.obj.set_item_a(1,2)
        await self.demo.obj.set_item_a(2,self.some_method)
        print("Demo array and object",  self.demo.arr,self.demo.obj)
        a = self.demo.arr.valueOf()
        print("A", a)
        assert a[0] == 1
        assert a[1] == 5
        assert a[2] == 3
        print("Array", self.demo.get_s('arr').valueOf())

    @pytest.mark.asyncio
    async def test_a_errors(self):
        try:
            await self.demo.error()
            print("Failed to error")
            exit(1)
        except Exception as e:
            print("OK, captured error")

    @pytest.mark.asyncio
    async def test_a_valueOf(self):
        a = await self.demo.arr.valueOf()
        print("A", a)
        assert a[0] == 1
        assert a[1] == 2
        assert a[2] == 3
        print("Array", self.demo.arr.valueOf())

    @pytest.mark.asyncio
    async def test_a_once(self):
        await self.demo.wait()
        await once_a(self.demo, "done")

    @pytest.mark.asyncio
    async def test_a_assignment(self):
        await self.demo.set_a('s', 3)

    @pytest.mark.asyncio
    async def test_chain_errors(self):
        try:
            module=await require_a("./test.js",amode=True)
            democlass = module.DemoClass

            demo = await democlass("blue", {"a": 3}, lambda v: print("Should be 3", v))
            chain=await demo.one.two.three.four.five.six.seven.eight.nine.ten.eleven
            print("Failed to error")
            exit(1)
        except Exception as e:
            print("OK, captured error")


    @pytest.mark.asyncio
    async def test_a_eval(self):

        module=await require_a("./test.js",amode=True)
        demo = await module.DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))
        # await demo.getdeep()
        print(demo)
        pythonArray = []
        pythonObject = {"var": 3}
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
        print('clear')
        print(result)
        # fmt: on

        print("My var", pythonObject)

    @pytest.mark.asyncio
    async def test_a_bigint(self):
        bigInt = await eval_js_a("100000n")
        print(bigInt)

    @pytest.mark.asyncio
    async def test_a_nullFromJsReturnsNone(self):
        await self.demo.returnNull
        assert self.demo.returnNull.call_s() is None

    @pytest.mark.asyncio
    async def test_asynctask_stop(self):
        @AsyncTaskA()
        async def routine(task):
            while (
                not task.stopping
            ):  # You can also just do `while True` as long as you use task.sleep and not time.sleep
                print(task)
                # print('asynciotask')
                await task.sleep(1)  # Sleep for a bit to not block everything else

        await AsyncTaskUtils.start(routine)
        await asyncio.sleep(1)
        print("stop!")
        await AsyncTaskUtils.stop(routine)
        await asyncio.sleep(1)

    @pytest.mark.asyncio
    async def test_long_running_asynctask(self):
        @AsyncTaskA()
        async def my_function(task):
            # Your function's logic here
            for i in range(0, 5):
                print(str(task), "this is a run ", i)
                await asyncio.sleep(0.4)  # Simulating some work
            print("TASK OVER.")

        print("corororo")
        await AsyncTaskUtils.start(my_function)
        for i in range(0, 3):
            print("MAIN LOOP")
            await asyncio.sleep(1)
        await asyncio.sleep(1)
