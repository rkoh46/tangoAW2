"""Emerald Sun Campaign: each mission's weather and look in the game (`-k es_weather_m`), and the weather pictures for the sheet (`es_weather.png`, AW2TEST_REVIEW_DIR).

The campaign sets a mission's weather in its header: clear, snow (gPlaySt weather 1, mode 3 = fixed), rain (2, mode 3, and it brings fog) or Dual Strike's sandstorm (fixed weather mode 3 with clear as the weather: bytes
00 03 00 00 at 0x03003FEC, `crate::sandstorm`). The test enters the mission, reads those bytes and the fog flag, and photographs the field twice: a weather moves (rain streaks, drifting grains,
falling snow), so the two pictures differ beyond what the units' idle animation makes. Missions: M3 and M8 rain, M5 and M11 sandstorm (desert look), M10 and M12 snow, M9 clear on a wasteland."""
import os

from aw2test import escampaign as es
from aw2test.harness import test

WEATHER = 0x03003FEC
FOG = 0x03003FCD
# mission: (weather bytes at 0x03003FEC.., fog on after entering)
EXPECT = {
    3: (bytes([2, 3, 0, 0]), None), 5: (bytes([0, 3, 0, 0]), False), 8: (bytes([2, 3, 0, 0]), None), 10: (bytes([1, 3, 0, 0]), None),
    11: (bytes([0, 3, 0, 0]), False), 12: (bytes([1, 3, 0, 0]), None), 9: (bytes([0, 0, 0, 0]), False),
}


def check(ctx, n):
    from PIL import Image, ImageChops
    e, g, d = es.enter(ctx, n)
    want, fog = EXPECT[n]
    have = bytes(e.read(WEATHER, 4))
    ctx.log(f"M{n}: weather bytes {have.hex()} fog {e.u8(FOG)}")
    ctx.eq(have[:2], want[:2], f"M{n}: the weather the mission sets")
    if n in (3, 8):
        ctx.check(e.u8(FOG) != 0, f"M{n}: rain brings fog")
    a = e.shot(os.path.join(ctx.out, f"w{n}a"))
    e.wait(23)
    b = e.shot(os.path.join(ctx.out, f"w{n}b"))
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    moved = sum(1 for p in ImageChops.difference(ia, ib).getdata() if max(p) > 24)
    ctx.log(f"M{n}: {moved} pixels changed between two pictures 23 frames apart")
    if n in (3, 5, 8, 10, 11, 12):
        ctx.check(moved >= 60, f"M{n}: the weather moves on the screen ({moved} pixels)")
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        ia.save(os.path.join(out, f"weather_m{n}.png"))
    e.close()


def _make(n):
    def fn(ctx):
        check(ctx, n)
    fn.__name__ = f"es_weather_m{n}"
    test(modes=("ds",))(fn)


for _n in EXPECT:
    _make(_n)
