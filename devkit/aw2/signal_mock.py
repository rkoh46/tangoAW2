"""A local stand-in for the Tango signalling server (vendor/tango-signaling/src/proto/signaling.proto), so network tests never touch the
public matchmaking server. It speaks the protocol the client expects:

  connect ws://127.0.0.1:PORT/?session_id=ID  (no session_id -> HTTP 400 with Abort REASON_MISSING_SESSION_ID)
  server -> client   Hello{ice_servers}        (none: loopback host candidates connect; no STUN/TURN)
  client -> server   Start{protocol_version, offer_sdp, connection_id}
  the first Start of a session is the impolite side; when a second arrives the server sends it Offer{first's sdp}; its Answer goes back to
  the first. IceCandidate packets are relayed to the other peer; Ping is echoed.

NOT emulated: TURN (relay-only needs the real server's Cloudflare credentials), NAT types, matchmaking beyond pairing by session id.
Run alone:  python3 -m aw2.signal_mock --port 8765      Used by `aw2dev net sim|matrix|soak` (local signalling is their default).
"""
import argparse, base64, hashlib, socket, struct, sys, threading
from urllib.parse import parse_qs, urlparse
from . import wsmini

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ---- the little protobuf we need ----
def _varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _fields(buf):
    i, out = 0, []
    while i < len(buf):
        key = 0
        shift = 0
        while True:
            b = buf[i]; i += 1
            key |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                break
        f, wt = key >> 3, key & 7
        if wt == 0:
            v = 0; shift = 0
            while True:
                b = buf[i]; i += 1
                v |= (b & 0x7F) << shift
                shift += 7
                if not b & 0x80:
                    break
        elif wt == 2:
            n = 0; shift = 0
            while True:
                b = buf[i]; i += 1
                n |= (b & 0x7F) << shift
                shift += 7
                if not b & 0x80:
                    break
            v = buf[i:i + n]; i += n
        else:
            raise ValueError("wire type")
        out.append((f, v))
    return out


def _ld(field, payload):
    return _varint(field << 3 | 2) + _varint(len(payload)) + payload


HELLO = _ld(4, b"")                 # Packet{hello: Hello{}} : no ICE servers
PING = _ld(6, b"")
F_START, F_OFFER, F_ANSWER, F_ABORT, F_PING, F_ICE = 1, 2, 3, 5, 6, 7


class Peer:
    def __init__(self, sock):
        self.sock, self.lock, self.start, self.partner = sock, threading.Lock(), None, None

    def send(self, data):
        with self.lock:
            self.sock.sendall(wsmini.encode(2, data))


class Server:
    def __init__(self, port=0, log=None):
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", port))
        self.srv.listen(32)
        self.port = self.srv.getsockname()[1]
        self.sessions = {}     # session id -> peers waiting for a partner
        self.mu = threading.Lock()
        self.log = log or (lambda *a: None)
        self.pairs = 0

    def serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._conn, args=(c,), daemon=True).start()

    def start_thread(self):
        threading.Thread(target=self.serve, daemon=True).start()
        return f"ws://127.0.0.1:{self.port}"

    def _conn(self, c):
        try:
            buf = b""
            while b"\r\n\r\n" not in buf:
                d = c.recv(4096)
                if not d:
                    return
                buf += d
            req = buf.split(b"\r\n")[0].decode()
            hdrs = {l.split(b":", 1)[0].strip().lower().decode(): l.split(b":", 1)[1].strip().decode() for l in buf.split(b"\r\n\r\n")[0].split(b"\r\n")[1:] if b":" in l}
            q = parse_qs(urlparse(req.split(" ")[1]).query)
            sid = (q.get("session_id") or [""])[0]
            if not sid:
                body = b"\x08\x03"   # Abort{REASON_MISSING_SESSION_ID}
                c.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
                return
            acc = base64.b64encode(hashlib.sha1((hdrs.get("sec-websocket-key", "") + GUID).encode()).digest()).decode()
            c.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {acc}\r\n\r\n".encode())
            peer = Peer(c)
            peer.send(HELLO)
            self.log("connect", sid)
            while True:
                op, data = wsmini.read_frame(c)
                if op == 8:
                    return
                if op == 9:
                    with peer.lock:
                        c.sendall(wsmini.encode(10, data))
                    continue
                if op not in (1, 2):
                    continue
                self._packet(sid, peer, data)
        except (EOFError, OSError, ValueError, IndexError):
            pass
        finally:
            self._drop(c)

    def _drop(self, c):
        with self.mu:
            for sid, lst in list(self.sessions.items()):
                self.sessions[sid] = [p for p in lst if p.sock is not c]
        try:
            c.close()
        except OSError:
            pass

    def _packet(self, sid, peer, data):
        f = dict(_fields(data))
        if F_PING in f:
            peer.send(PING)
        elif F_START in f:
            start = dict(_fields(f[F_START]))
            sdp = start.get(2, b"")
            with self.mu:
                waiting = [p for p in self.sessions.get(sid, []) if p.partner is None and p is not peer and p.start is not None]
                peer.start = sdp
                if waiting:
                    first = waiting[0]
                    first.partner, peer.partner = peer, first
                    self.pairs += 1
                    self.log("pair", sid)
                    peer.send(_ld(F_OFFER, _ld(1, first.start)))    # the later peer is the polite side
                else:
                    self.sessions.setdefault(sid, []).append(peer)
        elif F_ANSWER in f or F_ICE in f:
            if peer.partner is not None:
                peer.partner.send(data)   # Answer -> the impolite peer; IceCandidate -> the other side
        elif F_OFFER in f:
            if peer.partner is not None:
                peer.partner.send(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    a = ap.parse_args()
    s = Server(a.port, log=lambda *x: print("signal-mock:", *x, flush=True))
    print("signal-mock listening on", s.start_thread(), flush=True)
    threading.Event().wait()


if __name__ == "__main__":
    main()
