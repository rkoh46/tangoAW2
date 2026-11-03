"""Composes `faces_vs_army_screen.png` from the pictures `-k gauntlet_faces_vs_army_screen` leaves (AW2TEST_FACES): per CO the face as a dialogue box draws it (left) next to the same CO on the army screen (right).
Usage: python3 compose_faces.py <folder> <out.png>"""
import glob
import os
import sys

from PIL import Image, ImageDraw

folder, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
cos = sorted({int(os.path.basename(f)[4:-4]) for f in glob.glob(os.path.join(folder, "box_*.png"))})
NAMES = {0: "Nell", 1: "Andy", 2: "Max", 3: "Olaf", 4: "Sami", 5: "Grit", 6: "Kanbei", 7: "Sonja", 8: "Eagle", 9: "Drake", 10: "Sturm", 11: "Flak", 12: "Lash", 13: "Adder", 14: "Hawke", 15: "Hachi",
         16: "Colin", 17: "Jess", 18: "Sensei", 72: "Jugger", 73: "Koal", 74: "Kindle", 75: "Von Bolt", 76: "Grimm", 77: "Javier", 78: "Sasha", 79: "Jake", 80: "Rachel", 86: "Tabitha", 87: "Lili",
         88: "Caulder", 92: "Asuka", 93: "Aria"}
cols = 3
cw, ch = 128 + 6 + 240 + 10, 2 * 88
cell_h = 160 + 14
sheet = Image.new("RGB", (cols * cw, ((len(cos) + cols - 1) // cols) * cell_h), (20, 20, 28))
dr = ImageDraw.Draw(sheet)
for i, co in enumerate(cos):
    x, y = (i % cols) * cw, (i // cols) * cell_h
    dr.text((x + 2, y), f"{NAMES.get(co, co)} ({co}): box face | army screen", fill=(255, 220, 120))
    sheet.paste(Image.open(os.path.join(folder, f"box_{co}.png")).convert("RGB").resize((128, 88), Image.NEAREST), (x, y + 12))
    s = os.path.join(folder, f"screen_{co}.png")
    if os.path.exists(s):
        sheet.paste(Image.open(s).convert("RGB"), (x + 134, y + 12))
sheet.save(out)
print(len(cos), sheet.size)
