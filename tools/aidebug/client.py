#!/usr/bin/env python3
"""Client for tangoAW2's AI debug channel (see README.md).

Library:
    from client import AiDebug
    d = AiDebug.connect("127.0.0.1:5555")        # or a socket path; token from TANGOAW2_AI_DEBUG_TOKEN
    d.wait_until({"phase": "battle"}, timeout=60)
    d.press("A")
    print(d.state()["armies"])

CLI:  aidebug [--addr HOST:PORT|SOCKET] state [--fields a,b] [--path units.0]
      aidebug press A [FRAMES]     | hold KEYS | release [KEYS] | goto X Y | type TEXT
      aidebug wait-until phase=battle active_army=2 [day>=3] [--timeout 60]
      aidebug shot out.png [--raw]  | peek ADDR [LEN] | poke ADDR HEX | hash | procs | log [N]
      aidebug ckpt save NAME | ckpt load NAME | ckpt list
      aidebug sub [kinds...]        | events [AFTER] | net | inject latency 80 10 2 | inject drop 5 | inject freeze 3 | inject clear
      aidebug start-offline | hello
The address defaults to $TANGOAW2_AI_DEBUG_ADDR (the app prints `AI_DEBUG_LISTENING <addr>` when it starts).
"""
import base64
import json
import os
import re
import socket
import sys
import time


class AiDebugError(Exception):
    pass


