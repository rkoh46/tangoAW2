import struct
from aw2test.harness import test

@test(modes=("ds",))
def zz_vram(ctx):
    m = ctx.map()
    g = ctx.boot_teams(m)
    g.set_teams(["andy", "drake"], {1})
    g.e.wait(80)
    e = g.e
    io = bytes(e.read(0x04000000, 0x60))
    ctx.log("DISPCNT %04x" % struct.unpack_from('<H', io, 0)[0])
    for i in range(4):
        ctx.log("BG%dCNT %04x HOFS %d VOFS %d" % (i, struct.unpack_from('<H', io, 8+2*i)[0], struct.unpack_from('<H', io, 0x10+4*i)[0], struct.unpack_from('<H', io, 0x12+4*i)[0]))
    open(ctx.out + "/vram.bin", "wb").write(bytes(e.read(0x06000000, 0x18000)))
    open(ctx.out + "/pal.bin", "wb").write(bytes(e.read(0x05000000, 0x400)))
    open(ctx.out + "/oam.bin", "wb").write(bytes(e.read(0x07000000, 0x400)))
    e.close()
