"""The public services the app leans on, read from tango-net/src/endpoints.rs so this list never drifts, and the env that keeps tests off them."""
import re
from . import cfg


def _const(name, text):
    m = re.search(r"pub const %s: &\[&str\] = &\[(.*?)\];" % name, text, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def load():
    t = (cfg.REPO / "tango-net" / "src" / "endpoints.rs").read_text()
    nums = {}
    for k in ("NOSTR_MAX_BROWSE", "SIGNALING_TIMEOUT_SECS", "STUN_PROBES_PER_CALL", "CHECK_FRESH_SECS", "BACKOFF_FIRST_SECS", "BACKOFF_CAP_SECS", "LONG_BLOCK_SECS"):
        m = re.search(r"pub const %s: \w+ = (\d+);" % k, t)
        nums[k] = int(m.group(1)) if m else None
    return {"signaling": _const("SIGNALING", t), "stun": _const("STUN", t), "nostr": _const("NOSTR", t), **nums}


def block_env():
    """TANGOAW2_BLOCK_ENDPOINTS value that makes the app fail every public endpoint at once (no traffic leaves the machine), plus a dead lobby relay."""
    e = load()
    hosts = [h.split(":")[0] for h in e["stun"]] + [re.sub(r"^wss?://", "", u) for u in e["nostr"]] + [re.sub(r"^wss?://", "", u) for u in e["signaling"]]
    return {"TANGOAW2_BLOCK_ENDPOINTS": ",".join(hosts), "TANGOAW2_LOBBY_RELAYS": "ws://127.0.0.1:9"}
