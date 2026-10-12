"""Watch the Dual Strike tilt through an effect: every frame's picture is made (`tiltall`), and the tilt's own debug logs
(TANGOAW2_TILT_SKIP_LOG, TANGOAW2_TILT_LEAK_LOG) are read back per frame: frames left flat, frames where a blend or a window
still shows the console's flat map."""

import os
import re


def env(ctx, scale="4"):
    os.makedirs(ctx.out, exist_ok=True)
    log = os.path.join(ctx.out, "tilt.log")
    try:
        os.remove(log)
    except OSError:
        pass
    return {
        "TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SCALE": scale,
        "TANGOAW2_TILT_SKIP_LOG": "1", "TANGOAW2_TILT_LEAK_LOG": "1", "TANGOAW2_TILT_LOG": log,
    }


def on(ctx, g, shots=0):
    """From now on every frame is rendered; `shots`: write every shots-th frame as a picture to <out>/frames."""
    log = os.path.join(ctx.out, "tilt.log")
    try:
        os.remove(log)
    except OSError:
        pass
    shots = int(os.environ.get("TILTFX_STRIDE", shots or 0))
    if shots:
        d = os.path.join(ctx.out, "frames")
        os.makedirs(d, exist_ok=True)
        g.e.cmd(f"tiltall 1 {d} {shots}")
    else:
        g.e.cmd("tiltall 1")


def off(g):
    g.e.cmd("tiltall 0")


def report(ctx, name="effect"):
    """Frames with skips / leaks since on(): returns (frames, skipped {frame: [lines]}, leaked {frame: n})."""
    log = os.path.join(ctx.out, "tilt.log")
    frames, skipped, leaked = 0, {}, {}
    fr = 0
    try:
        lines = open(log).read().splitlines()
    except OSError:
        lines = []
    for l in lines:
        m = re.match(r"@frame (\d+)", l)
        if m:
            fr = int(m.group(1))
            frames += 1
            continue
        m = re.match(r"ds_tilt skip line (\d+)", l)
        if m:
            skipped.setdefault(fr, []).append(int(m.group(1)))
            continue
        m = re.match(r"ds_tilt leak (\d+) mode (\d) bldcnt (\w+) alpha (\w+) win (\w+) (\w+)", l)
        if m and int(m.group(1)) > 0:
            leaked[fr] = f"{m.group(1)} m{m.group(2)} bld{m.group(3)} a{m.group(4)} win{m.group(5)[0]}{m.group(6)[0]}"
    def ranges(d):
        out, cur = [], None
        for f in sorted(d):
            v = d[f] if not isinstance(d[f], list) else tuple(sorted(set(d[f])))
            if cur and f == cur[1] + 1 and cur[2] == v:
                cur[1] = f
            else:
                cur = [f, f, v]
                out.append(cur)
        return [f"{a}-{b}:{v}" for a, b, v in out]
    ctx.log(f"TILT {name}: {frames} frames; skipped {len(skipped)}: {ranges(skipped)[:30]}")
    ctx.log(f"TILT {name}: leaked {len(leaked)}: {ranges(leaked)[:30]}")
    import shutil
    shutil.copy(log, os.path.join(ctx.out, f"tilt-{re.sub(r'[^A-Za-z0-9]+', '_', name)}.log"))
    open(log, "w").close()
    return frames, skipped, leaked
