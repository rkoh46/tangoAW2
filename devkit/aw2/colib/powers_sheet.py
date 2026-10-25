"""`aw2dev co portrait powers CO`: the pictures that show a CO's powers working, from the real game, on one labelled contact sheet (docs/dev/asuka.md).

The frames come from two places, both the game's own output (never composed): `co portrait ingame` (the app: CO select card, HUD, CO page, the quote box, the cut-in's figure) and the scripted battle
tests `tools/aw2test/tests/test_asuka_pictures.py` (the console's frames: the power bar filling, a CO Power's and a Super Power's activation, the units' HP before and after, the Tag Power with Von Bolt,
a battle where Counter Break strikes first, the fog view). The tests are run here (`run.py -k asuka_pics`) unless `--no-run`."""
import subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .. import cfg

OUT = cfg.REPO / "tools" / "aw2test" / "out" / "ds"


def frame(test, name):
    p = OUT / test / f"{name}.bmp"
    return Image.open(p).convert("RGB") if p.exists() else None


def meter(test, name):
    """The top right quarter of a frame (the CO panel's meter and stars), for the power bar row."""
    im = frame(test, name)
    return None if im is None else im.crop((120, 0, 240, 80))


def ingame(co, name):
    p = cfg.work("co", "ingame", co) / f"{co}_{name}.png"
    return Image.open(p).convert("RGB") if p.exists() else None


def rows(co):
    """[(row title, [(caption, image)])]: what each picture shows is said in its caption."""
    cop, scop = "asuka_pics_cop_activation", "asuka_pics_scop_activation"
    bar, tagt, cb, fog = "asuka_pics_power_bar", "asuka_pics_tag_power_with_von_bolt", "asuka_pics_counter_break", "asuka_pics_fog_view"
    grid = "asuka_pics_co_select_grid"
    af, hq = "asuka_pics_ammo_and_fuel", "asuka_pics_hq_follows_the_co"
    return [
        ("Her screens", [("CO select card (Versus Teams)", ingame(co, "select")), ("HUD (face, meter, stars)", ingame(co, "hud")), ("CO page (her own text)", ingame(co, "page")), ("Power cut-in (large art)", ingame(co, "figure")), ("Quote box", ingame(co, "dialogue"))]),
        ("CO select grids (War Room, Survival, Champion)", [("Dual Strike's grid, cursor on Asuka", frame(grid, "grid_asuka")), ("AW2's own screen, cursor on Asuka", frame(grid, "grid_aw2"))]),
        ("HQ follows the CO: army 1 is Orange Star's slot (red); Asuka's HQ is Black Hole's", [("Asuka (Black Hole's HQ)", frame(hq, "hq_asuka")), ("Hawke (Black Hole's HQ)", frame(hq, "hq_hawke")), ("Andy (Orange Star's HQ)", frame(hq, "hq_andy")), ("Sonja (Yellow Comet's HQ)", frame(hq, "hq_sonja"))]),
        ("Dark Intel / Event Horizon halve the enemy's ammo and fuel (the unit panel on an enemy Tank: fuel 70, ammo 9)", [("before Dark Intel", frame(af, "af_cop_before")), ("after Dark Intel: fuel 35, ammo 4", frame(af, "af_cop_after")), ("before Event Horizon", frame(af, "af_scop_before")), ("after Event Horizon: fuel 35, ammo 4", frame(af, "af_scop_after"))]),
        ("Power bar filling (CO Power 3 stars = 27000)", [(f"{p}% of 27000 (meter zoomed)", meter(bar, f"bar_{k}")) for k, p in enumerate((0, 25, 50, 75, 100))] + [("Super Power ready (9 stars)", meter(bar, "bar_super"))]),
        ("CO Power: Dark Intel (+1 / -1 HP)", [("before: Mech 45, enemy Infantry 55", frame(cop, "cop_before")), ("quote box", frame(cop, "cop_quote")), ("cut-in", frame(cop, "cop_cutin")), ("flash", frame(cop, "cop_flash")), ("after: Mech 55, Infantry 45", frame(cop, "cop_after"))]),
        ("Super Power: Event Horizon (+2 / -2 HP)", [("before", frame(scop, "scop_before")), ("quote box", frame(scop, "scop_quote")), ("cut-in", frame(scop, "scop_cutin")), ("flash", frame(scop, "scop_flash")), ("after: Mech 65, Infantry 35", frame(scop, "scop_after"))]),
        ("Tag Power with Von Bolt (Vault Breakers, 115)", [("menu offers Tag", frame(tagt, "tag_menu")), ("the Tag screen sliding in", frame(tagt, "tag_screen_slide")), ("the Tag screen", frame(tagt, "tag_screen")), ("first half: Asuka's Super Power", frame(tagt, "tag_first_half")), ("second half: Von Bolt's", frame(tagt, "tag_second_half"))]),
        ("Counter Break: Andy's Tank attacks, she strikes first", [("before (her Tank at 10)", frame(cb, "cb_before")), ("the scene opens", frame(cb, "cb_f06")), ("her first strike lands", frame(cb, "cb_f17")), ("his reply from the HP he has left", frame(cb, "cb_f24")), ("after: she is at 10, he is at 2", frame(cb, "cb_after"))]),
        ("Fog of War: vision 3 Tank", [("Andy: sees 3", frame(fog, "fog_andy")), ("Asuka day to day: sees 4", frame(fog, "fog_d2d")), ("Dark Intel: sees 5 and into the woods", frame(fog, "fog_cop"))]),
    ]


def sheet(co, scale=2):
    W, H = 240 * scale, 160 * scale
    font = ImageFont.load_default()
    pad, head, cap = 8, 22, 16
    data = rows(co)
    cols = max(len(r[1]) for r in data)
    img = Image.new("RGB", (cols * (W + pad) + pad, sum(head + H + cap + pad for _ in data) + pad), (24, 24, 32))
    d = ImageDraw.Draw(img)
    y = pad
    for title, items in data:
        d.text((pad, y + 4), title, fill=(255, 220, 90), font=font)
        y += head
        for k, (cap_text, im) in enumerate(items):
            x = pad + k * (W + pad)
            if im is None:
                d.rectangle((x, y, x + W, y + H), outline=(200, 60, 60))
                d.text((x + 6, y + 6), "MISSING", fill=(255, 90, 90), font=font)
            else:
                img.paste(im.resize((W, H), Image.NEAREST), (x, y))
            d.text((x, y + H + 3), cap_text, fill=(230, 230, 230), font=font)
        y += H + cap + pad
    return img


def run_tests():
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    r = subprocess.run([sys.executable, str(run), "--mode", "ds", "-k", "asuka_pics"], cwd=cfg.REPO, capture_output=True, text=True)
    return r.returncode == 0, r.stdout[-2000:]
