"""Sonja stays completely untouched by Asuka (and by any later CO): everything of hers that this console can show or compute is written to `sonja.json` in this test's output folder, and
`aw2dev co verify sonja` runs the test with this build and with the v0.8.7 build (AW2TEST_RUNNER_DIR) and fails on any difference. What is observed: her CO table row (stars, luck, abilities, power words,
music, texts' ids), her presentation row's pictures (the bytes each picture word points to), her HUD face, her texts (name, pages, power names, quotes), her order among AW2's COs in the Teams list, the
numbers of real battles (base damage, defence, luck range and the records of both sides in her three power levels, as attacker and as defender), her vision in fog, her Tag page and Tag Powers' numbers, and the
frames of her screens (the battle's first frame, her CO page, the CO Power's and Super Power's cut-ins). Nothing from the games is stored: the file holds hashes and numbers."""

import hashlib
import json
import os

from aw2test import damage, rom as romlib, tag
from aw2test.harness import test
from tests.test_fog import seen
from tests.test_tag import tag_battle, tag_page_of
from tests.test_co_music import SONG_TABLE_POOL, header_of

SONJA = 7
TEXT_TABLE = 0x08610A38


def h(b):
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def read_text(g, tid):
    at = g.e.u32(TEXT_TABLE + 4 * tid)
    if not (0x08000000 <= at < 0x0A000000):
        return None
    out = bytearray()
    while len(out) < 600:
        c = g.e.u8(at + len(out))
        if c == 0:
            break
        out.append(c)
    return bytes(out).hex()


def frame_hash(ctx, g, name):
    p = ctx.shot(g, name)
    return h(open(p, "rb").read())


