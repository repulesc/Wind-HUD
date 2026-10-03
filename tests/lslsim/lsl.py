"""A small LSL interpreter, for testing scripts outside Second Life.

It runs the real generated scripts. LSL-PyOptimizer parses them (the same
strict parser `tools/build.py --check` uses) and its library supplies LSL's
exact operator rules and the pure ll* functions (llVecNorm, llList2Float...).
Everything that touches the world - physics, chat, timers, permissions - is
passed to a World object (see world.py), which answers like Second Life would.

Not supported (Wind does not use them): jump/labels and states other than
"default" with state_exit. Unknown world functions raise NotImplementedError
so a test notices.
"""
import os
import sys

LSLOPT = os.environ.get("LSLOPT", "/tmp/lslopt")
if not os.path.exists(os.path.join(LSLOPT, "main.py")):
    sys.exit("The tests need LSL-PyOptimizer: git clone https://github.com/Sei-Lisa/LSL-PyOptimizer " + LSLOPT)
sys.path.insert(0, LSLOPT)

from lslopt import lslcommon  # noqa: E402

lslcommon.DataPath = LSLOPT + os.sep
from lslopt.lslparse import parser  # noqa: E402
from lslopt import lslloadlib  # noqa: E402
from lslopt import lslbasefuncs as B  # noqa: E402
from lslopt.lslcommon import Key, Vector, Quaternion  # noqa: E402

LIB = lslloadlib.LoadLibrary()
EVENTS, CONSTANTS, FUNCTIONS = LIB

PY = {"integer": int, "float": float, "string": str, "key": Key,
      "vector": Vector, "rotation": Quaternion, "list": list}


def default(t):
    return {"integer": 0, "float": 0.0, "string": "", "key": Key(""),
            "vector": Vector((0.0, 0.0, 0.0)), "rotation": Quaternion((0.0, 0.0, 0.0, 1.0)),
            "list": []}[t]


def f32(x):
    return B.F32(float(x))


class LSLError(Exception):
    """A run-time error that stops the script in Second Life (Math Error, Stack-Heap...)."""


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class _Reset(Exception):
    pass


class _StateChange(Exception):
    def __init__(self, name):
        self.name = name


