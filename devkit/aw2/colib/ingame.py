"""The real app, offline, with the Dual Strike pack and the Emerald Sun COs on (`TANGOAW2_ES_VERSUS=1`), driven through the AI debug channel: `aw2dev co portrait ingame` photographs a CO on the
game's own screens (CO select, CO page, HUD, dialogue) for the review sheet."""
import json, os, subprocess, sys, time
from pathlib import Path
from .. import cfg, profiles, util


class App:
    def __init__(self, extra_env=None):
        binary = cfg.REPO / "target" / "release" / "tango"
        util.check_fresh(binary, "tango")
        profiles.ensure("skinds", pack=True)
        cj = profiles.profile_dir("skinds") / "config" / "config.json"
        conf = json.loads(cj.read_text())
        conf.update({"ds_graphics": True, "ds_tilt": False})
        cj.write_text(json.dumps(conf, indent=2))
        self.app = profiles.test_app(binary)
        env = dict(os.environ, TANGOAW2_PROFILE=str(profiles.profile_dir("skinds")), TANGOAW2_AI_DEBUG="0", AW2DEV_LOOK="1", TANGOAW2_ES_VERSUS="1")
        env.update(extra_env or {})
        self.proc = subprocess.Popen([str(self.app)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cfg.REPO)
        addr, t0 = None, time.time()
        while time.time() - t0 < 90 and addr is None:
            line = self.proc.stdout.readline()
            if not line:
                break
            if "AI_DEBUG_LISTENING" in line:
                addr = line.split()[-1]
        if not addr:
            self.stop()
            util.die("the app did not open the AI debug channel")
        sys.path.insert(0, str(cfg.REPO / "tools" / "aidebug"))
        from client import AiDebug
        self.d = AiDebug.connect(addr)
        for _ in range(60):
            if self.d.hello().get("session") not in (None, "none"):
                break
            time.sleep(1)
        self.d.start_offline()

    def stop(self):
        self.proc.kill()
        self.proc.wait()
        subprocess.run(["pkill", "-9", "-f", str(self.app)])

    def shot(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.d.screenshot(str(path))


def mug_rgb(co, pic="face_normal"):
    """A CO's committed normal mug as RGB (None transparent) and its eye point (cell_x, strip_y based), for finding it on a screenshot."""
    import numpy as np
    from PIL import Image
    from . import importer as I
    pics, pal = I.read_art(co)
    a = pics[pic]
    rgb = np.zeros(a.shape + (3,), np.int32)
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x]:
                rgb[y, x] = pal[a[y, x]]
    return a != 0, rgb


def find_on(shot, co, need=0.93, patches=2, pic="face_normal"):
    """Whether the CO's face is on the screenshot (the game shows the mug whole or cropped): some 8 x 8 patches of the committed mug are found, pixel for pixel."""
    import numpy as np
    from PIL import Image
    im = np.array(Image.open(shot).convert("RGB")).astype(np.int32)
    mask, rgb = mug_rgb(co, pic)
    H, W = im.shape[:2]
    found = 0
    for py in range(0, mask.shape[0] - 7, 8 if pic == "face_normal" else 16):
        for px in range(0, mask.shape[1] - 7, 8 if pic == "face_normal" else 16):
            pm = mask[py:py + 8, px:px + 8]
            if pm.sum() < 56:
                continue
            pr = rgb[py:py + 8, px:px + 8]
            if len({tuple(c) for c in pr[pm]}) < 3:
                continue          # a flat patch matches anywhere
            acc = np.zeros((H - 7, W - 7), np.int32)
            for dy in range(8):
                for dx in range(8):
                    if pm[dy, dx]:
                        acc += (np.abs(im[dy:H - 7 + dy, dx:W - 7 + dx] - pr[dy, dx]).max(2) <= 3)
            if acc.max() >= need * pm.sum():
                found += 1
                if found >= patches:
                    return True
    return False


# The Teams list (34 COs with the four): Klaus, Aurelia, Cassius and Livia stand at 27..30 (after Crumb, before Hawke; `co_new::build` puts a new CO after the one it takes after, Adder).
# The Teams screen keeps the P1 card's place in this list at 0x02017C6C (found by diffing EWRAM while UP walked the list): the walk presses UP or DOWN until it is on the CO, so a press
# a busy machine drops or doubles does not matter.
# The game's own list of the Teams screen is at TEAMS_ORDER (CO ids, 0xFF-ended): the CO's place in it is read from there, since each new CO stands after the one it takes after.
ES_IDS = {"klaus": 86, "aurelia": 87, "cassius": 88, "livia": 89, "asuka": 92}
TEAMS_ORDER = 0x0203FE80
TEAMS_CURSOR = 0x02017C6C
TEAMS_LEN = 34


def teams_index(d, co):
    order = list(bytes.fromhex(d.peek(TEAMS_ORDER, 48)["hex"]))
    order = order[: order.index(0xFF)] if 0xFF in order else order
    global TEAMS_LEN
    TEAMS_LEN = len(order)
    return order.index(ES_IDS[co])


def walk_to(d, index):
    import time
    for _ in range(60):
        cur = bytes.fromhex(d.peek(TEAMS_CURSOR, 1)["hex"])[0]
        if cur == index:
            return True
        up = (cur - index) % TEAMS_LEN
        d.press("UP" if up <= TEAMS_LEN - up else "DOWN")
        time.sleep(0.7)
    return False


def photograph(co, out_dir, tries=3):
    for k in range(tries):
        try:
            return _photograph(co, out_dir)
        except Exception as e:
            util.say(f"{co}: try {k + 1} failed: {str(e)[:120]}")
    util.die(f"{co}: could not be photographed")


def _photograph(co, out_dir):
    """Boot the app, pick `co` for P1 on the Normal Battle Teams screen (CO select), start the battle (the HUD), open the CO page from the map menu. Saves <co>_select, <co>_hud, <co>_page."""
    import time
    app = App()
    d = app.d
    out = Path(out_dir)
    try:
        d.wait_until({"phase": {"in": ["title", "select_mode"]}}, 90)
        d.press_until("START", {"phase": "select_mode"}, 40)
        for _ in range(12):
            s = d.state(["screen_info"])["screen_info"]
            if s.get("wheel_item") == 1 and s.get("box_open") is False:
                break
            d.press("DOWN")
            time.sleep(0.8)
        d.press_until("A", {"phase": "select_map"}, 30)
        d.press_until("A", {"phase": "army_select"}, 30)
        time.sleep(2)
        if not walk_to(d, teams_index(d, co)):
            util.die(f"the Teams screen did not reach {co}")
        time.sleep(0.8)
        app.shot(out / f"{co}_select.png")
        d.press_until("A", {"phase": "battle"}, 60)
        d.press_until("A", {"screen": "map", "cues.mapup": True}, 60, gap=1.5)
        st = d.state(["armies"])
        util.say(f"{co}: the battle's P1 CO is {st['armies'][0].get('co_name')}")
        time.sleep(1.0)
        app.shot(out / f"{co}_hud.png")
        # the power's cut-in shows the large figure: fill the meter, open the map menu on Power
        base = int.from_bytes(bytes.fromhex(d.peek(0x08499598, 4)["hex"]), "little")
        cost = d.state(["armies"])["armies"][0]["power_cost"]
        d.poke(base + 0x3C + 0x20, (cost * 2 + 100).to_bytes(4, "little").hex())
        time.sleep(0.5)
        d.press("A", 3)
        d.wait_until({"screen": "map_menu"}, 8)
        rows = [r["text"] for r in d.state(["menu"])["menu"].get("rows", [])]
        util.say(f"{co}: map menu rows {rows}")
        for _ in range(12):
            if (d.state(["menu"])["menu"].get("item") or "").lower().startswith("power"):
                break
            d.press("DOWN")
        d.press("A")
        time.sleep(0.5)
        # the cut-in comes a moment after the quote: shoot fast, keep the frame with the most of the figure's own colours on the red
        import numpy as np
        from PIL import Image
        try:
            mask, rgb = mug_rgb(co, "large")
            own = {tuple(int(v) for v in c) for c in rgb[mask]}
        except FileNotFoundError:
            own = None          # no committed picture to match: the cut-in frame is the one with the most of the figure's black uniform
        best, best_n, quote, quote_n = None, 0, None, 0
        for k in range(26):
            p = out / f"{co}_power{k}.png"
            app.shot(p)
            im = np.array(Image.open(p).convert("RGB"))
            red = ((im[:, :, 0] > 200) & (im[:, :, 1] < 90) & (im[:, :, 2] < 70)).mean()
            if own is None:
                n = int((im.max(2) < 60).sum())          # dark pixels: the figure's black uniform
            else:
                n = sum(1 for c in {tuple(int(v) for v in px) for px in im.reshape(-1, 3)} if c in own)
            if red > 0.03 and n >= best_n:
                best, best_n = p, n
            box = (im[124:152, 70:230].min(2) > 205).mean()       # the dialogue box's cream band at the foot
            if red < 0.07 and box > 0.9:
                quote = p          # (the last such frame: the text is typed out by then)
            time.sleep(0.12)
        import shutil
        if best:
            shutil.copy(best, out / f"{co}_figure.png")
        if quote:
            shutil.copy(quote, out / f"{co}_dialogue.png")
        for k in range(26):
            if not os.environ.get("AW2DEV_KEEP_FRAMES"):
                (out / f"{co}_power{k}.png").unlink(missing_ok=True)
        util.say(f"{co}: the power's large figure " + ("is on " + best.name if best else "was not seen"))
        try:
            d.wait_until({"screen": "map"}, 25)
        except Exception:
            pass
        d.press("A", 3)
        d.wait_until({"screen": "map_menu"}, 8)
        for _ in range(12):
            if d.state(["menu"])["menu"].get("item") == "CO":
                break
            d.press("DOWN")
        d.press("A")
        try:
            d.wait_until({"screen": "co_page"}, 12)
        except Exception as e:
            util.say(f"{co}: waiting for the CO page: {e}")
        time.sleep(1.5)
        app.shot(out / f"{co}_page.png")
        return st["armies"][0].get("co_name")
    finally:
        app.stop()


def best_match(shot, co, pic, box):
    """How well a committed picture is on the screenshot, sliding it over `box` = (x0, y0, x1, y1): the correlation of the two brightness patterns over the picture's opaque pixels
    (the HUD draws its face with a brighter palette than the CO's own, so the colours are not compared)."""
    import numpy as np
    from PIL import Image
    im = np.array(Image.open(shot).convert("RGB")).astype(np.float64)
    lum = im @ np.array([0.299, 0.587, 0.114])
    mask, rgb = mug_rgb(co, pic)
    ref = rgb.astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    h, w = mask.shape
    best = -1.0
    for cut in range(0, 9 if pic == "hud" else 1):         # (the game draws the HUD face with its top rows above the screen)
        m = mask[cut:]
        rr = ref[cut:][m]
        rr = (rr - rr.mean()) / (rr.std() + 1e-9)
        hh = h - cut
        for y in range(box[1], min(im.shape[0] - hh, box[3]) + 1):
            for x in range(box[0], min(im.shape[1] - w, box[2]) + 1):
                v = lum[y:y + hh, x:x + w][m]
                v = (v - v.mean()) / (v.std() + 1e-9)
                best = max(best, float((v * rr).mean()))
    return best


def figure_seen(shot, co):
    """The power's cut-in shows the large figure: much of the figure's own palette is on the picture beyond the red."""
    import numpy as np
    from PIL import Image
    mask, rgb = mug_rgb(co, "large")
    own = {tuple(int(v) for v in c) for c in rgb[mask]}
    im = np.array(Image.open(shot).convert("RGB")).reshape(-1, 3)
    hit = sum(1 for c in {tuple(int(v) for v in px) for px in im} if any(max(abs(a - b) for a, b in zip(c, o)) <= 3 for o in own))
    return hit >= 9


def verify(co, out_dir):
    """Does the game show the committed art? -> {screen: bool}: the CO select card shows the mug (patches of it found pixel for pixel), the HUD shows the HUD face, the power's cut-in shows
    the large figure, the CO page and the dialogue box were reached."""
    out = Path(out_dir)
    res = {}
    res["CO select"] = find_on(out / f"{co}_select.png", co, 0.9, 2, "face_normal")
    res["HUD"] = best_match(out / f"{co}_hud.png", co, "hud", (200, 0, 212, 2)) >= 0.15      # (a weak check: the game draws the HUD face brighter and cut at the top; look at the shot)
    fig = out / f"{co}_figure.png"
    res["power cut-in (large art)"] = fig.exists() and figure_seen(fig, co)
    res["CO page"] = (out / f"{co}_page.png").exists()
    res["dialogue box"] = (out / f"{co}_dialogue.png").exists()
    return res
