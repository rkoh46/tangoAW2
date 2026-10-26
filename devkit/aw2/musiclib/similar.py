"""Originality check (`aw2dev sound similar`, docs/dev/music-kit.md): how much a song of ours resembles another song, by interval sequences and rhythm.

Pure functions over note lists `[(tick, key)]` (one melodic line a track: the top note of a chord). Three scores, on every pair of one of our tracks and one of theirs:
  * the longest run of notes whose **intervals** match exactly (transposition does not matter), counting only informative runs (3 or more distinct pitches: a repeated
    note or a two-note rattle is in everything);
  * the longest run whose **rhythm and contour** match (the same gaps between onsets, in 6-tick steps, and the same up / down / same steps), informative when the run has both
    two kinds of gap and two kinds of step;
  * the share of our bars (of 4 or more notes) that match one of their bars in onset pattern (Jaccard 0.9 of the sixteenth grid) AND interval sequence.
`verdict` fails a pair when a run is 6 notes or more, a rhythm+contour run is 8 or more, or the bar share is 20% or more.
The other song is read from the ROM for the comparison only; nothing of it is written anywhere."""

RUN_NOTES = 6          # an exact interval run of this many notes fails
CONTOUR_NOTES = 8      # a rhythm + contour run of this many notes fails
SEARCH_RUN = 4         # shorter runs are not searched for (so the score reports the longest from 4 notes up)
SEARCH_CONTOUR = 6
BAR_SHARE = 0.20       # this share of our bars matching a bar of theirs fails
BAR_TICKS = 96
GRID = 6


def line(notes):
    """[(tick, key)] sorted, one note a tick (the highest)."""
    top = {}
    for t, k in notes:
        if t not in top or k > top[t]:
            top[t] = k
    return sorted(top.items())


def intervals(ln):
    return [b[1] - a[1] for a, b in zip(ln, ln[1:])]


def _pitches(start, ivs):
    p, out = start, {start}
    for d in ivs:
        p += d
        out.add(p)
    return out


def longest_interval_run(ours, theirs):
    """Notes in the longest informative common run of intervals (0 if none reaches 3 notes), with the position in each."""
    a, b = intervals(ours), intervals(theirs)
    k = SEARCH_RUN - 1
    index = {}
    for j in range(len(b) - k + 1):
        w = tuple(b[j:j + k])
        if len(_pitches(0, w)) >= 3:
            index.setdefault(w, []).append(j)
    best = (0, None, None)
    for i in range(len(a) - k + 1):
        for j in index.get(tuple(a[i:i + k]), ()):
            n = k
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            if n + 1 > best[0]:
                best = (n + 1, i, j)
    return best


def _contour_items(ln):
    out = []
    for i in range(1, len(ln) - 1):
        gap = max(1, round((ln[i + 1][0] - ln[i][0]) / GRID))
        step = ln[i][1] - ln[i - 1][1]
        out.append((gap, (step > 0) - (step < 0)))
    return out


def longest_contour_run(ours, theirs):
    """Notes in the longest common run of (gap to the next onset, direction of the step into the note), informative when it has two gaps and two directions."""
    a, b = _contour_items(ours), _contour_items(theirs)
    k = SEARCH_CONTOUR
    index = {}
    for j in range(len(b) - k + 1):
        w = tuple(b[j:j + k])
        if len({g for g, _ in w}) >= 2 and len({s for _, s in w}) >= 2:
            index.setdefault(w, []).append(j)
    best = 0
    for i in range(len(a) - k + 1):
        for j in index.get(tuple(a[i:i + k]), ()):
            n = k
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            best = max(best, n + 2)
    return best


def _bars(ln):
    bars = {}
    for t, k in ln:
        bars.setdefault(t // BAR_TICKS, []).append((t % BAR_TICKS, k))
    return bars


def bar_share(ours, theirs):
    """The share of our bars with 4 or more notes that match one of their bars: onset sets alike (Jaccard >= 0.9 on the sixteenth grid) and the same intervals."""
    ob, tb = _bars(ours), _bars(theirs)
    cand = []
    for notes in tb.values():
        if len(notes) >= 4:
            cand.append((frozenset(t // GRID for t, _ in notes), tuple(b[1] - a[1] for a, b in zip(notes, notes[1:]))))
    mine = [n for n in ob.values() if len(n) >= 4]
    if not mine:
        return 0.0
    hit = 0
    for notes in mine:
        on = frozenset(t // GRID for t, _ in notes)
        iv = tuple(b[1] - a[1] for a, b in zip(notes, notes[1:]))
        if len(set(iv)) < 2:
            continue
        for on2, iv2 in cand:
            if iv == iv2 and len(on & on2) / len(on | on2) >= 0.9:
                hit += 1
                break
    return hit / len(mine)


def compare(ours, theirs):
    """The three scores of one pair of lines: dict(run, contour, bars)."""
    return dict(run=longest_interval_run(ours, theirs)[0], contour=longest_contour_run(ours, theirs), bars=bar_share(ours, theirs))


def verdict(s):
    """The reasons a pair of scores fails (empty: it passes)."""
    bad = []
    if s["run"] >= RUN_NOTES:
        bad.append(f"a run of {s['run']} notes with the same intervals")
    if s["contour"] >= CONTOUR_NOTES:
        bad.append(f"a run of {s['contour']} notes with the same rhythm and contour")
    if s["bars"] >= BAR_SHARE:
        bad.append(f"{s['bars']:.0%} of the bars match")
    return bad
