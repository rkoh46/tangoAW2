import os

from aw2test import escampaign as es
from aw2test.emu import Emu
from aw2test.harness import test


@test(modes=("ds",))
def es_colours_probe(ctx):
    n = int(os.environ.get("M", "13"))
    last = [None]
    orig = Emu.wait

    def wait(self, k):
        for _ in range(0, k, 2):
            orig(self, 2)
            try:
                base = self.u32(0x0849_9598)
                cur = tuple(self.u8(base + 0x3C * a + 0x1A) for a in range(1, 5)) + (self.u8(self.u32(0x0804_2DDC) + 86 * 0x104 + 0x15),)
            except Exception:
                continue
            if cur != last[0]:
                last[0] = cur
                ctx.log(f"colours {cur}")
    Emu.wait = wait
    try:
        e, g, d = es.enter(ctx, n)
    finally:
        Emu.wait = orig
    e.close()
