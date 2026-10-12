import sys, collections
def load(path):
    frames, cur = {}, None
    for l in open(path):
        if l.startswith("@frame"):
            cur = int(l.split()[1]); frames[cur] = []
        else:
            frames[cur].append(tuple(int(x) for x in l.split()))
    return frames
if __name__ == "__main__":
    fr = load(sys.argv[1]); ks = sorted(fr)
    base = set()
    for f in ks[:int(sys.argv[2]) if len(sys.argv) > 2 else 5]:
        base |= {(s[6], s[7], s[5], s[3], s[4]) for s in fr[f]}
    seen = collections.OrderedDict()
    for f in ks:
        for s in fr[f]:
            k = (s[6], s[7], s[5], s[3], s[4], s[8])
            if k[:5] in base: continue
            seen.setdefault(k, [f, f, 0]); seen[k][1] = f; seen[k][2] += 1
    for k, (a, b, n) in seen.items():
        print(f"tile {k[0]} pal {k[1]} mode {k[2]} shape {k[3]} size {k[4]} pri {k[5]}  frames {a}-{b} n={n}")
