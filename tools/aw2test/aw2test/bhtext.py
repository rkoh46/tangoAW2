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


def scene(key, lead=None, partner=None, bonds=()):
    """The texts the game holds for the scene: runs of rows by one speaker (and expression) merged, boxes joined with \\x0f."""
    texts, last, n = [], None, 0
    for who, mood, text in rows(key, lead, partner, bonds):
        face = (who, mood)
        if texts and face == last and n + 1 <= MERGE_BOXES:
            texts[-1] += "\x0f" + text
            n += 1
        else:
            texts.append(text)
            last, n = face, 1
    return texts


def clean(t):
    """As the dialogue tests clean a text: boxes and line breaks as spaces, pauses dropped."""
    return re.sub(r" +", " ", t.replace("\x0f", " ").replace("\r", " ").replace("\x0e", "")).strip()


def shown(key, lead=None, partner=None, bonds=()):
    """What a test that collects `text_shown()` (cleaned) sees for the scene."""
    return [clean(t) for t in scene(key, lead, partner, bonds)]


def boxes(key, lead=None, partner=None, bonds=()):
    """Every box of the scene one by one (merged texts split again): the cleaned text of each."""
    return [clean(b) for t in scene(key, lead, partner, bonds) for b in t.split("\x0f")]
