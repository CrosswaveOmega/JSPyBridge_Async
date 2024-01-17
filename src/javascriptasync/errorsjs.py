from __future__ import annotations

import re
import traceback
import asyncio
from typing import List
from .core.abc import BaseError


INTERNAL_FILES = ["bridge.js", "pyi.js", "errors.js", "deps.js", "test.js"]


class JavaScriptError(Exception):
    """
    Custom exception class for JavaScript errors.
    """

    def __init__(self, call: str, jsStackTrace: List[str], *args, **kwargs):
        """
        Initialize a JavaScriptError object.

        Args:
            call (str): The failed JavaScript call.
            jsStackTrace (List[str]): JavaScript stack trace.
        """

        super().__init__(*args, **kwargs)  # Assuming BaseError is the base class of JavaScriptError
        self.call = call
        self.js = jsStackTrace
        self.failedCall = None
        self.jsErrorline = None
        self.jsStackTrace = None
        self.jsErrorMessage = None
        self.pyErrorline = None
        self.pyStackTrace = None

    def get_error_message(self):
        return self.getErrorMessage(self.call, self.js, traceback.format_tb(self.__traceback__))

    def __str__(self):
        return self.get_error_message()

    def __repr__(self):
        return str(self)

    def print_error(self) -> List[str]:
        lines = []
        log = lambda *s: lines.append(" ".join(s))
        if self.failedCall == "FatalError":
            log("NODEJS RAISED A FATAL ERROR.")
        else:
            log(
                "NodeJS",
                " JavaScript Error ",
                f"Call to '{self.failedCall.replace('~~', '')}' failed:",
            )

        log("[Context: Python]")
        for at, line in self.pyStackTrace:
            if "javascriptasync" in at or "IPython" in at:
                continue
            if not line:
                log(" ", at)
            else:
                log(">", format_line(line))
                log(" ", at)

        log(">", format_line(self.pyErrorline))

        log("\n[Context: NodeJS]\n")

        for traceline in reversed(self.jsStackTrace):
            log(" ", traceline)

        log(">", format_line(self.jsErrorline))
        log("Bridge", self.jsErrorMessage)

        return lines

    def processPyStacktrace(self, stack):
        lines = []
        error_line = ""
        stacks = stack

        for lin in stacks:
            lin = lin.rstrip()
            if lin.startswith("  File"):
                if lin is None:
                    continue
                tokens = lin.split("\n")
                lin = tokens[0]
                Code = tokens[1] if len(tokens) > 1 else "<via standard input>"
                fname = lin.split('"')[1]
                line = re.search(r"\, line (\d+)", lin).group(1)
                at = re.search(r"\, in (.*)", lin)
                if at:
                    at = at.group(1)
                else:
                    at = "^"
                lines.append([f"at {at} ({fname}:{line})", Code.strip()])
            elif lin.strip():
                error_line = lin.strip()

        return error_line, lines

    def isInternal(self, file):
        for f in INTERNAL_FILES:
            if f in file:
                return True
        return False

    def processJsStacktrace(self, stack, allowInternal=False):
        lines = []
        message_line = ""
        error_line = ""
        found_main_line = False
        # print("Allow internal", allowInternal)
        if stack is None:
            stack = ["No js stacktracce?"]
        stacks = stack if (type(stack) is list) else stack.split("\n")
        for line in stacks:
            if not message_line:
                message_line = line
            if allowInternal:
                lines.append(line.strip())
            elif (not self.isInternal(line)) and (not found_main_line):
                abs_path = re.search(r"\((.*):(\d+):(\d+)\)", line)
                file_path = re.search(r"(file:\/\/.*):(\d+):(\d+)", line)
                base_path = re.search(r"at (.*):(\d+):(\d+)$", line)
                if abs_path or file_path or base_path:
                    path = abs_path or file_path or base_path
                    fpath, errorline, _ = path.groups()
                    if fpath.startswith("node:"):
                        continue
                    with open(fpath, "r", encoding="utf8") as f:
                        flines = f.readlines()
                        error_line = flines[int(errorline) - 1].strip()
                    lines.append(line.strip())
                    found_main_line = True
            elif found_main_line:
                lines.append(line.strip())

        if allowInternal and not error_line:
            error_line = "^"
        if error_line:
            return (error_line, message_line, lines)
        return None

    def getErrorMessage(self, failed_call, jsStackTrace, pyStacktrace):
        try:
            tuple_a = self.processJsStacktrace(jsStackTrace)
            if tuple_a is None:
                tuple_a = self.processJsStacktrace(jsStackTrace, True)
            (jse, jsm, jss) = tuple_a
            pye, pys = self.processPyStacktrace(pyStacktrace)
            self.failedCall = failed_call
            self.jsErrorline = jse
            self.jsStackTrace = jss
            self.jsErrorMessage = jsm
            self.pyErrorline = pye
            self.pyStackTrace = pys
            lines = self.print_error()
            return "\n".join(lines)
        except Exception as e:  # pylint: disable=broad-except
            print("Error in exception handler")

            print(e)
            pys = "\n".join(pyStacktrace)
            print(f"** JavaScript Stacktrace **\n{jsStackTrace}\n** Python Stacktrace **\n{pys}")
            return jsStackTrace


