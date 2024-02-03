from pathlib import Path
import time
from javascriptasync import require, eval_js, init_js
from javascriptasync.emitters import On, Once, off, once
from javascriptasync.errorsjs import BridgeTimeout
import pytest

class TestJavaScriptLibrary:
    @pytest.fixture(autouse=True)
    def setUp_teardown_main(self) -> None: 
        init_js()
        DemoClass = require("./test.js").DemoClass
        self.demo = DemoClass("blue", {"a": 3}, lambda v: self.assertEquals(v, 3))

        yield
        print("done.")
        
    def assertEquals(self, cond, val):
        assert cond == val
        
    def some_method(self, text):
        print("Callback called with", text)
        assert text == "It works !"

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
        assert self.demo.toString() == "123!"
        assert self.demo.ok().x == "wow"
        assert DemoClass.hello() == "world"

    def test_iter(self):
        DemoClass = require("./test.js").DemoClass
        demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

        f = None
        for i in demo.array():
            print("i", i)
            f = i
        assert f.a == 3

        expect = ["x", "y", "z"]
        for key in demo.object():
            assert key == expect.pop(0)

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
        assert a[1] == 2 #5
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
        bigInt = eval_js("100000n")
        print(bigInt)

    def test_nullFromJsReturnsNone(self):
        assert self.demo.returnNull() is None

    def test_timeout(self):
        DemoClass = require("./test.js").DemoClass
        self.demo = DemoClass("blue", {"a": 3}, lambda v: print("Should be 3", v))

        try:
            self.demo.this_times_out(4000,timeout=2)
            print("Failed to error")
            assert False
        except BridgeTimeout as e:
            print("timedout!",e)
            time.sleep(4)

if __name__ == "__main__":
    print("NA")

    # Run all test methods in the specified order
    # pytest.main()