@test(modes=("ds",))
def sonja_untouched(ctx):
    obs = {}
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 3, 3).unit(2, "infantry", 25, 15)
    g = ctx.start(m, ["sonja", "andy"])
    e = g.e
    row = e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * SONJA
    raw = e.read(row, romlib.CO_RECORD)
    obs["co_row"] = h(raw)
    obs["co_row_fields"] = {"stars": [e.u32(row + 0x0C), e.u32(row + 0x10)], "music": e.u16(row + 4),
                            "modes": [[e.u16(row + 0x38 + 0x44 * k + o) for o in (0x0C, 0x0E, 0x10, 0x12, 0x14, 0x16)] + [e.u32(row + 0x38 + 0x44 * k + 4), e.u32(row + 0x38 + 0x44 * k + 8)] for k in range(3)]}
    # her music, and Sturm's: Asuka's theme quotes both from the ROM at run time and must only read them. Everything of each song as the console holds it: the song table's row, the header, the
    # voice group's 128 entries and every track's bytes (the stretch from the first track to the end of the header)
    table = e.u32(SONG_TABLE_POOL)
    music = {}
    for name, sid in (("sonja", e.u16(row + 4)), ("sturm", 219)):
        hd = header_of(e, sid)
        n = e.u8(hd)
        ptrs = [e.u32(hd + 8 + 4 * k) for k in range(n)]
        lo = min(ptrs + [hd])
        hi = max(ptrs + [hd]) + 0x1000 if hd < max(ptrs) else hd + 8 + 4 * n
        group = e.u32(hd + 4)
        music[name] = {"song": sid, "table_row": h(e.read(table + 8 * sid, 8)), "header": h(e.read(hd, 8 + 4 * n)),
                       "voices": h(e.read(group, 12 * 128)), "tracks": h(e.read(lo, hi - lo)),
                       "track_count": n, "track_offsets": [p - lo for p in ptrs], "header_offset": hd - lo}
    obs["music"] = music
    # presentation row: the words and the bytes they point to
    pres = e.u32(0x08043AF8)
    prow = pres + 0x44 * SONJA
    words = [e.u32(prow + 4 * k) for k in range(0x44 // 4)]
    obs["presentation_row"] = h(e.read(prow, 0x44))
    pics = {}
    for k, w in enumerate(words[:7]):
        if 0x08000000 <= w < 0x0A000000:
            pics[f"word{k}"] = h(e.read(w, 0x1800))
    pair = words[0]
    for k in (0, 1):
        ptr = e.u32(pair + 4 * k)
        pics[f"body{k}"] = h(e.read(ptr, 0x1800))
    obs["presentation_pictures"] = pics
    hud = e.u32(0x080437EC)
    obs["hud_face"] = h(e.read(hud + 0x100 * SONJA, 0x100))
    dossier = e.u32(0x080853A0)
    obs["dossier_row"] = h(e.read(dossier + 8 * SONJA, 8))
    # texts
    ids = [e.u32(row)] + [e.u16(row + 0x20 + 2 * q) for q in range(6)] + [e.u16(row + 0x2C + 2 * q) for q in range(4)] + [e.u16(row + 0x34)] + [e.u32(row + 0x38 + 0x44 * k) for k in (1, 2)]
    obs["texts"] = {str(i): read_text(g, i) for i in ids if i}
    # numbers: Sonja attacks Andy in her three levels
    atk = {}
    for which in (None, "power", "super"):
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10).unit(1, "artillery", 3, 3).unit(2, "tank", 6, 3)
        gg = ctx.start(m, ["sonja", "andy"])
        if which:
            ctx.power(gg, 1, which)
        r = ctx.attack(gg, (10, 10), (10, 10), (11, 10))
        r2 = ctx.attack(gg, (3, 3), (3, 3), (6, 3)) if False else None
        atk[str(which)] = {"first": r["first"].describe(), "records": r["records"], "hp": [u["hp"] for u in gg.units()]}
    obs["attack"] = atk
    dfn = {}
    for which in (None, "power", "super"):
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
        gg = ctx.start(m, ["andy", "sonja"], humans=(1, 2))
        if which:
            gg.end_turn(human=2)
            ctx.power(gg, 2, which)
            gg.end_turn(human=1)
        gg.attack((10, 10), (10, 10), (11, 10))
        dfn[str(which)] = {"records": ctx.battle_records(gg), "hp": [u["hp"] for u in gg.units()]}
    obs["defend"] = dfn
    # fog vision
    fog = {}
    for which in (None, "power", "super"):
        m = ctx.map()
        for x, y in ((12, 6), (11, 6), (10, 8)):
            m.terrain(x, y, "wood")
        m.unit(1, "tank", 10, 6).unit(2, "infantry", 12, 6).unit(2, "infantry", 11, 6).unit(2, "infantry", 13, 7)
        gg = ctx.start(m, ["sonja", "andy"], fog=True)
        if which:
            ctx.power(gg, 1, which)
            gg.e.wait(30)
        fog[str(which)] = [seen(gg, x, y) for x in range(5, 18) for y in range(2, 12)]
    obs["fog"] = fog
    # the Teams list: Sonja's place among AW2's own COs
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    gt = ctx.boot_teams(m)
    lst = gt.teams()["co_list"]
    obs["teams_order_of_aw2_cos"] = [c for c in lst if c < 19]
    # her Tag page and Tag Powers' numbers
    gtag = tag_battle(ctx, ["sonja", "olaf"], [None, None], units=[(1, "tank", 10, 4)])
    obs["tag_page"] = [x.hex() if isinstance(x, bytes) else x for x in tag_page_of(ctx, gtag)]
    tagn = {}
    for partner in ("hawke", "vonbolt", "kanbei", "andy", "sturm", "crumb", "eagle"):
        gp = tag_battle(ctx, ["sonja", "olaf"], [partner, "max"], units=[(1, "tank", 10, 10), (2, "tank", 11, 10)])
        gp.e.w8(tag.rec(1) + 1, 1)
        gp.e.w8(tag.rec(2) + 1, 1)
        gp.attack((10, 10), (10, 10), (11, 10))
        tagn[partner] = ctx.battle_records(gp)
    obs["tag_attack_records"] = tagn
    # her screens
    screens = {}
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
    gs = ctx.start(m, ["sonja", "andy"])
    gs.e.wait(30)
    screens["battle_first_frame"] = frame_hash(ctx, gs, "s_battle")
    for which in ("power", "super"):
        gs = ctx.start(m, ["sonja", "andy"])
        gs.charge_power(1, which)
        gs.open_map_menu()
        gs.choose("Super" if which == "super" else "Power", gs.MAP_MENU)
        for k in range(100):
            gs.e.wait(4)
            if k % 10 == 5:
                screens[f"{which}_frame{k}"] = frame_hash(ctx, gs, f"s_{which}_{k}")
    gc = ctx.start(m, ["sonja", "andy"])
    gc.open_map_menu()
    gc.choose("CO", gc.MAP_MENU)
    gc.e.wait(240)
    screens["co_page"] = frame_hash(ctx, gc, "s_page")
    obs["screens"] = screens
    with open(os.path.join(ctx.out, "sonja.json"), "w") as f:
        json.dump(obs, f, indent=1, sort_keys=True, default=str)
    ctx.check(True, f"Sonja's observations written ({len(obs)} groups)")