class FatalJavaScriptError(JavaScriptError):
    """
    Raised when something caused the Javascript runtime to crash.
    """


class NoAsyncLoop(BaseError):
    """
    Raised when calling @On when the passed in handler is an async function
    And no event loop was passed into the args
    """


class NoPyiAction(BaseError):
    """
    Raised when PYI does not have a given set action in PYI.

    """


class NoConfigInitalized(BaseError):
    """
    Raised if there was no JSConfig initalized.
    """


class InvalidNodeJS(BaseError):
    """
    Raised if node.js was either not installed or is unreachable.

    """


class InvalidNodeOp(BaseError):
    """
    Raised if a NodeOp is invalid

    """


class AsyncReminder(BaseError):
    """
    Raised if an syncrounous magic method was called in amode

    """


class NodeTerminated(BaseError):
    """
    Raised if the Node process terminated for any reason.

    """


class BridgeTimeout(TimeoutError):
    """
    Raised if a request times out.
    """

    def __init__(self, message, action, ffid, attr):
        self.message = message
        self.action = action
        self.ffid = ffid
        self.attr = attr


class BridgeTimeoutAsync(asyncio.TimeoutError):
    """
    Raised if a request times out in async mode
    """

    def __init__(self, message, action, ffid, attr):
        self.message = message
        self.action = action
        self.ffid = ffid
        self.attr = attr


def format_line(line: str) -> str:
    """
    Format a line of code with appropriate colors.

    :param line: The code line to be formatted.
    :return: Formatted code line.
    """
    if line.startswith("<") or line.startswith("\\"):
        return line
    statements = [
        "const ",
        "await ",
        "import ",
        "let ",
        "var ",
        "async ",
        "self ",
        "def ",
        "return ",
        "from ",
        "for ",
        "raise ",
        "try ",
        "except ",
        "catch ",
        ":",
        "\\(",
        "\\)",
        "\\+",
        "\\-",
        "\\*",
        "=",
    ]
    secondary = ["{", "}", "'", " true", " false"]
    for statement in statements:
        exp = re.compile(statement, re.DOTALL)
        line = re.sub(exp, statement.replace("\\", "") + "", line)
    for second in secondary:
        exp = re.compile(second, re.DOTALL)
        line = re.sub(exp, second + "", line)
    return line


class Chalk:
    """
    Chalk class for text coloring.
    """

    def red(self, text):
        return "\033[91m" + text + "\033[0m"

    def blue(self, text):
        return "\033[94m" + text + "\033[0m"

    def green(self, text):
        return "\033[92m" + text + "\033[0m"

    def yellow(self, text):
        return "\033[93m" + text + "\033[0m"

    def bold(self, text):
        return "\033[1m" + text + "\033[0m"

    def italic(self, text):
        return "\033[3m" + text + "\033[0m"

    def underline(self, text):
        return "\033[4m" + text + "\033[0m"

    def gray(self, text):
        return "\033[2m" + text + "\033[0m"

    def bgred(self, text):
        return "\033[41m" + text + "\033[0m"

    def darkred(self, text):
        return "\033[31m" + text + "\033[0m"

    def lightgray(self, text):
        return "\033[37m" + text + "\033[0m"

    def white(self, text):
        return "\033[97m" + text + "\033[0m"


chalk = Chalk()
# Custom exception logic

# Fix for IPython as it blocks the exception hook
# https://stackoverflow.com/a/28758396/11173996
# try:
#     # __IPYTHON__
#     if haspackage("IPython"):
#         import IPython

#         oldLogger = IPython.core.interactiveshell.InteractiveShell.showtraceback

#         def newLogger(*a, **kw):
#             ex_type, ex_inst, tb = sys.exc_info()
#             if ex_type is JavaScriptError:
#                 pyStacktrace = traceback.format_tb(tb)
#                 # The Python part of the stack trace is already printed by IPython
#                 print(getErrorMessage(ex_inst.call, ex_inst.js, pyStacktrace))
#             else:
#                 oldLogger(*a, **kw)

#         IPython.core.interactiveshell.InteractiveShell.showtraceback = newLogger
# except ImportError:
#     pass

# orig_excepthook = sys.excepthook


# def error_catcher(error_type, error, error_traceback):
#     """
#     Catches JavaScript exceptions and prints them to the console.
#     """
#     logs.error("ERROR.")
#     #print("TRACE:", traceback.format_exc())
#     #if error_type is JavaScriptError:        error.py=error_traceback
#     orig_excepthook(error_type, error, error_traceback)


# sys.excepthook = error_catcher
# ====
