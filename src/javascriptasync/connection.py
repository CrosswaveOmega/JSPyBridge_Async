from __future__ import annotations
from typing import TYPE_CHECKING

import importlib
from queue import Empty, Queue

# import asyncio
import threading
import subprocess
import json
import time

# import signal

import os
import sys
from typing import Any, Dict, List, TextIO, Union

if TYPE_CHECKING:
    from .configjs import JSConfig

from .core.jslogging import log_print, log_debug, log_info, log_error, log_critical, log_warning
from .util import haspackage
from .errorsjs import FatalJavaScriptError, InvalidNodeJS, NodeTerminated
from .json_patch import JSONRequestDecoder

ISCLEAR = False
ISNOTEBOOK = False
try:
    if haspackage("IPython"):
        IPython = importlib.import_module("IPython")
        get_ipython = IPython.get_ipython
        if "COLAB_GPU" in os.environ:
            ISCLEAR = True
        else:
            ipythonname = get_ipython().__class__.__name__
            if ipythonname in ["ZMQInteractiveShell", "TerminalInteractiveShell"]:
                print("Notebook?")
                ISNOTEBOOK = True
    else:
        ISCLEAR = False
except (ImportError, KeyError, AttributeError) as pre_error:
    log_error(pre_error)
    ISCLEAR = False

# The "root" interface to JavaScript with FFID 0