class Script:
    """One LSL script. `world` answers the ll* calls the library cannot."""

    def __init__(self, world, name, source, link=1):
        self.world = world
        self.name = name
        self.link = link
        self.tree, self.symtab = parser(LIB).parse(source, ("explicitcast",))
        self.functions = {}
        self.states = {}
        self.global_decls = []
        for node in self.tree:
            if node.nt == "DECL":
                self.global_decls.append(node)
            elif node.nt == "FNDEF":
                self.functions[node.name] = node
            elif node.nt == "STDEF":
                self.states[node.name] = {ev.name: ev for ev in node.ch}
        self.crashed = None
        self.queue = []
        self.reset_state()

    # ---- life cycle ---------------------------------------------------
    def reset_state(self):
        self.globals = {}
        for d in self.global_decls:
            self.globals[d.name] = self.eval(d.ch[0], None) if d.ch else default(d.t)
        self.state = "default"
        self.queue = []
        self.detected = []
        self.world.script_reset(self)

    def post(self, event, *args, detected=None):
        """Queue an event (Second Life keeps at most 64 per script)."""
        if self.crashed:
            return
        if event not in self.states[self.state]:
            return
        if event == "timer" and any(e[0] == "timer" for e in self.queue):
            return  # timer events do not stack up
        if len(self.queue) >= 64:
            self.world.note("queue full: %s dropped %s" % (self.name, event))
            return
        self.queue.append((event, args, detected))

    def run_one(self):
        """Runs the next queued event. Returns False if there was none."""
        if not self.queue or self.crashed:
            return False
        event, args, detected = self.queue.pop(0)
        handler = self.states[self.state].get(event)
        if handler is None:
            return True
        self.detected = detected or []
        frame = {}
        for (pname, ptype, value) in zip(handler.pnames, handler.ptypes, args):
            frame[(handler.pscope, pname)] = self.coerce(value, ptype)
        try:
            self.exec_stmt(handler.ch[0], frame)
        except _Return:
            pass
        except _Reset:
            self.reset_state()
            self.post("state_entry")
        except _StateChange as sc:
            raise NotImplementedError("state change to " + sc.name)
        except (B.ELSLMathError, LSLError) as e:
            self.crashed = "%s in %s: %r" % (type(e).__name__, event, e)
            self.world.note("SCRIPT CRASH " + self.name + ": " + self.crashed)
        self.detected = []
        return True

    @staticmethod
    def coerce(value, t):
        py = PY[t]
        if t == "key":
            return Key(value)
        if t == "float":
            return f32(value)
        if t == "integer":
            return int(value)
        if t == "string":
            return str(value)
        if t == "vector" and type(value) is not Vector:
            return Vector(f32(x) for x in value)
        if t == "rotation" and type(value) is not Quaternion:
            return Quaternion(f32(x) for x in value)
        return py(value) if type(value) is not py else value

    # ---- statements ---------------------------------------------------
    def exec_stmt(self, node, frame):
        nt = node.nt
        if nt == "{}":
            for c in node.ch:
                self.exec_stmt(c, frame)
        elif nt == "EXPR":
            if node.ch:
                self.eval(node.ch[0], frame)
        elif nt == "DECL":
            frame[(node.scope, node.name)] = self.eval(node.ch[0], frame) if node.ch else default(node.t)
        elif nt == "IF":
            if B.cond(self.eval(node.ch[0], frame)):
                self.exec_stmt(node.ch[1], frame)
            elif len(node.ch) > 2:
                self.exec_stmt(node.ch[2], frame)
        elif nt == "WHILE":
            while B.cond(self.eval(node.ch[0], frame)):
                self.exec_stmt(node.ch[1], frame)
        elif nt == "DO":
            while True:
                self.exec_stmt(node.ch[0], frame)
                if not B.cond(self.eval(node.ch[1], frame)):
                    break
        elif nt == "FOR":
            for e in node.ch[0].ch:
                self.eval(e, frame)
            while B.cond(self.eval(node.ch[1], frame)):
                self.exec_stmt(node.ch[3], frame)
                for e in node.ch[2].ch:
                    self.eval(e, frame)
        elif nt == "RETURN":
            raise _Return(self.eval(node.ch[0], frame) if node.ch else None)
        elif nt == "STSW":
            raise _StateChange(node.name)
        elif nt == ";":
            pass
        else:
            raise NotImplementedError("statement " + nt)

    # ---- expressions --------------------------------------------------
    def get(self, node, frame):
        if frame is not None and (node.scope, node.name) in frame:
            return frame[(node.scope, node.name)]
        return self.globals[node.name]

    def set(self, node, frame, value):
        if node.nt == "FLD":
            var = node.ch[0]
            old = self.get(var, frame)
            i = "xyzs".index(node.fld)
            parts = list(old)
            parts[i] = f32(value)
            value = type(old)(parts)
            node = var
        if frame is not None and (node.scope, node.name) in frame:
            frame[(node.scope, node.name)] = value
        elif node.name in self.globals:
            self.globals[node.name] = value
        else:
            frame[(node.scope, node.name)] = value

    def eval(self, node, frame):
        nt = node.nt
        if nt == "CONST":
            v = node.value
            if node.t == "list":
                return list(v)
            if node.t == "vector":
                return Vector(f32(x) for x in v)
            if node.t == "rotation":
                return Quaternion(f32(x) for x in v)
            if node.t == "float":
                return f32(v)
            return v
        if nt == "IDENT":
            return self.get(node, frame)
        if nt == "FLD":
            return self.get(node.ch[0], frame)["xyzs".index(node.fld)]
        if nt == "CAST":
            return B.typecast(self.eval(node.ch[0], frame), PY[node.t])
        if nt == "VECTOR":
            return Vector(f32(self.eval(c, frame)) for c in node.ch)
        if nt == "ROTATION":
            return Quaternion(f32(self.eval(c, frame)) for c in node.ch)
        if nt == "LIST":
            return [self.eval(c, frame) for c in node.ch]
        if nt == "PRIO":
            return self.eval(node.ch[0], frame)
        if nt == "FNCALL":
            # arguments are evaluated right to left, as in Second Life
            args = [None] * len(node.ch)
            for i in range(len(node.ch) - 1, -1, -1):
                args[i] = self.eval(node.ch[i], frame)
            return self.call(node.name, args)
        if nt == "NEG":
            return B.neg(self.eval(node.ch[0], frame))
        if nt == "!":
            return int(not B.cond(self.eval(node.ch[0], frame)))
        if nt == "~":
            return B.S32(~self.eval(node.ch[0], frame))
        if nt in ("=", "+=", "-=", "*=", "/=", "%="):
            value = self.eval(node.ch[1], frame)
            target = node.ch[0]
            if nt != "=":
                old = self.eval(target, frame)
                op = {"+=": B.add, "-=": B.sub, "*=": B.mul, "/=": B.div, "%=": B.mod}[nt]
                value = op(old, value)
                if node.t == "float":
                    value = f32(value)
            self.set(target, frame, value)
            return value
        if nt in ("++V", "--V", "V++", "V--"):
            target = node.ch[0]
            old = self.eval(target, frame)
            new = B.add(old, 1) if "++" in nt else B.sub(old, 1)
            if type(old) is float:
                new = f32(new)
            self.set(target, frame, new)
            return new if nt[0] in "+-" else old
        if nt == "EXPRLIST":
            v = None
            for c in node.ch:
                v = self.eval(c, frame)
            return v
        # binary operators: the right side is evaluated first, as in Second Life
        b = self.eval(node.ch[1], frame)
        a = self.eval(node.ch[0], frame)
        if nt == "+":
            return B.add(a, b)
        if nt == "-":
            return B.sub(a, b)
        if nt == "*":
            return B.mul(a, b)
        if nt == "/":
            return B.div(a, b)
        if nt == "%":
            return B.mod(a, b)
        if nt == "==":
            return B.compare(a, b, True)
        if nt == "!=":
            return B.compare(a, b, False)
        if nt == "<":
            return B.less(a, b)
        if nt == ">":
            return B.less(b, a)
        if nt == "<=":
            return 1 - B.less(b, a)
        if nt == ">=":
            return 1 - B.less(a, b)
        if nt == "&&":   # no short circuit in LSL: both sides were evaluated
            return int(B.cond(a) and B.cond(b))
        if nt == "||":
            return int(B.cond(a) or B.cond(b))
        if nt == "&":
            return B.S32(a & b)
        if nt == "|":
            return B.S32(a | b)
        if nt == "^":
            return B.S32(a ^ b)
        if nt == "<<":
            return B.S32(a << (b & 31))
        if nt == ">>":
            return B.S32(a >> (b & 31))
        raise NotImplementedError("expression " + nt)

    # ---- calls --------------------------------------------------------
    def call(self, name, args):
        fn = self.functions.get(name)
        if fn is not None:
            frame = {}
            for pname, ptype, value in zip(fn.pnames, fn.ptypes, args):
                frame[(fn.pscope, pname)] = value
            try:
                self.exec_stmt(fn.ch[0], frame)
            except _Return as r:
                return r.value
            return None
        if name == "llResetScript":
            raise _Reset()
        handler = getattr(self.world, name, None)
        if handler is not None:
            return handler(self, *args)
        lib = FUNCTIONS.get(name)
        if lib is not None and "Fn" in lib:
            return lib["Fn"](*args)
        raise NotImplementedError("world function " + name)
