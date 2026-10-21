"""A tiny stdlib WebSocket (RFC 6455) client and frame helpers, enough for the signalling mock and the endpoint probes."""
import base64, os, socket, ssl, struct
from urllib.parse import urlparse


def encode(op, payload=b"", mask=False):
    b0 = 0x80 | op
    n = len(payload)
    hdr = bytes([b0])
    m = 0x80 if mask else 0
    if n < 126:
        hdr += bytes([m | n])
    elif n < 65536:
        hdr += bytes([m | 126]) + struct.pack(">H", n)
    else:
        hdr += bytes([m | 127]) + struct.pack(">Q", n)
    if mask:
        key = os.urandom(4)
        payload = bytes(c ^ key[i % 4] for i, c in enumerate(payload))
        return hdr + key + payload
    return hdr + payload


def _recvn(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            raise EOFError
        buf += c
    return buf


def read_frame(sock):
    """-> (opcode, payload); fragmented messages are joined; ping/pong/close are returned as they come."""
    data, op0 = b"", None
    while True:
        h = _recvn(sock, 2)
        fin, op = h[0] & 0x80, h[0] & 0x0F
        masked, n = h[1] & 0x80, h[1] & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recvn(sock, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recvn(sock, 8))[0]
        key = _recvn(sock, 4) if masked else None
        p = _recvn(sock, n) if n else b""
        if key:
            p = bytes(c ^ key[i % 4] for i, c in enumerate(p))
        if op >= 8:
            return op, p
        if op0 is None:
            op0 = op
        data += p
        if fin:
            return op0, data


def connect(url, timeout=6.0):
    """Open a client websocket. Returns (sock, status_line, response_body_or_empty). On a non-101 answer sock is None."""
    u = urlparse(url)
    port = u.port or (443 if u.scheme == "wss" else 80)
    s = socket.create_connection((u.hostname, port), timeout=timeout)
    if u.scheme == "wss":
        s = ssl.create_default_context().wrap_socket(s, server_hostname=u.hostname)
    key = base64.b64encode(os.urandom(16)).decode()
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    s.sendall((f"GET {path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               "Sec-WebSocket-Version: 13\r\nUser-Agent: aw2dev-probe\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        c = s.recv(4096)
        if not c:
            break
        buf += c
    head, _, rest = buf.partition(b"\r\n\r\n")
    status = head.split(b"\r\n")[0].decode(errors="ignore")
    if " 101 " in status + " ":
        return s, status, rest
    body = rest
    try:
        s.settimeout(1.0)
        body += s.recv(4096)
    except Exception:
        pass
    s.close()
    return None, status, body