class AiDebug:
    def __init__(self, sock, token=None):
        self.sock = sock
        self.f = sock.makefile("rwb", buffering=0)
        self.buf = b""
        self.next_id = 1
        self.pending_events = []
        if token is None:
            token = os.environ.get("TANGOAW2_AI_DEBUG_TOKEN")
        if token:
            self.call("auth", token=token)

    @classmethod
    def connect(cls, addr=None, token=None, timeout=60.0):
        addr = addr or os.environ.get("TANGOAW2_AI_DEBUG_ADDR")
        if not addr:
            raise AiDebugError("no address: pass one or set TANGOAW2_AI_DEBUG_ADDR")
        if addr.startswith("unix:"):
            addr = addr[5:]
        if re.fullmatch(r"(\d+\.\d+\.\d+\.\d+:)?\d+", addr):
            host, _, port = addr.rpartition(":")
            s = socket.create_connection((host or "127.0.0.1", int(port)), timeout=10)
        else:
            s = socket.socket(socket.AF_UNIX)
            s.connect(addr)
        s.settimeout(timeout)
        return cls(s, token)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _readline(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise AiDebugError("connection closed")
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        return json.loads(line)

    def call(self, cmd, **args):
        """Sends a command, returns the answer (a dict) or raises AiDebugError. Event lines that arrive meanwhile are kept."""
        rid = self.next_id
        self.next_id += 1
        args = {k: v for k, v in args.items() if v is not None}
        self.sock.sendall((json.dumps({"id": rid, "cmd": cmd, **args}) + "\n").encode())
        while True:
            m = self._readline()
            if "event" in m:
                self.pending_events.append(m)
                continue
            if m.get("id") == rid or "id" not in m:
                if not m.get("ok"):
                    raise AiDebugError(m.get("error", "failed"))
                return m

    # --- reading -----------------------------------------------------------------------------------------------
    def hello(self):
        return self.call("hello")

    def state(self, fields=None, fresh=False):
        return self.call("state", fields=fields, fresh=fresh or None)["state"]

    def net(self):
        return self.call("net")

    # --- acting ------------------------------------------------------------------------------------------------
    def press(self, keys, frames=8, seat=None, wait=True):
        return self.call("press", keys=keys, frames=frames, seat=seat, wait=wait)

    def hold(self, keys):
        return self.call("hold", keys=keys)

    def release(self, keys=None):
        return self.call("release", keys=keys)

    def type(self, text):
        return self.call("type", text=text)

    def goto(self, x, y, timeout=30):
        return self.call("goto", x=x, y=y, timeout=timeout)

    def wait_until(self, cond, timeout=30):
        """cond: a dict, e.g. {"phase": "battle", "active_army": 2} or {"day": {"gte": 3}} (see README)."""
        old = self.sock.gettimeout()
        self.sock.settimeout(max(old or 0, timeout + 15))
        try:
            return self.call("wait_until", cond=cond, timeout=timeout)
        finally:
            self.sock.settimeout(old)

    def press_until(self, keys, cond, timeout=20, frames=8, gap=0.6):
        """Presses `keys` now and then until the state matches `cond` (a screen that ignores the first press)."""
        end = time.time() + timeout
        while time.time() < end:
            try:
                return self.wait_until(cond, 0.01)
            except AiDebugError:
                pass
            self.press(keys, frames)
            try:
                return self.wait_until(cond, gap)
            except AiDebugError:
                pass
        raise AiDebugError(f"gave up pressing {keys} until {cond}")

    def start_offline(self):
        return self.call("start_offline")

    # --- inspecting --------------------------------------------------------------------------------------------
    def screenshot(self, path=None, raw=False):
        r = self.call("screenshot", raw=raw or None)
        png = base64.b64decode(r.pop("png_b64"))
        if path:
            with open(path, "wb") as f:
                f.write(png)
            r["path"] = path
        r["png"] = png
        return r

    def peek(self, addr, length=16):
        return self.call("peek", addr=addr, len=length)

    def poke(self, addr, hexbytes, force_offline=None):
        return self.call("poke", addr=addr, hex=hexbytes, force_offline=force_offline)

    def hash(self):
        return self.call("hash")

    def procs(self):
        return self.call("proc_list")

    def log_tail(self, lines=50):
        return self.call("log_tail", lines=lines)["lines"]

    def checkpoint_save(self, name):
        return self.call("checkpoint_save", name=name)

    def checkpoint_load(self, name):
        return self.call("checkpoint_load", name=name)

    def checkpoint_list(self):
        return self.call("checkpoint_list")

    def inject(self, op, **kw):
        return self.call("inject", op=op, **kw)

    # --- events ------------------------------------------------------------------------------------------------
    def subscribe(self, kinds=None, after=None):
        return self.call("subscribe", events=kinds, after=after)

    def events(self, timeout=None):
        """Yields event dicts (after subscribe) until the connection closes or `timeout` seconds pass with none."""
        for e in self.pending_events:
            yield e
        self.pending_events = []
        self.sock.settimeout(timeout)
        try:
            while True:
                m = self._readline()
                if "event" in m:
                    yield m
        except (socket.timeout, AiDebugError):
            return


def parse_cond(items):
    """`phase=battle active_army=2 day>=3 map.name~Ball` -> a condition dict."""
    ops = [(">=", "gte"), ("<=", "lte"), ("!=", "ne"), (">", "gt"), ("<", "lt"), ("~", "contains"), ("=", None)]
    cond = {}
    for it in items:
        for sym, op in ops:
            if sym in it:
                k, v = it.split(sym, 1)
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
                if op is None:
                    cond[k] = v
                else:
                    cond.setdefault(k, {})
                    if not isinstance(cond[k], dict):
                        cond[k] = {"eq": cond[k]}
                    cond[k][op] = v
                break
        else:
            raise AiDebugError(f"cannot read condition {it!r} (use key=value, key>=n, key~text)")
    return cond


def _dig(v, path):
    for p in path.split("."):
        v = v[int(p)] if isinstance(v, list) else v[p]
    return v


def main(argv):
    addr = None
    args = list(argv)
    if args[:1] == ["--addr"]:
        addr, args = args[1], args[2:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = args[0], args[1:]
    d = AiDebug.connect(addr)
    out = None
    if cmd == "state":
        fields = path = None
        while rest:
            o = rest.pop(0)
            if o == "--fields":
                fields = rest.pop(0).split(",")
            elif o == "--path":
                path = rest.pop(0)
        out = d.state(fields)
        if path:
            out = _dig(out, path)
    elif cmd == "press":
        out = d.press(rest[0], int(rest[1]) if len(rest) > 1 else 8)
    elif cmd in ("hold", "release"):
        out = d.hold(rest[0]) if cmd == "hold" else d.release(rest[0] if rest else None)
    elif cmd == "goto":
        out = d.goto(int(rest[0]), int(rest[1]))
    elif cmd == "type":
        out = d.type(" ".join(rest))
    elif cmd in ("wait-until", "wait_until"):
        timeout = 30.0
        if "--timeout" in rest:
            i = rest.index("--timeout")
            timeout = float(rest[i + 1])
            del rest[i : i + 2]
        out = d.wait_until(parse_cond(rest), timeout)
    elif cmd in ("shot", "screenshot"):
        raw = "--raw" in rest
        rest = [r for r in rest if r != "--raw"]
        out = d.screenshot(rest[0] if rest else "shot.png", raw)
        out.pop("png")
    elif cmd == "peek":
        out = d.peek(rest[0], int(rest[1], 0) if len(rest) > 1 else 16)
    elif cmd == "poke":
        out = d.poke(rest[0], rest[1], True if "--force-offline" in rest else None)
    elif cmd == "hash":
        out = d.hash()
    elif cmd in ("procs", "proc_list"):
        out = d.procs()
    elif cmd == "log":
        print("\n".join(d.log_tail(int(rest[0]) if rest else 50)))
        return 0
    elif cmd in ("ckpt", "checkpoint"):
        sub = rest[0]
        out = {"save": lambda: d.checkpoint_save(rest[1]), "load": lambda: d.checkpoint_load(rest[1]), "list": d.checkpoint_list}[sub]()
    elif cmd in ("sub", "subscribe"):
        d.subscribe(rest or None)
        try:
            for e in d.events():
                print(json.dumps(e), flush=True)
        except KeyboardInterrupt:
            pass
        return 0
    elif cmd == "events":
        out = d.call("events", after=int(rest[0]) if rest else 0)
    elif cmd == "net":
        out = d.net()
    elif cmd == "inject":
        op = rest[0]
        kw = {}
        if op == "latency":
            kw = dict(zip(("latency_ms", "jitter_ms", "loss_pct"), (float(x) for x in rest[1:4])))
        elif op in ("drop", "freeze"):
            kw = {"seconds": float(rest[1])}
        out = d.inject(op, **kw)
    elif cmd in ("start-offline", "start_offline"):
        out = d.start_offline()
    elif cmd == "hello":
        out = d.hello()
    else:
        print(f"unknown command {cmd}\n{__doc__}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except AiDebugError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
