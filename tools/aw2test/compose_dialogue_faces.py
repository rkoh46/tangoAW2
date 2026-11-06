"""Composes the dialogue-face review pictures from two runs of `aw2dev gfx audit --scenes dialogue_faces --modes sn_campaign --looks aw2` (a `before` and an `after` folder):
faces_{before,after}_{lili,tabitha}.png (the whole screen of a box with that CO speaking), faces_{before,after}_compare.png (box strips: a vanilla CO, Caulder, Lili, Tabitha), each also at 3x nearest-neighbour (`_x3`).
Boxes: vanilla m1_victory_box00, Tabitha m14_intro_box10, Lili m14_intro_box02, Caulder m14_intro_box27 (Caulder speaks only in the after folder's M14 run: his art is unchanged, so both rows use it).
Usage: python3 compose_dialogue_faces.py <before_dir> <after_dir> <out_dir>   (the dirs are .../sn_campaign/dialogue_faces/aw2)"""
import os
import sys

from PIL import Image

before, after, out = sys.argv[1:4]
BOX = {"vanilla": "m1_victory_box00", "tabitha": "m14_intro_box10", "lili": "m14_intro_box02", "caulder": "m14_intro_box27"}


def pic(folder, key):
    f = folder if key != "caulder" else after
    return Image.open(os.path.join(f, BOX[key] + ".png")).convert("RGB")


def save(im, name):
    im.save(os.path.join(out, name + ".png"))
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(out, name + "_x3.png"))


for tag, folder in (("before", before), ("after", after)):
    for co in ("lili", "tabitha"):
        save(pic(folder, co), f"faces_{tag}_{co}")
    strips = [pic(folder, k).crop((0, 0, 120, 44)) for k in ("vanilla", "caulder", "lili", "tabitha")]
    sheet = Image.new("RGB", (240, 88))
    for i, s in enumerate(strips):
        sheet.paste(s, ((i % 2) * 120, (i // 2) * 44))
    save(sheet, f"faces_{tag}_compare")
