"""Simple code profiler to generate plantuml sequence diagrams for a single specific Thread."""

from types import NoneType
import pytest
import asyncio
import pytest

import sys


import threading

to_ignore = [
    "threading",
    "javascriptasync.core.jslogging",
    "logging",
    "enum",
    "dumps",
    "loads",
    "json.decoder",
    "ntpath",
    "json",
    "json.encoder",
    "subprocess",
    "os",
    "inspect",
    "collections.abc",
    "contextlib",
    "_weakrefset",
    "weakref",
    "genericpath",
    "encodings.cp1252",
    "abc",
]


# to_ignore=[]
def prettyprint(arg, maxlen):
    out = str(arg)

    if isinstance(arg, list):
        out = ""
        out = "[" + "],\\n[".join(prettyprint(a, maxlen) for a in arg) + "]"
    elif isinstance(arg, dict):
        out = ""
        for key in arg.keys():
            out += f"{key},"
    elif len(out) > maxlen:
        out = f"{out[0:8]}... [{len(out)-16}] ...{out[-8:]}"
    return out


def primitive_check(thisval, maxlen):
    primitive_types = (int, bool, float, str, NoneType)
    if isinstance(thisval, primitive_types):
        if isinstance(thisval, str):
            if len(thisval) > 10:
                return "str"
        return thisval
    else:
        return prettyprint(thisval, maxlen)


class CodeProfiler:
    def __init__(self, filename="profilered", ignore_private=True):
        self.function_calls = []
        self.call_stack = []
        self.all_names = set()
        self.maxlen = 64
        self.output_file = f"{filename}.puml"
        self.ignore_private = ignore_private
        self.ignore_classes = ["Queue", "Event", "Thread", None, "JSONDecoder"]
        self.write_to_file("@startuml\nautoactivate on\n", mode="w+")

    def filter_valid_ascii(self, input_string):
        # Filter out characters that are not valid ASCII
        valid_ascii_chars = [char for char in input_string if ord(char) < 128]
        return "".join(valid_ascii_chars)

    def write_to_file(self, value, mode="a+"):
        with open(self.output_file, mode, encoding="utf8") as file:
            # print('writing',value)

            file.write(self.filter_valid_ascii(value))

    def trace_calls(self, frame, event, arg):
        if event == "call":
            function_name = frame.f_code.co_name
            caller_name = frame.f_back.f_code.co_name if frame.f_back else None
            caller_class = None

            thread_id = threading.current_thread().ident
            if "self" in frame.f_back.f_locals:
                caller_class = frame.f_back.f_locals["self"].__class__.__name__
                caller_name = caller_class

                caller_name = f"{thread_id}{caller_class}"
            if "cls" in frame.f_back.f_locals:
                if frame.f_back.f_locals["cls"] is not None:
                    caller_class = frame.f_back.f_locals["cls"].__name__
                    caller_name = caller_class

                    caller_name = f"{thread_id}{caller_class}"
            class_nm = class_name = None
            if "self" in frame.f_locals:
                class_nm = frame.f_locals["self"].__class__.__name__
                class_name = f"{thread_id}{class_nm}"
            if "cls" in frame.f_locals:
                # print("FRE",frame.f_locals["cls"])
                if frame.f_locals["cls"] is not None:
                    class_nm = frame.f_locals["cls"].__name__
                    class_name = f"{thread_id}{class_nm}"
            # print(caller_name,class_name,function_name)
            if (
                class_nm in self.ignore_classes
                or function_name == "<listcomp>"
                or frame.f_globals.get("__name__") in to_ignore
                or (class_name in self.ignore_classes)
                or (self.ignore_private == True and function_name.startswith("_"))
            ):
                self.call_stack.append((caller_name, class_name, function_name, "call", False))
                return self.trace_calls

            self.all_names.add(frame.f_globals.get("__name__"))
            self.call_stack.append((caller_name, class_name, function_name, "call", True))
            frame_locals_items = frame.f_locals.items()
            allitems = []
            for key, value in frame_locals_items:
                if key not in ["self", "cls"]:
                    if value is not None:
                        thisval = primitive_check(value, self.maxlen)
                        allitems.append((key, thisval))

            arg = prettyprint(allitems, self.maxlen)
            if caller_name is not None:
                self.function_calls.append((caller_name, (class_name, function_name, "call", arg)))
                arg = arg[:256]
                # if class_name:
                #     self.write_to_file(f"{caller_name} -> {class_name} : {function_name}({arg})\n")
                # else:
                #     self.write_to_file(f"{caller_name} -> {function_name}:{arg}\n")

        elif event == "return":
            if self.call_stack:
                call_name, classname, function_name, _, include = self.call_stack.pop()
                if include:
                    caller_name = frame.f_code.co_name

                    if caller_name is not None:
                        self.function_calls.append(
                            (caller_name, (f"{classname}", function_name, "return", arg))
                        )
                        # self.write_to_file(f"return from {function_name}: with {out}\n")

        return self.trace_calls

    def __enter__(self):
        sys.setprofile(self.trace_calls)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.setprofile(None)
        self.to_plantuml()
        self.write_to_file("@enduml")
        # self.output_file.close()

    def to_plantuml(self):
        for caller_name, (class_name, function_name, event_type, arg) in self.function_calls:
            if event_type == "call":
                arg = str(arg)
                if class_name:
                    self.write_to_file(f"{caller_name} -> {class_name} : {function_name}({arg})\n")

                else:
                    self.write_to_file(f"{caller_name} -> {function_name}:{arg}\n")
            elif event_type == "return":
                out = prettyprint(arg, self.maxlen)
                out = out.replace("\n", "\\n")
                self.write_to_file(f"return from {function_name}: with {str(out)}\n")
