"""The BH Campaign's text budget, measured in the running game: the campaign's texts take ids from 0x7400 to 0x7FFF
(3,072) and the whole compiled campaign (texts, scripts, maps, units) lives in 0x08F00100..0x08FC0000 of the ROM image. The
dialogue is long; this test fails when the ids or the data region run short, and says how much is left."""

from aw2test import bhcampaign as bh
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

TEXT_FIRST, TEXT_LAST = 0x7400, 0x7FFF
TABLE = 0x08610A38
DATA, DATA_END = 0x08F00000, 0x08FC0000
ID_RESERVE = 100            # ids kept free (the engine's own texts: a mission's name and objective are counted, the rest is small)
BYTE_RESERVE = 64 * 1024    # bytes kept free in the data region


@test(modes=("ds",))
def bh_text_budget_ids_and_data(ctx):
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.start_at(won_mask=0, unlocked_mask=1)
    d.wait_world_map()
    used, top, longest = 0, 0, 0
    for tid in range(TEXT_FIRST, TEXT_LAST + 1):
        p = e.u32(TABLE + 4 * tid)
        if DATA <= p < DATA_END:
            used += 1
            top = max(top, p)
    ctx.log(f"text ids used: {used} of {TEXT_LAST - TEXT_FIRST + 1}")
    ctx.check(used + ID_RESERVE <= TEXT_LAST - TEXT_FIRST + 1, f"{used} text ids used, at least {ID_RESERVE} left")
    # The data region: the blob is written from the bottom up and the rest of the region reads 0xFF.
    end = DATA
    at = DATA_END - 4096
    while at >= DATA:
        b = e.read(at, 4096)
        if any(x != 0xFF for x in b):
            end = at + max(i for i, x in enumerate(b) if x != 0xFF) + 1
            break
        at -= 4096
    ctx.log(f"the compiled campaign ends near 0x{end:08X}: {end - DATA} of {DATA_END - DATA} bytes, {DATA_END - end} left")
    ctx.check(DATA_END - end >= BYTE_RESERVE, f"{DATA_END - end} bytes of the data region left (at least {BYTE_RESERVE})")
    e.close()