class ConnectionClass:
    """
    Encapsulated connection class for interacting with JavaScript.

    This class initalizes a node.js instance, sends information from Python to JavaScript, and recieves input from JavaScript back to Python.

    Attributes:
        config (JSConfig): Reference to the active JSConfig object.
        endself(bool): if the thread is ending, send nothing else.
        stdout (TextIO): The standard output.
        modified_stdout (bool): True if stdout has been altered in some way, False otherwise.
        notebook (bool): True if running in a Jupyter notebook, False otherwise.
        NODE_BIN (str): The path to the Node.js binary.
        directory_name (str): The directory containing this file.
        proc (subprocess.Popen): The subprocess for running JavaScript.
        com_thread (threading.Thread): The thread for handling communication with JavaScript.
        stdout_thread (threading.Thread): The thread for reading standard output.

        sendQ (list): List for outgoing messages to JavaScript before the process fully starts.
        stderr_lines (list): Lines piped from JavaScript Process
    """

    # Encapsulated connection to make this file easier to work with.
    # Special handling for IPython jupyter notebooks

    def is_notebook(self):
        """
        Check if running in a Jupyter notebook.

        Returns:
            bool: True if running in a notebook, False otherwise.
        """
        return ISNOTEBOOK

    def __init__(self, configval: JSConfig):
        """
        Initialize the ConnectionClass.

        Args:
            config (JSConfig): Reference to the active JSConfig object.
        """

        self.stdout: TextIO = sys.stdout

        self.notebook = False
        self.NODE_BIN = os.environ.get("NODE_BIN") if hasattr(os.environ, "NODE_BIN") else "node"
        self.check_nodejs_installed()

        self.directory_name: str = os.path.dirname(__file__)
        self.proc: subprocess.Popen = None
        self.com_thread: threading.Thread = None
        self.stdout_thread: threading.Thread = None
        # self.stderr_lines: List[str] = []
        self.stderr_lines: Queue[str] = Queue()
        self.sendQ: list = []
        self.config: JSConfig = configval

        # Modified stdout
        self.endself = False
        self.modified_stdout = (sys.stdout != sys.__stdout__) or (
            getattr(sys, "ps1", sys.flags.interactive) == ">>> "
        )

        self.status = (self.is_notebook() << 1) | self.modified_stdout
        self.notebook = (self.status & 2) != 0
        self.stdout = subprocess.PIPE if (self.status & 1) != 0 else self.stdout

        self.earlyterm = False
        self.kill_error = None
        # atexit.register(self.stopwrapper)

    def stopwrapper(self):
        log_critical("called wrapper")
        self.stop()

    def check_nodejs_installed(self):
        """Check if node.js is installed.

        Raises:
            InvalidNodeJS: Node.JS was not installed.
        """

        try:
            output = subprocess.check_output([self.NODE_BIN, "-v"])
            print("NodeJS is installed: Current Version Node.js version:", output.decode().strip())
        except OSError as e:
            errormessage = (
                "COULD NOT FIND A VALID NODE.JS INSTALLATION!"
                + "PLEASE INSTALL NODE.JS FROM https://nodejs.org/  "
            )
            log_critical(errormessage)
            raise InvalidNodeJS(errormessage) from e

    def supports_color(self) -> bool:
        """
        Returns True if the running system's terminal supports color, and False
        otherwise.
        """
        plat = sys.platform
        supported_platform = plat != "Pocket PC" and (plat == "win32" or "ANSICON" in os.environ)
        # isatty is not always implemented, #6223.
        is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
        if "idlelib.run" in sys.modules:
            return False
        if self.notebook and not self.modified_stdout:
            return True
        return supported_platform and is_a_tty

    # Currently this uses process standard input & standard error pipes
    # to communicate with JS, but this can be turned to a socket later on
    # ^^ Looks like custom FDs don't work on Windows, so let's keep using STDIO.
    def read_output_line(self, out_line: str):
        """
        Process an output line from the JavaScript process, returning a list of JSON-decoded
        data objects. The line is decoded using UTF-8, then split into individual lines based
        on newline characters. Empty lines are skipped.


        In case of a ValueError during JSON decoding, the error and offending line are printed.

        Args:
            out_line (str): The output line to be processed.

        Returns:
            list: A list of JSON-decoded data objects derived from the input line.

        Raises:
            ValueError: If a line cannot be JSON-decoded.
        """
        inp = out_line.decode("utf-8")
        ret = []
        for line in inp.split("\n"):
            if not len(line):
                continue

            decoder = JSONRequestDecoder()
            try:
                d, decodeok = decoder.decode(line)
                if not decodeok:
                    log_error("[JSE] %s", line)
                    print("[JSE]", line)
                    continue
                if "error_severe" in d:
                    self.kill_error = d
                    raise FatalJavaScriptError("FATAL ERROR", d["error_severe"])
                log_debug("%s,%d,%s", "connection: [js -> py]", int(time.time() * 1000), line)
                ret.append(d)
            except json.JSONDecodeError as jde:
                print(jde, "[JSE]", line)
                log_error("Decode err: %s, [JSE] %s", jde, line)
            except ValueError as v_e:
                print(v_e, "[JSE]", line)
                log_error("%s, [JSE] %s", v_e, line)
            except FatalJavaScriptError as v_e:
                # print(v_e, "[JSE]", line)
                log_error("FATAL ERROR.  TERMINATING.")
                log_error(v_e)
                return ret
                # log_error()
        return ret

    def read_stderr(self) -> List[Dict]:
        """
        Read and process stderr messages from the node.js process, transforming them
        into Dictionaries via json.loads


        Returns:
            List[Dict]: Processed outbound_messages
        """
        out = []
        current_iter = 0
        still_full = True
        while self.stderr_lines.qsize() > 0 and still_full:
            try:
                toadd = self.stderr_lines.get_nowait()
                out.extend(self.read_output_line(toadd))
                current_iter += 1
            except Empty as e:
                log_warning("EventLoop, inbound Queue is empty.", exc_info=e)
                still_full = False
        return out

    # Write a message to a remote socket, in this case it's standard input
    # but it could be a websocket (slower) or other generic pipe.
    def writeAll(self, objs: List[Union[str, Any]]):
        """
        Transform objects into JSON strings, and write them to the node.js process.

        Args:
            objs (List[Union[str,Any]]): List of messages to be transformed and sent.
        """

        if self.endself or self.earlyterm:
            if self.kill_error:
                raise NodeTerminated(
                    "attempted to write while the node.js process was terminated with error state."
                )
            raise NodeTerminated("attempted to write while the node.js process was terminated.")
        for obj in objs:
            if type(obj) == str:
                j = obj + "\n"
            else:
                # if not type(obj) == dict:   pass
                j = json.dumps(obj) + "\n"
            log_debug("connection: %s,%d,%s", "[py -> js]", int(time.time() * 1000), j)
            encoded = j.encode()
            if not self.proc:
                self.sendQ.append(j.encode())
                continue
            try:
                self.proc.stdin.write(encoded)
                self.proc.stdin.flush()
            except (IOError, BrokenPipeError) as error:
                log_critical(encoded)
                log_critical(error, exc_info=True)
                self.stop()
                break

    # Reads from the socket, in this case it's standard error. Returns an array
    # of responses from the server.
    def readAll(self):
        """
        Read and process all messages from the node.js process.

        Returns:
            list: Processed messages.
        """
        ret = self.read_stderr()
        # self.stderr_lines.clear()
        return ret

    def startup_node_js(self):
        try:
            if os.name == "nt" and "idlelib.run" in sys.modules:
                log_debug("subprossess mode s")
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.directory_name + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                self.proc = subprocess.Popen(
                    [self.NODE_BIN, self.directory_name + "/js/bridge.js"],
                    stdin=subprocess.PIPE,
                    stdout=self.stdout,
                    stderr=subprocess.PIPE,
                )

        except subprocess.SubprocessError as err:
            log_critical(
                "--====--\t--====--\n\nBridge failed to spawn JS process!\n\nDo you have Node.js 16 or newer installed? Get it at https://nodejs.org/\n\n--====--\t--====--"
            )
            self.stop()
            raise err

    def recieve_stdio(self, line_read):
        """
        Receives standard input from a subprocess pipe and adds it to a
        queue for further processing. It also raises a 'stdin' event.

        Args:
            stderr(subprocess.PIPE): A subprocess pipe from which to read.
        """
        readline = line_read
        if readline:
            self.stderr_lines.put(readline)
            self.config.push_job("stdin")

    def com_io(self):
        """
        Handle communication with the node.js process.

        This method runs as an endless daemon thread, initializing a Node.js
        instance and managing the piping of input and output between Python and
        JavaScript. It launches a new daemon thread using `com_io` as the
        function.

        The node.js process is spawned with the specified Node.js binary and
        a bridge script, which facilitates communication.

        Raises:
            Exception: If there's an issue spawning the JS process or if any
            exceptions occur during communication.
        """

        print("Starting Node.JS connection...!")
        self.startup_node_js()
        for send in self.sendQ:
            self.proc.stdin.write(send)
        self.proc.stdin.flush()
        print("Connection established!")
        if self.status != 0:
            s1 = "a notebook" if self.status & 0b10 else ""
            s2 = ("a modified stdout") if self.status & 0b01 else ""
            out = f"This is {s1}{' and ' if self.status==3 else ''}{s2}."
            print(out)
            self.stdout_thread = threading.Thread(target=self.stdout_read, args=(), daemon=True)
            self.stdout_thread.start()

        while self.proc.poll() is None:
            self.recieve_stdio(self.proc.stderr.readline())

        # print("Termination condition", self.endself)
        if not self.endself:
            print("JS Process terminated on it's own.")
            self.earlyterm = True
            self.stop()
        else:
            print("JSProcess was terminated by parent.")

    def stdout_read(self):
        """
        Read and process standard output from the JavaScript process.
        This is only for Jupyter notebooks.
        """
        while self.proc.poll() is None:
            if not self.endself:
                # log_print('kill')
                output = self.proc.stdout.readline().decode("utf-8")
                if len(output) > 0:
                    print(output)

    def start(self):
        """
        Start the communication thread.
        """
        log_info("ConnectionClass.com_thread opened")
        # self.event_loop=self.config.get_event_loop()
        self.com_thread = threading.Thread(target=self.com_io, args=(), daemon=True)
        self.com_thread.start()

    def stop(self):
        """
        Terminate the node.js process.
        """
        if self.earlyterm:
            print("The JS Process terminated already.", self.is_alive())

            return
        self.endself = True
        time.sleep(2)
        log_print("terminating JS connection..")
        try:
            self.proc.terminate()
            print("Terminated JS Runtime.")

        except Exception as e:
            raise e
        self.config.reset_self()

    def is_alive(self):
        """
        Check if the node.js process is still running.

        Returns:
            bool: True if the process is running, False otherwise.
        """
        return self.proc.poll() is None
