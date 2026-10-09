#!/usr/bin/env python3
"""Labels the review pictures (tests/test_bh_review.py) and makes one contact sheet per act.

    review_sheets.py <raw dir> <out dir>

<raw dir> holds m<N>_<view>.png (views: full, fogon, fogoff, front2, stage2), unscaled (16 pixels a
cell). <out dir> gets "mission_NN_<view>.png" (3x, headed "MISSION N - Title (view)") and
act1..act5b_contact_sheet.png (the same pictures at 1x on a grid)."""
import os
import re
import sys
from PIL import Image, ImageDraw, ImageFont

TITLES = {
    1: "Storm Landing", 2: "The Sleeping Foundry", 3: "Blockade Runner", 4: "Marshal in Green", 5: "Night Raid",
    6: "Stepping Stones", 7: "Greenhaven Arsenal", 8: "The Twin Gates", 9: "The Loot Train", 10: "Evergreen Citadel",
    11: "Ashfall Pass", 12: "Highway to the Horizon", 13: "Festival of Flame", 14: "No Soldier Left Behind",
    15: "The Skybridge", 16: "Comet Keep", 17: "Cold Iron", 18: "The Pit", 19: "The Assembly Line",
    20: "Moonlit Harbours", 21: "Running Dry", 22: "Whiteout", 23: "Laboratory 7", 24: "Sky Gala",
    25: "Twin Harbours", 26: "The Last Alliance", 27: "Echo", 28: "Home Is Where The Black Is",
    29: "The Orange Gate", 30: "Nell's Stand", 31: "The Colonel's Vault",
}
VIEWS = {"full": "full map, Setup", "fogon": "fog on, Setup", "fogoff": "fog off, Setup",
         "front2": "second front, Setup", "stage2": "stage 2"}
ORDER = ["full", "fogon", "fogoff", "front2", "stage2"]
ACTS = {"act1": range(1, 4), "act2": range(4, 12), "act3": range(12, 17), "act4": range(17, 23),
        "act5a": range(23, 29), "act5b": range(29, 32)}


def font(size):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def labelled(im, text, scale, size):
    im = im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale != 1 else im
    bar = size + 14
    out = Image.new("RGB", (max(im.width, 360), im.height + bar), (20, 20, 28))
    out.paste(im, (0, bar))
    ImageDraw.Draw(out).text((8, 6), text, fill=(255, 255, 255), font=font(size))
    return out


def main(raw, out):
    os.makedirs(out, exist_ok=True)
    have = {}
    for f in os.listdir(raw):
        m = re.fullmatch(r"m(\d+)_(\w+)\.png", f)
        if m and m.group(2) in VIEWS:
            have[(int(m.group(1)), m.group(2))] = os.path.join(raw, f)
    for act, nums in ACTS.items():
        tiles = []
        for n in nums:
            for v in ORDER:
                if (n, v) not in have:
                    continue
                im = Image.open(have[(n, v)]).convert("RGB")
                text = f"MISSION {n} — {TITLES[n]} ({VIEWS[v]})"
                labelled(im, text, 3, 26).save(os.path.join(out, f"mission_{n:02d}_{v}.png"))
                tiles.append(labelled(im, text, 1, 15))
        if not tiles:
            continue
        cols = 3 if len(tiles) > 4 else 2
        rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
        widths = [max(sum(t.width + 10 for t in r) for r in rows)]
        h = sum(max(t.height for t in r) + 10 for r in rows)
        sheet = Image.new("RGB", (widths[0], h), (10, 10, 14))
        y = 0
        for r in rows:
            x = 0
            for t in r:
                sheet.paste(t, (x, y))
                x += t.width + 10
            y += max(t.height for t in r) + 10
        sheet.save(os.path.join(out, f"{act}_contact_sheet.png"))
        print(act, len(tiles), "pictures", sheet.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
