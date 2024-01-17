""" 
Module that contains a special Encoder variant to assist
with the serialization of PCall requests.

"""
from json import JSONEncoder, JSONDecoder

from javascriptasync.core.jslogging import log_warning
from .errorsjs import InvalidNodeOp
from typing import Any, Tuple


# There's no reason to monkey patch like this if the only class
# with a custom __json__ method is Proxy.
# The only thing Proxy's to_json method even returns is it's FFID,
# and that's handled by CustomJSONCountEncoder.
#
# There's no point, and monkey patching is a nightmare
# for code maintenance.

# def _default(self, obj):
#     return getattr(obj.__class__, "__json__", _default.default)(obj)
# _default.default = JSONEncoder.default  # Save unmodified default.
# JSONEncoder.default = _default  # Replace it.

# You're better off just using a custom Decoder.


class JSONRequestDecoder(JSONDecoder):
    def decode(self, s: str):
        """Return the Python representation of ``s`` (a ``str`` instance
        containing a JSON document).

        """
        decoded_obj = super().decode(s)
        if isinstance(decoded_obj, dict) and "r" in decoded_obj:
            return decoded_obj, True
        return s, False


class CustomJSONCountEncoder(JSONEncoder):
    """
    A custom JSON Encoder used by the Executor's Pcall methods, which
    stores a count of how many times default was triggered and
    adds it to the serialized dictionary.

    Attributes:
        append_p (bool): Determines whether to append the value of ctr.
        ctr (int): Counter value.
        problem (int): Issues found when encoding.
        expect_reply (bool): Defines if a reply is expected.
        wanted (dict) : Holds wanted objects.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes the CustomJSONCountDirect object.

        Args:
            append_p (bool): Determines whether to append the value of ctr.
        """
        if "append_p" not in kwargs:
            self.append_p = True
        else:
            self.append_p = kwargs.pop("append_p")
        super().__init__(*args, **kwargs)
        self.ctr = 0
        self.problem = 0
        self.expect_reply = False
        self.wanted = {}

    def get_ctr(self):
        """
        Returns the current counter value.

        Returns:
            int: Current counter value.
        """
        return self.ctr

    def get_reply(self):
        """
        Returns the 'expect_reply' attribute.

        Returns:
            bool: Current value of 'expect_reply'.
        """
        return self.expect_reply

    def get_wanted(self):
        """
        Returns a dictionary containing 'p', 'exp_reply' and 'wanted'.

        Returns:
            dict: Dictionary containing 'p', 'exp_reply' and 'wanted'.
        """
        return {"p": self.ctr, "exp_reply": self.expect_reply, "wanted": self.wanted}

    def default(self, o):
        """
        Increments the counter and checks if object has 'ffid' attribute.
        Will also assign any non-primitive objects to the self.wanted dictionary.

        Args:
            o (object): The object to be checked.

        Returns:
            dict: If 'ffid' exists returns ffid, else returns 'r', 'ffid' and updates wanted dict.
        """
        self.ctr += 1
        pro = o
        if hasattr(pro, "node_op"):
            if pro.node_op:
                log_warning(f"passed in arg {pro} is an unprocessed chain! ")
                self.ctr -= 1
                self.problem += 1
                return {"no": "UNPROCESSED CHAIN."}
        if hasattr(pro, "ffid"):
            return {"ffid": pro.ffid}
        else:
            self.expect_reply = True
            self.wanted[self.ctr] = pro
            return {"r": self.ctr, "ffid": ""}

    def encode_refs(self, o: Any, args: Tuple[Any]) -> str:
        """
        Encodes a request while getting direct references to the
        arguments defined within a local stack frame.

        Args:
            o (Any): Any object.
            args (Tuple[Any]): Tuple of any objects.

        Returns:
            str: Encoded result.
        """
        _block, _locals = args
        o["args"] = [args[0], {}]
        flocals = o["args"][1]
        for k in _locals:
            v = _locals[k]
            # or (v is True) or (v is False)
            if isinstance(v, (int, float, bool)) or (v is None):
                flocals[k] = v
            else:
                flocals[k] = self.default(v)
        payload = self.encode(o)
        return payload

    def encode(self, o: Any) -> str:
        """
        Encodes an object.

        Args:
            o (Any): Any object.

        Returns:
            str: Encoded result.
        """
        chunks = super().iterencode(o)

        if not isinstance(chunks, (list, tuple)):
            chunks = list(chunks)
        # cl = len(chunks) - 1
        chunk_append = []
        if self.ctr <= 0 and self.problem >= 1:
            raise InvalidNodeOp("please check your code...")
        doappend = self.append_p
        for c in chunks:
            chunk_append.append(c)
            if doappend:
                if c == "{":
                    extendwith = ['"p"', ":", str(self.ctr), ","]
                    chunk_append.extend(extendwith)
                    doappend = False

        return "".join(chunk_append)
