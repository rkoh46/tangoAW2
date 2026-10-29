"""Reading a cartridge save's suspended games (`aw2dev save inspect`, docs/dev/save-inspect.md): AW2's block, the marks tangoAW2 puts after it (the pairs' tail, the stage, the two fronts) and a five-army
battle's record (crate::suspend, crate::five::saved_state), without running anything. The byte layout is the Rust side's; keep this in step with `suspend.rs`."""
import struct
import sys

from . import cfg

BLOCK_SIZE = 0xE28          # AW2's block as it writes it (crate::suspend::BLOCK_SIZE)
HASHED = 0xDAC              # the part of it the record's hash covers
TAIL_MARK = b"TAW2"         # +0xDAC: tangoAW2's own state after AW2's (rain fog, stun, the map table)
TAG_MARK = b"TAG2"          # +0xE28: the pairs (a hash of AW2's part follows)
FIVE_MARK = b"FIV5"         # the five-army record: mark, length u16, hash u32, then the state
FIVE_HEAD = 10
FRONTS_MARK = b"T2FT"       # the two-front battle's other front
STAGE_MARK = struct.pack("<I", 0x4547_5453)     # a mission saved on a later stage: mark, the stage number
SUSPEND_SLOTS = {2: "Campaign", 3: "War Room", 4: "Versus", 12: "BH Campaign", 14: "DS Campaign"}
PLAYER_SIZE, UNIT_SIZE = 0x3C, 12
P_COLOUR, P_CONTROL, P_CO, P_TEAM = 0x1A, 0x1B, 0x1D, 0x2A


def _saveimg():
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import saveimg
    return saveimg


def block_hash(block):
    """The hash the Rust side puts in the record and the pairs' tail: FNV-1a over AW2's part of the block."""
    h = 0x811C9DC5
    for b in block[:HASHED]:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def five_record(block, tag_len=None):
    """(offset, hash in the record, state bytes) of the five-army record in a slot's bytes, else None. The Rust reader looks at +0xE28 and after the pairs' tail; so do we, by scanning for the mark from +0xE28."""
    at = block.find(FIVE_MARK, BLOCK_SIZE)
    if at < 0 or len(block) < at + FIVE_HEAD:
        return None
    n = struct.unpack_from("<H", block, at + 4)[0]
    h = struct.unpack_from("<I", block, at + 6)[0]
    return at, h, bytes(block[at + FIVE_HEAD:at + FIVE_HEAD + n])


def five_state(state):
    """Decode crate::five::saved_state: FIVE_ON, army 5's switches, the Teams record, six player slots, the live units (id, 12 bytes)."""
    teams, plen = 0xE0, PLAYER_SIZE * 6
    five_on, switches = state[0], state[1:9]
    p = 9 + teams
    players = [state[p + PLAYER_SIZE * i:p + PLAYER_SIZE * (i + 1)] for i in range(6)]
    q = p + plen
    n = struct.unpack_from("<H", state, q)[0]
    units, q = [], q + 2
    for _ in range(n):
        units.append((state[q], bytes(state[q + 1:q + 13])))
        q += 13
    return {"five_on": five_on, "switches": bytes(switches), "players": players, "units": units, "ok": q == len(state)}


def describe_slot(tag, slot):
    """A suspended slot's report as a dict: sizes, AW2's part, the marks, the five-army record and whether it belongs to this block."""
    r = {"slot": tag, "name": SUSPEND_SLOTS.get(tag, f"slot {tag}"), "bytes": len(slot)}
    r["aw2"] = {"day": struct.unpack_from("<H", slot, 0)[0], "map": slot[0x140 + 2] if len(slot) > 0x142 else None, "hash": block_hash(slot)}
    r["tail"] = bool(len(slot) > HASHED + 4 and slot[HASHED:HASHED + 4] == TAIL_MARK)
    marks = {}
    for name, m in (("pairs", TAG_MARK), ("stage", STAGE_MARK), ("fronts", FRONTS_MARK)):
        if len(slot) > BLOCK_SIZE and slot[BLOCK_SIZE:BLOCK_SIZE + 4] == m:
            marks[name] = BLOCK_SIZE
    if marks.get("stage") is not None and len(slot) > BLOCK_SIZE + 4:
        marks["stage_number"] = slot[BLOCK_SIZE + 4]
    if "pairs" in marks:
        marks["pairs_match"] = struct.unpack_from("<I", slot, BLOCK_SIZE + 4)[0] == r["aw2"]["hash"]
    r["marks"] = marks
    rec = five_record(slot)
    if rec:
        at, h, state = rec
        f = five_state(state)
        counts = {}
        for uid, u in f["units"]:
            counts[uid // 51 + 1] = counts.get(uid // 51 + 1, 0) + 1
        r["five"] = {"at": at, "state_bytes": len(state), "hash_matches": h == r["aw2"]["hash"], "five_on": f["five_on"], "decoded_ok": f["ok"],
                     "armies": [{"army": i, "funds": struct.unpack_from("<I", p, 0)[0], "colour": p[P_COLOUR], "control": p[P_CONTROL], "co": p[P_CO], "team": p[P_TEAM], "units": counts.get(i, 0)}
                                for i, p in enumerate(f["players"]) if i >= 1 and (counts.get(i) or p[P_CONTROL])],
                     "units": len(f["units"])}
    return r


def inspect(path):
    """Every suspended slot of the save at `path`, described; plus the sector budget (sectors used and free)."""
    saveimg = _saveimg()
    im = saveimg.Image(path)
    out = {"path": path, "slots": [], "sectors": {}}
    d = im.directory()
    used = [t for t in d if t != 0xFF]
    out["sectors"] = {"used": len(used), "free": 16 - len(used), "by_slot": {t: used.count(t) for t in sorted(set(used))}}
    for tag in im.tags():
        if tag in SUSPEND_SLOTS:
            s = im.slot(tag)
            if s:
                out["slots"].append(describe_slot(tag, bytes(s)))
    return out


def render(rep):
    lines = [f"{rep['path']}: Flash sectors {rep['sectors']['used']} used, {rep['sectors']['free']} free (by slot {rep['sectors']['by_slot']})"]
    if not rep["slots"]:
        lines.append("  no suspended game")
    for s in rep["slots"]:
        a = s["aw2"]
        lines.append(f"  slot {s['slot']} ({s['name']}): {s['bytes']} bytes, AW2's block: day {a['day']}, map {a['map']}, hash {a['hash']:08x}; tangoAW2's tail {'yes' if s['tail'] else 'no'}")
        for k, v in s["marks"].items():
            lines.append(f"    mark {k}: {v}")
        f = s.get("five")
        if f:
            lines.append(f"    five-army record at +{f['at']:#x}: {f['state_bytes']} bytes, FIVE_ON {f['five_on']}, {f['units']} units, hash {'matches this block' if f['hash_matches'] else 'DOES NOT match (stale: never applied)'}"
                         + ("" if f["decoded_ok"] else ", LENGTH MISMATCH"))
            for ar in f["armies"]:
                lines.append(f"      army {ar['army']}: funds {ar['funds']}, colour {ar['colour']}, control {ar['control']}, CO {ar['co']}, team {ar['team']}, {ar['units']} units")
        else:
            lines.append("    no five-army record")
    return "\n".join(lines)
