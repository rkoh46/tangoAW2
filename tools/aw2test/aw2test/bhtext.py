"""The BH Campaign's dialogue files (tango-gamesupport-aw2/src/bh_text/*.txt) as the tests see them.

`scene(key, lead=..., partner=...)` is what the game shows a player leading `lead` (a CO name such as "STURM") with
`partner` (or None): the rows of the scene whose groups apply, runs of boxes by one speaker merged the way the
compiler merges them (up to six boxes a text, boxes joined with \\x0f), as a list of texts exactly as the game
holds them (lines joined with \\r, boxes with \\x0f). `shown(key, ...)` is the same as `text_shown()` returns for
each text (what the dialogue tests collect), cleaned with `clean()`.
"""

import os
import re

from . import paths

DIR = os.path.join(paths.REPO, "tango-gamesupport-aw2", "src", "bh_text")
FILES = ["act1", "act2a", "act2b", "act3", "act4a", "act4b", "act5", "act5ba", "act5bb", "story"]
ROSTER = ["STURM", "VON BOLT", "HAWKE", "KOAL", "KINDLE", "JUGGER", "FLAK", "LASH", "ADDER", "CLONE ANDY", "SONJA", "CRUMB CO"]
BOND_ORDER = ["VON BOLT", "HAWKE", "KOAL", "KINDLE", "JUGGER", "FLAK", "LASH", "ADDER", "CLONE ANDY", "CRUMB CO"]
MERGE_BOXES = 6

_BOOK = None


def _norm(n):
    n = n.strip()
    return "CLONE ANDY" if n == "CLONE" else n


def book():
    """{key: (pool, [(group, who, mood, text)])} where group is (kind, [names]) and kind is None, IF, OTHER, WITH, PARTNER or BOND."""
    global _BOOK
    if _BOOK is not None:
        return _BOOK
    out = {}
    for name in FILES:
        key, pool, group = None, None, (None, [])
        for raw in open(os.path.join(DIR, name + ".txt"), encoding="utf-8"):
            l = raw.strip()
            if not l or l.startswith("#"):
                continue
            if l.startswith("== "):
                h = l[3:]
                k, _, p = h.partition("|")
                key = k.strip()
                pool = [_norm(x) for x in p.split(",") if x.strip()] or list(ROSTER)
                out[key] = (pool, [])
                group = (None, [])
                continue
            if l.startswith("@"):
                word, _, rest = l[1:].partition(" ")
                group = (None, []) if word == "END" else (word, [_norm(x) for x in rest.split(",") if x.strip()])
                continue
            head, _, text = l.partition(": ")
            m = re.fullmatch(r"(.*?)(?:\(([a-z])\))?", head)
            who, mood = _norm(m.group(1)), m.group(2) or ""
            out[key][1].append((group, who, mood, text.strip().replace(" / ", "\r").replace("{p}", "\x0e")))
    _BOOK = out
    return out


def keys():
    return list(book())


def rows(key, lead=None, partner=None, bonds=()):
    """The (who, mood, text) rows a player leading `lead` with `partner` sees (names: "STURM", "VON BOLT", "CLONE ANDY"...)."""
    pool, rs = book()[key]
    named = {n for (g, _, _, _) in rs if g[0] == "IF" for n in g[1]}
    out = []
    for (kind, names), who, mood, text in rs:
        if kind is None:
            if who == "[CO]":
                if lead is None or lead not in pool:
                    continue
                out.append((lead, mood, text))
            elif who == "[CO2]":
                if partner is None:
                    continue
                out.append((partner, mood, text))
            else:
                out.append((who, mood, text))
            continue
        if kind == "IF":
            ok = lead in names
            speaker = lead
        elif kind == "OTHER":
            ok = lead in pool and lead not in named
            speaker = lead
        elif kind == "WITH":
            hit = [n for n in names if n in (lead, partner)]
            ok, speaker = bool(hit), (hit[0] if hit else None)
        elif kind == "PARTNER":
            ok = partner is not None and partner in names
            speaker = partner
        elif kind == "BOND":
            ok = any(BOND_ORDER.index(n) in bonds for n in names if n in BOND_ORDER)
            speaker = None
        else:
            raise ValueError(kind)
        if not ok:
            continue
        if who == "[CO]":
            out.append((speaker, mood, text))
        elif who == "[CO2]":
            out.append((partner if kind != "PARTNER" else speaker, mood, text))
        else:
            out.append((who, mood, text))
    return out


