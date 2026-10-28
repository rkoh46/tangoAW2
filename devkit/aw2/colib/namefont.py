"""The CO name graphic (48 x 16, six 8 x 16 sprites): a blocky italic-free capital-and-lowercase face of our own (original art, GPL-3.0-or-later) in the style of AW2's names: white fill (index 1),
a dark outline (15) and a drop shadow (14), drawn with the fixed name palette (0x080F6164). The letters the Emerald Sun names and Asuka need: A C K L V, a e i k l o r s u v."""
import numpy as np

G = {
    "A": ["..111..", ".11111.", "11...11", "11...11", "11...11", "11...11", "1111111", "1111111", "11...11", "11...11", "11...11"],
    "C": [".11111.", "1111111", "11...11", "11.....", "11.....", "11.....", "11.....", "11.....", "11...11", "1111111", ".11111."],
    "K": ["11...11", "11..11.", "11.11..", "1111...", "111....", "111....", "1111...", "11.11..", "11..11.", "11...11", "11...11"],
    "L": ["11.....", "11.....", "11.....", "11.....", "11.....", "11.....", "11.....", "11.....", "11.....", "1111111", "1111111"],
    "V": ["11...11", "11...11", "11...11", "11...11", "11...11", "11...11", "11...11", ".11.11.", ".11.11.", "..111..", "...1..."],
    "o": ["......", "......", "......", ".1111.", "111111", "11..11", "11..11", "11..11", "11..11", "111111", ".1111."],
    "k": ["11....", "11....", "11....", "11..11", "11.11.", "1111..", "1111..", "11.11.", "11..11", "11..11", "11..11"],
    "l": ["111", "111", "111", "111", "111", "111", "111", "111", "111", "111", "111"],
    "i": ["111", "111", "...", "111", "111", "111", "111", "111", "111", "111", "111"],
    "a": ["......", "......", "......", ".1111.", "111111", ".....11", ".11111", "111111", "11..11", "111111", ".11111"],
    "e": ["......", "......", "......", ".1111.", "111111", "11..11", "111111", "111111", "11....", "111111", ".1111."],
    "r": [".....", ".....", ".....", "11.11", "1111.", "111..", "11...", "11...", "11...", "11...", "11..."],
    "s": ["......", "......", "......", ".11111", "111111", "11....", ".1111.", "..1111", "....11", "111111", "11111."],
    "u": ["......", "......", "......", "11..11", "11..11", "11..11", "11..11", "11..11", "11..11", "111111", ".1111."],
    "v": ["......", "......", "......", "11..11", "11..11", "11..11", "11..11", ".1111.", ".1111.", "..11..", "..11.."],
}


def name_grid(text, gap=1):
    """-> 16 x 48 palette indexes of the name: fill 1, outline 15, shadow 14, centred."""
    cols = []
    for ch in text:
        g = G[ch]
        w = len(g[0])
        for x in range(w):
            cols.append([1 if g[y][x] == "1" else 0 for y in range(11)])
        cols.extend([[0] * 11] * gap)
    cols = cols[:-gap]
    w = len(cols)
    if w + 2 > 48:
        raise ValueError(f"{text!r} is {w + 2} px, the name graphic has 48")
    fill = np.zeros((16, 48), bool)
    x0, y0 = (48 - w) // 2, 2
    for x, c in enumerate(cols):
        for y, v in enumerate(c):
            if v:
                fill[y0 + y, x0 + x] = True
    out = np.zeros((16, 48), np.uint8)
    out[fill] = 1
    shadow = np.zeros_like(fill)
    for dx, dy in ((1, 1), (1, 0), (0, 1)):
        shadow |= np.roll(np.roll(fill, dy, 0), dx, 1)
    ring = np.zeros_like(fill)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
        ring |= np.roll(np.roll(fill, dy, 0), dx, 1)
    out[shadow & ~fill] = 14
    out[ring & ~fill & ~shadow] = 15
    # the outline round the shadow too
    both = fill | shadow
    ring2 = np.zeros_like(fill)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring2 |= np.roll(np.roll(both, dy, 0), dx, 1)
    out[ring2 & ~both & (out == 0)] = 15
    return out


NAME_PALETTE = [0x6af7, 0x7fff, 0x56bf, 0x461f, 0x41b3, 0x67ff, 0x37ff, 0x3ed3, 0x7f5a, 0x7f53, 0x666a, 0x46ff, 0x7c1f, 0x6338, 0x4986, 0x00a0]


def name_rgb():
    return [(((c & 31) * 255) // 31, (((c >> 5) & 31) * 255) // 31, (((c >> 10) & 31) * 255) // 31) for c in NAME_PALETTE]
