#!/usr/bin/env python3
"""Renders the Emerald Sun dialogue (src/es_text/act*.txt) as one readable Markdown file for review.

    python3 tools/estext/render.py [out.md]      (default: devkit/work/campaign/es/ES_DIALOGUE.md)

Grouped by mission in play order: prologue, then per mission its scenes (briefing, day scenes, victory, the scenes on the world map), each with its song and box
count; a box is `**SPEAKER** line one / line two`. Used by `aw2dev campaign dialogue`."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "tango-gamesupport-aw2", "src", "es_text"))
TITLES = {1: "Landfall", 2: "Testudo", 3: "The Wall", 4: "The Second Legion", 5: "Dust and Wheels", 6: "Tribute", 7: "Mare Nostrum", 8: "Hammer and Anvil",
          9: "Grain Ships", 10: "The Quiet Pass", 11: "The Treasure Train", 12: "Siege of Iron", 13: "The Free Port", 14: "Varro's Gambit", 15: "Pax Romana",
          16: "Sol Invictus"}
KINDS = {"pre": "Briefing", "pre2": "Briefing, part 2", "post": "After the battle", "post2": "After the battle, part 2", "map": "On the world map",
         "map2": "On the world map, part 2", "epilogue": "Epilogue", "epilogue2": "Epilogue, the black light"}


def scenes():
    out = {}
    order = []
    for f in sorted(os.listdir(SRC)):
        if not (f.startswith("act") and f.endswith(".txt")):
            continue
        key, song, rows = None, None, []
        for raw in open(os.path.join(SRC, f), encoding="utf-8"):
            l = raw.strip()
            if not l or l.startswith("#"):
                continue
            if l.startswith("== "):
                if key:
                    out[key] = (song, rows)
                key, song, rows = l[3:].split("|")[0].strip(), None, []
                order.append(key)
            elif l.startswith("@SONG"):
                song = l[5:].strip()
            elif l.startswith("@"):
                rows.append(("", f"[{l}]"))
            else:
                who, _, text = l.partition(": ")
                rows.append((who, text.replace(" / ", " / ")))
        if key:
            out[key] = (song, rows)
    return out, order


def label(key):
    m = re.fullmatch(r"m(\d\d)_(\w+)", key)
    if not m:
        return key
    kind = m.group(2)
    if kind in KINDS:
        return KINDS[kind]
    d = re.fullmatch(r"day(\d+)", kind)
    if d:
        return f"During the battle, day {d.group(1)}"
    return kind.replace("_", " ").title()


def main(out_path):
    sc, order = scenes()
    lines = ["# The Emerald Sun Campaign: dialogue for review", "",
             f"{sum(len(v[1]) for v in sc.values())} boxes in {len(sc)} scenes. Each box is two lines of at most 176 pixels (the lint checks it); `(h)` and `(s)` are happy and sad faces.", ""]
    if "prologue" in sc:
        lines += ["## Prologue", "", f"*song: {sc['prologue'][0]}, {len(sc['prologue'][1])} pages*", ""]
        lines += [f"> {t}" for _, t in sc["prologue"][1]] + [""]
    for n in range(1, 17):
        keys = [k for k in order if k.startswith(f"m{n:02d}_")]
        if not keys:
            continue
        lines += [f"## Mission {n}: {TITLES[n]}", ""]
        for k in keys:
            song, rows = sc[k]
            lines += [f"### {label(k)} (`{k}`, {len(rows)} boxes{', song ' + song if song else ''})", ""]
            for who, t in rows:
                lines.append(f"**{who}** {t}  " if who else f"_{t}_  ")
            lines.append("")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{len(sc)} scenes -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "devkit", "work", "campaign", "es", "ES_DIALOGUE.md"))
