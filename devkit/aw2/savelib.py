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
    # (the stage's and the two-front mark stand right after the block, or after the pairs' tail when the block carries one: crate::suspend::MARK_AT; older saves have them over the tail)
    for name, m in (("stage", STAGE_MARK), ("fronts", FRONTS_MARK)):
        if name not in marks:
            at = slot.find(m, BLOCK_SIZE + 4)
            if at > 0:
                marks[name] = at
    if marks.get("stage") is not None and len(slot) > marks["stage"] + 4:
        marks["stage_number"] = slot[marks["stage"] + 4]
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


# --- the COs' EXP (`aw2dev save exp`) ---------------------------------------------------------------------------------------------------------------------
CO_NAMES = {0: "Nell", 1: "Andy", 2: "Max", 3: "Sami", 4: "Olaf", 5: "Grit", 6: "Colin", 7: "Kanbei", 8: "Sonja", 9: "Sensei", 10: "Eagle", 11: "Drake", 12: "Jess", 13: "Hachi", 14: "Sturm",
            15: "Flak", 16: "Lash", 17: "Adder", 18: "Hawke", 72: "Jake", 73: "Rachel", 74: "Sasha", 75: "Grimm", 76: "Javier", 77: "Jugger", 78: "Koal", 79: "Kindle", 80: "Von Bolt",
            81: "Clone Andy", 82: "Crumb", 86: "Tabitha", 87: "Lili", 88: "Caulder", 92: "Asuka", 93: "Aria"}
EXTRA_COS = (86, 87, 88, 92, 93)       # crate::co_skills::EXTRA_COS: slots 30..34
SKILLS_AT = 0x20 + 8 * 32               # slot 15's payload: progress (0x20), the DS Campaign's records (8 x 32), then "SKL1" and 30 x 32 bytes
CO_LEN, FIRST_COS, HISTORY_LEN, EXTRA_LEN = 32, 30, 0x1A4, 4 + 32 * 7     # (the block has 7 records: two spare)
EXTRA_AT = SKILLS_AT + 4 + CO_LEN * FIRST_COS + HISTORY_LEN      # "SKX1" and 5 x 32 bytes, after the History


def co_slot(co):
    co = {89: 87, 90: 88}.get(co, co)
    if 0 <= co <= 18:
        return co
    if 72 <= co <= 82:
        return 19 + co - 72
    return FIRST_COS + EXTRA_COS.index(co)       # (ValueError: no slot)


def co_offset(co):
    """Where CO `co`'s 32-byte record (EXP u32, then Campaign, Survival, War Room, four Versus sets of 4 skill ids) is in slot 15's payload."""
    k = co_slot(co)
    return SKILLS_AT + 4 + CO_LEN * k if k < FIRST_COS else EXTRA_AT + 4 + CO_LEN * (k - FIRST_COS)


def exp_table(path):
    """[(CO id, name, EXP, rank, sets)] for every CO with a slot, from slot 15 of the save at `path` (a save with no record: every CO at 0)."""
    im = _saveimg().Image(path)
    rec = im.slot(15) or b""
    ids = [c for c in range(19)] + list(range(72, 83)) + list(EXTRA_COS)
    out = []
    for co in ids:
        o = co_offset(co)
        ok = len(rec) >= o + CO_LEN and (co_slot(co) < FIRST_COS and rec[SKILLS_AT:SKILLS_AT + 4] == b"SKL1" or co_slot(co) >= FIRST_COS and rec[EXTRA_AT:EXTRA_AT + 4] == b"SKX1")
        b = rec[o:o + CO_LEN] if ok else bytes(CO_LEN)
        exp = struct.unpack_from("<I", b, 0)[0]
        out.append((co, CO_NAMES.get(co, str(co)), exp, min(exp // 1000, 100), [list(b[4 + 4 * i:8 + 4 * i]) for i in range(7)]))
    return out


def set_exp(path, out, changes):
    """The save at `path` with each CO's EXP in `changes` ({CO id: EXP}) set in slot 15's record (written to `out`). A record without the later COs' block gets one; a save with no record is refused."""
    saveimg = _saveimg()

    def edit(p):
        b = bytearray(p)
        if len(b) < SKILLS_AT + 4 or b[SKILLS_AT:SKILLS_AT + 4] != b"SKL1":
            raise ValueError("the save has no skill record yet (win a battle or set a skill in the game first)")
        if co_slot(max(changes, key=co_slot)) >= FIRST_COS and bytes(b[EXTRA_AT:EXTRA_AT + 4]) != b"SKX1":
            b[EXTRA_AT:EXTRA_AT] = b"SKX1" + bytes(EXTRA_LEN - 4)
        for co, v in changes.items():
            struct.pack_into("<I", b, co_offset(co), min(v, 100_000))
        return bytes(b)
    return saveimg.rewrite_slot(path, out, 15, edit)
