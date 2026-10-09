#!/usr/bin/env python3
"""Lint the BH Campaign's dialogue files (tango-gamesupport-aw2/src/bh_text/*.txt).

    python3 tools/bhtext/lint.py                 # every file
    python3 tools/bhtext/lint.py act3            # one file (act1 act2a act2b act3 act4a act4b act5 act5ba act5bb story)
    python3 tools/bhtext/lint.py --counts        # box counts per scene

Checks the same grammar as src/bh_text.rs, and the box size against AW2's font: every
row is one box of at most two lines of at most 176 pixels (the width table is read from your
AW2 ROM, nothing of it is kept). Voice checks (warnings): Sturm never shouts or contracts,
Jugger speaks in capitals, the COs who never use contractions do not.
Exit status 1 when there is an error.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "tango-gamesupport-aw2", "src"))
ROM = os.environ.get("AW2TEST_ROM", os.path.expanduser("~/Documents/TangoAW2/roms/Advance_wars_2.gba"))
FILES = ["act1", "act2a", "act2b", "act3", "act4a", "act4b", "act5", "act5ba", "act5bb", "story"]
LIMIT = 176

CO_NAMES = {
    "STURM", "VON BOLT", "HAWKE", "KOAL", "KINDLE", "JUGGER", "FLAK", "LASH", "ADDER", "CLONE", "CLONE ANDY",
    "SONJA", "CRUMB CO", "ANDY", "NELL", "MAX", "OLAF", "SAMI", "GRIT", "KANBEI", "EAGLE", "DRAKE", "HACHI",
    "COLIN", "JESS", "SENSEI", "GRIMM", "JAVIER", "SASHA", "JAKE", "RACHEL",
}
OTHER_NAMES = {"NARRATION", "CRUMB", "MORTAR", "WICK", "SOLDIER", "SOLDIER OS", "SOLDIER BM", "SOLDIER GE", "SOLDIER YC", "[CO]", "[CO2]"}
ROSTER = ["STURM", "VON BOLT", "HAWKE", "KOAL", "KINDLE", "JUGGER", "FLAK", "LASH", "ADDER", "CLONE ANDY", "SONJA", "CRUMB CO"]
NO_CONTRACTIONS = {"STURM", "HAWKE", "KANBEI", "JUGGER", "SASHA", "JAVIER", "KOAL"}
CONTRACTION = re.compile(r"\b\w+(n't|'ll|'re|'ve|'m|'d)\b|\b(I|it|that|there|what|he|she|let|here|who)'s\b", re.I)

W = None


def widths():
    global W
    if W is None:
        d = open(ROM, "rb").read()
        W = d[0x4C36E4:0x4C36E4 + 256]
    return W


def px(s):
    w = widths()
    return sum(w[ord(c)] if ord(c) < 256 else 99 for c in s) + max(len(s) - 1, 0)


def lint_file(name, errors, warns, counts):
    path = os.path.join(SRC, "bh_text", name + ".txt")
    if not os.path.exists(path):
        errors.append(f"{name}: no such file")
        return {}
    scenes = {}
    key = None
    group = None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        l = raw.rstrip("\n").strip()
        where = f"{name}.txt:{n}"
        if not l or l.startswith("#"):
            continue
        if l.startswith("== "):
            h = l[3:]
            k, _, pool = h.partition("|")
            key = k.strip()
            if not re.fullmatch(r"m\d\d\w*|[a-z0-9_]+", key):
                errors.append(f"{where}: odd scene key {key!r}")
            if key in scenes:
                errors.append(f"{where}: scene {key} defined twice")
            scenes[key] = 0
            for c in [p.strip() for p in pool.split(",") if p.strip()]:
                if c not in CO_NAMES:
                    errors.append(f"{where}: unknown CO {c!r} in the pool")
            group = None
            continue
        if key is None:
            errors.append(f"{where}: row before the first scene header")
            continue
        if l.startswith("@"):
            word, _, rest = l[1:].partition(" ")
            if word in ("IF", "WITH", "PARTNER", "BOND"):
                for c in [p.strip() for p in rest.split(",")]:
                    if c not in CO_NAMES:
                        errors.append(f"{where}: unknown CO {c!r}")
                group = word
            elif word in ("OTHER", "END"):
                group = None if word == "END" else "OTHER"
            else:
                errors.append(f"{where}: unknown directive @{word}")
            continue
        i = l.find(": ")
        if i < 0:
            errors.append(f"{where}: not a row: {l!r}")
            continue
        head, text = l[:i], l[i + 2:].strip()
        m = re.fullmatch(r"(.*?)(?:\(([a-z])\))?", head)
        who, expr = m.group(1), m.group(2)
        if expr not in (None, "h", "s"):
            errors.append(f"{where}: unknown expression ({expr})")
        if who not in CO_NAMES and who not in OTHER_NAMES:
            errors.append(f"{where}: unknown speaker {who!r}")
        if who in ("[CO]", "[CO2]") and group is None and False:
            pass
        lines = text.split(" / ")
        if len(lines) > 2:
            errors.append(f"{where}: {len(lines)} lines in a box: {l!r}")
        for ln in lines:
            if not ln:
                errors.append(f"{where}: empty line: {l!r}")
            if any(ord(c) > 126 or ord(c) < 32 for c in ln):
                errors.append(f"{where}: character outside ASCII: {ln!r}")
                continue
            w = px(ln)
            if w > LIMIT:
                errors.append(f"{where}: {w}px > {LIMIT}: {ln!r}")
        # voice (warnings)
        plain = text.replace(" / ", " ")
        if who == "STURM" or (who in ("[CO]", "[CO2]") and False):
            if "!" in plain:
                warns.append(f"{where}: Sturm shouts: {plain!r}")
        if who in NO_CONTRACTIONS and CONTRACTION.search(plain):
            warns.append(f"{where}: {who} uses a contraction: {plain!r}")
        if who == "JUGGER" and re.search(r"[a-z]", plain):
            warns.append(f"{where}: Jugger in lower case: {plain!r}")
        if who == "SONJA" and re.search(r"\bdears?\b", plain, re.I):
            warns.append(f"{where}: Sonja says dear: {plain!r}")
        scenes[key] += 1
    return scenes


def used_keys():
    keys = set()
    for fn in os.listdir(SRC):
        if fn.endswith(".rs"):
            s = open(os.path.join(SRC, fn)).read()
            keys |= set(re.findall(r'bh_text::(?:scene|lines|pages)\(\s*"(\w+)"', s))
            keys |= set(re.findall(r'\b(?:scene|lines|pages|txt)\(\s*"(\w+)"\s*\)', s))
    return keys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    names = args or FILES
    errors, warns = [], []
    allscenes = {}
    for n in names:
        sc = lint_file(n, errors, warns, None)
        for k, v in sc.items():
            if k in allscenes:
                errors.append(f"scene {k} is in two files")
            allscenes[k] = (n, v)
    if "--counts" in sys.argv:
        tot = 0
        for k, (n, v) in allscenes.items():
            print(f"{n:6} {k:28} {v:4}")
            tot += v
        print(f"total {tot} boxes in {len(allscenes)} scenes")
    if "--keys" in sys.argv or not args:
        used = used_keys()
        if used:
            for k in sorted(used - set(allscenes)):
                if not args:
                    errors.append(f"the code asks for scene {k!r}, no file defines it")
            for k in sorted(set(allscenes) - used):
                if not args:
                    warns.append(f"scene {k!r} is defined but the code never asks for it")
    for w in warns:
        print("warn:", w)
    for e in errors:
        print("ERROR:", e)
    total = sum(v for _, v in allscenes.values())
    print(f"{len(allscenes)} scenes, {total} boxes, {len(errors)} errors, {len(warns)} warnings")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
