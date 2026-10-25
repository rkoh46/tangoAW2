#!/usr/bin/env python3
"""Labels the Emerald Sun review pictures (tests/test_es_review.py) and makes one contact sheet per act.

    es_sheets.py <raw dir> <out dir>

<raw dir> holds m<N>_<view>.png (views: full = fog off, fogon, fogoff), 16 pixels a cell. <out dir> gets "mission_NN_<view>.png" (3x, headed
"MISSION N - Title (view)") and act1..act4_contact_sheet.png (the same pictures at 1x on a grid)."""
import os
import re
import sys
from PIL import Image, ImageDraw, ImageFont

TITLES = {
    1: "Landfall", 2: "Testudo", 3: "The Wall", 4: "The Second Legion", 5: "Dust and Wheels", 6: "Tribute", 7: "Mare Nostrum", 8: "Hammer and Anvil",
    9: "Grain Ships", 10: "The Quiet Pass", 11: "The Treasure Train", 12: "Siege of Iron", 13: "The Free Port", 14: "Varro's Gambit",
    15: "Pax Romana", 16: "Sol Invictus",
}
VIEWS = {"full": "full map, fog off", "fogoff": "full map, fog off", "fogon": "fog on"}
ORDER = ["full", "fogoff", "fogon"]
ACTS = {"act1": range(1, 5), "act2": range(5, 9), "act3": range(9, 13), "act4": range(13, 17)}


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
        cols = 2
        rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
        width = max(sum(t.width + 10 for t in r) for r in rows)
        height = sum(max(t.height for t in r) + 10 for r in rows)
        sheet = Image.new("RGB", (width, height), (10, 10, 14))
        y = 0
        for r in rows:
            x = 0
            for t in r:
                sheet.paste(t, (x, y))
                x += t.width + 10
            y += max(t.height for t in r) + 10
        sheet.save(os.path.join(out, f"{act}_contact_sheet.png"))
        print(act, len(tiles), "pictures", sheet.size)


WEATHERS = {3: "rain (fog)", 5: "sandstorm, desert", 8: "rain (fog)", 9: "clear, wasteland", 10: "snow, fog", 11: "sandstorm, desert", 12: "snow", 13: "clear, wasteland"}


def weather_sheet(raw, out):
    """es_weather.png: the weather missions' fields in the game (weather_m<N>.png, 240 x 160, 2x), each labelled with its mission and weather."""
    files = {int(m.group(1)): os.path.join(raw, f) for f in os.listdir(raw) for m in [re.fullmatch(r"weather_m(\d+)\.png", f)] if m}
    if not files:
        return
    tiles = [labelled(Image.open(files[n]).convert("RGB"), f"MISSION {n} — {TITLES[n]}: {WEATHERS.get(n, '')}", 2, 18) for n in sorted(files)]
    cols = 2
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    width = max(sum(t.width + 10 for t in r) for r in rows)
    height = sum(max(t.height for t in r) + 10 for r in rows)
    sheet = Image.new("RGB", (width, height), (10, 10, 14))
    y = 0
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + 10
        y += max(t.height for t in r) + 10
    sheet.save(os.path.join(out, "es_weather.png"))
    print("weather sheet", len(tiles), "pictures", sheet.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
    weather_sheet(sys.argv[1], sys.argv[2])
