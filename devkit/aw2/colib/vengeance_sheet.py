"""`aw2dev co sheet vengeance`: Aria's Vengeance (units with 8 HP or less attack 25% harder) in the game's own damage forecasts: runs tools/aw2test/tests/test_aria_compare.py (the forecast box's number of 7 matchups at 10, 8 and 5
displayed HP for Andy, Aria and Aria in Build Anew, each checked against the damage formula) and writes the table (.md) and a picture sheet of the forecast boxes (.png)."""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .. import cfg

OUT = cfg.REPO / "tools" / "aw2test" / "out" / "ds" / "aria_vengeance_forecast_table"
NAMES = {"infantry": "Infantry", "tank": "Tank", "mdtank": "Md Tank", "artillery": "Artillery", "bcopter": "B Copter", "fighter": "Fighter"}
MATCHUPS = [("infantry", "infantry"), ("tank", "tank"), ("tank", "infantry"), ("mdtank", "tank"), ("artillery", "tank"), ("bcopter", "tank"), ("fighter", "bcopter")]


def run_test():
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    r = subprocess.run([sys.executable, str(run), "--mode", "ds", "-k", "aria_vengeance_forecast"], cwd=cfg.REPO, capture_output=True, text=True)
    return r.returncode == 0, r.stdout[-1500:]


def table(rows):
    g = lambda c, a, d, h: rows[f"{c}|{a}|{d}|{h}"]["box"]
    lines = ["| Matchup (attacker -> target) | Andy 10 / 8 / 5 HP | Aria 10 HP (no Vengeance) | Aria 8 / 5 HP (Vengeance) | Aria + Build Anew 10 / 8 / 5 HP |", "|---|---|---|---|---|"]
    for a, d in MATCHUPS:
        lines.append(f"| {NAMES[a]} -> {NAMES[d]} | {g('Andy', a, d, 10)}% / {g('Andy', a, d, 8)}% / {g('Andy', a, d, 5)}% | {g('Aria', a, d, 10)}% | {g('Aria', a, d, 8)}% / {g('Aria', a, d, 5)}% | "
                     f"{g('Aria, Build Anew', a, d, 10)}% / {g('Aria, Build Anew', a, d, 8)}% / {g('Aria, Build Anew', a, d, 5)}% |")
    return "\n".join(lines)


def build(png, md):
    rows = json.loads((OUT / "forecast.json").read_text())
    ratio = lambda c, a, d, h: rows[f"{c}|{a}|{d}|{h}"]["box"] / max(1, rows[f"Andy|{a}|{d}|{h}"]["box"])
    text = ("# Aria's Vengeance in the game's own damage forecast\n\n"
            "The damage % the forecast box shows for the attacker against the same full-HP target (plain terrain), read from the game at the target cursor, for 7 matchups. Every number was checked against the damage formula "
            "(chart damage x firepower, x displayed HP / 10, x (200 - defence) / 100; the shot's own battle record equals it): all 63 cells agree, and the box equals the record.\n\n"
            + table(rows) + "\n\n"
            "(Aria 9-10 HP is Andy's number: she has no other bonus, so the column for 'Aria without Vengeance' is the 10 HP one.)\n\n"
            f"At 8 HP Aria's Tank hits a Tank for {rows['Aria|tank|tank|8']['box']}% against Andy's {rows['Andy|tank|tank|8']['box']}%, at 5 HP {rows['Aria|tank|tank|5']['box']}% against {rows['Andy|tank|tank|5']['box']}%: "
            f"{ratio('Aria', 'tank', 'tank', 8):.2f}x and {ratio('Aria', 'tank', 'tank', 5):.2f}x.\n\n"
            "**Why it matters:** a damaged unit normally hits weaker in proportion to its HP (an 8 HP Tank does 80% of a healthy one's damage, a 5 HP Tank 50%); Vengeance's +25% on top makes Aria's wounded units hit nearly like healthy ones "
            "(an 8 HP Tank of hers does about as much as an Andy Tank at 10 HP: "
            f"{rows['Aria|tank|tank|8']['box']}% against {rows['Andy|tank|tank|10']['box']}%).\n")
    Path(md).write_text(text)
    font = ImageFont.load_default()
    box = lambda c, h: rows[f"{c}|tank|tank|{h}"]["box"]
    tiles = [(f"Andy Tank, 8 HP -> Tank: {box('Andy', 8)}%", "fc_andy_tank8"), (f"Aria Tank, 8 HP -> Tank (Vengeance): {box('Aria', 8)}%", "fc_aria_tank8"), (f"Aria Tank, 8 HP, Build Anew: {box('Aria, Build Anew', 8)}%", "fc_aria_power_tank8"),
             (f"Andy Tank, 5 HP -> Tank: {box('Andy', 5)}%", "fc_andy_tank5"), (f"Aria Tank, 5 HP -> Tank (Vengeance): {box('Aria', 5)}%", "fc_aria_tank5"), (f"Aria Tank, 5 HP, Build Anew: {box('Aria, Build Anew', 5)}%", "fc_aria_power_tank5")]
    S = 2
    W, H = 240 * S, 160 * S
    sheet = Image.new("RGB", (3 * (W + 8) + 8, 2 * (H + 26) + 8), (24, 24, 32))
    d = ImageDraw.Draw(sheet)
    for k, (cap, name) in enumerate(tiles):
        im = Image.open(OUT / f"{name}.bmp").convert("RGB").crop((0, 0, 240, 160)).resize((W, H), Image.NEAREST)
        x, y = 8 + (k % 3) * (W + 8), 8 + (k // 3) * (H + 26)
        sheet.paste(im, (x, y + 16))
        # an inset of the forecast box at 3x (the digits read clearly: 39 / 48, not 39 / 40)
        box = Image.open(OUT / f"{name}.bmp").convert("RGB").crop((30, 75, 90, 105)).resize((180, 90), Image.NEAREST)
        sheet.paste(box, (x + W - 186, y + 22))
        d.text((x, y + 2), cap, fill=(255, 220, 90), font=font)
    sheet.save(png)
    return text
