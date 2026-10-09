"""Where the ROMs, runners and scratch output live (all overridable by env)."""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TOOL))


def aw2_rom():
    return os.environ.get(
        "AW2TEST_ROM", os.path.expanduser("~/Documents/TangoAW2/roms/Advance_wars_2.gba")
    )


def ds_rom():
    return os.environ.get(
        "TANGOAW2_DS_ROM",
        os.path.expanduser("~/Documents/TangoAW2/roms/Advance Wars - Dual Strike (USA).nds"),
    )


def runner(name):
    """This checkout's build, or $AW2TEST_RUNNER_DIR's (another build, for
    before/after comparisons)."""
    d = os.environ.get("AW2TEST_RUNNER_DIR") or os.path.join(REPO, "target", "release", "examples")
    return os.path.join(d, name)


def out_dir(*parts):
    """Scratch output (gitignored): tools/aw2test/out/..., or $AW2TEST_OUT."""
    base = os.environ.get("AW2TEST_OUT", os.path.join(TOOL, "out"))
    d = os.path.join(base, *parts)
    os.makedirs(d, exist_ok=True)
    return d


LIVE_SAVE = os.path.expanduser("~/Documents/TangoAW2/saves/Advance Wars 2.sav")


def base_save():
    """A cartridge save to start from: any save past the campaign prologue (it is
    only read; the harness writes its maps into a copy). $AW2TEST_BASE_SAVE, or
    a pinned copy in the output folder (`base.sav`), taken once from the
    player's own save (which is never written, and which changes as they
    play: a pinned copy keeps every run starting from the same state)."""
    p = os.environ.get("AW2TEST_BASE_SAVE")
    if p:
        return p
    pinned = os.path.join(out_dir(), "base-clean.sav")
    if not os.path.exists(pinned):
        with open(LIVE_SAVE, "rb") as f:
            data = f.read()
        with open(pinned, "wb") as f:
            f.write(_profile_only(data))
    return pinned


def _profile_only(data):
    """The save with only its profile: every other slot (design maps, suspended
    games, the BH and DS Campaign records and their latch flags) erased, and the
    profile's suspend marks cleared. The player's own save changes as they play
    (a BH record with its once-triggers already latched kept scenes and day
    events from firing in the tests), the tests want a save with nothing beside
    the profile."""
    import struct
    from . import saveimg
    data = bytearray(data)
    img = saveimg.Image(bytes(data))
    keep = {img.newest_profile()["sector"]}
    for i in range(16):
        if i not in keep:
            data[i * 0x1000:(i + 1) * 0x1000] = b"\xff" * 0x1000
    for i in sorted(keep):
        sec = data[i * 0x1000:(i + 1) * 0x1000]
        sec[0xFEF:0xFFF] = bytes(0 if j == i else 0xFF for j in range(16))
        for k in saveimg.C420_SUSPEND.values():
            sec[0x52 + saveimg.P_C420 + k] = 0
        sec[6] = sec[7] = 0
        t = (sum(sec) + 255) & 0xFF
        sec[6], sec[7] = t, (~t) & 0xFF
        data[i * 0x1000:(i + 1) * 0x1000] = sec
    return bytes(data)