TROOPERS = ("CRUMB", "MORTAR", "WICK", "SOLDIER")


def _face(who, mood):
    """The Speaker the compiler compares: a CO and expression; the trooper face (Crumb, Mortar, Wick, SOLDIER share it;
    expression kept); a soldier of another colour (no expression); the narration."""
    if who in TROOPERS:
        return ("T", mood)
    if who.startswith("SOLDIER "):
        return ("S", who)
    if who == "NARRATION":
        return ("N",)
    return ("C", who, mood)


def _lines(key):
    """The scene's lines as bh_text.rs builds them, for every CO at once: (face, condition, text), the condition one of
    None, ("only", co), ("partner", co), ("with", co), ("bond", name)."""
    pool, rs = book()[key]
    named = {n for (g, _, _, _) in rs if g[0] == "IF" for n in g[1]}
    out, i = [], 0
    while i < len(rs):
        g = rs[i][0]
        j = i
        while j < len(rs) and rs[j][0] == g:
            j += 1
        run = rs[i:j]
        kind, names = g
        if kind is None:
            for _, who, mood, text in run:
                if who == "[CO]":
                    out += [(_face(c, mood), ("only", c), text) for c in pool]
                elif who == "[CO2]":
                    out += [(_face(c, mood), ("partner", c), text) for c in pool]
                else:
                    out.append((_face(who, mood), None, text))
        else:
            if kind == "OTHER":
                cos = [c for c in pool if c not in named]
            else:
                cos = names
            cond = {"IF": "only", "OTHER": "only", "WITH": "with", "PARTNER": "partner", "BOND": "bond"}[kind]
            for c in cos:
                for _, who, mood, text in run:
                    speaker = c if who in ("[CO]", "[CO2]") else who
                    out.append((_face(speaker, mood), (cond, c), text))
        i = j
    return out


def scene(key, lead=None, partner=None, bonds=()):
    """The texts the game shows for the scene: the compiler merges runs of lines (same face, same condition, up to six
    boxes) before the lines are filtered for the player's CO, so a text never joins lines of different groups; boxes are
    joined with \\x0f."""
    merged = []
    for face, cond, text in _lines(key):
        if merged and merged[-1][0] == face and merged[-1][1] == cond and merged[-1][3] < MERGE_BOXES:
            merged[-1][2].append(text)
            merged[-1][3] += 1
        else:
            merged.append([face, cond, [text], 1])
    out = []
    for face, cond, texts, _ in merged:
        if cond is not None:
            kind, c = cond
            if kind == "only" and c != lead:
                continue
            if kind == "partner" and c != partner:
                continue
            if kind == "with" and c not in (lead, partner):
                continue
            if kind == "bond" and not (c in BOND_ORDER and BOND_ORDER.index(c) in bonds):
                continue
        out.append("\x0f".join(texts))
    return out


def clean(t):
    """As the dialogue tests clean a text: boxes and line breaks as spaces, pauses dropped."""
    return re.sub(r" +", " ", t.replace("\x0f", " ").replace("\r", " ").replace("\x0e", "")).strip()


def shown(key, lead=None, partner=None, bonds=()):
    """What a test that collects `text_shown()` (cleaned) sees for the scene."""
    return [clean(t) for t in scene(key, lead, partner, bonds)]


def boxes(key, lead=None, partner=None, bonds=()):
    """Every box of the scene one by one (merged texts split again): the cleaned text of each."""
    return [clean(b) for t in scene(key, lead, partner, bonds) for b in t.split("\x0f")]
