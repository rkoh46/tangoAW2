"""python3 fx/jerk.py LOG [FIRST_FRAME]: the 24-wide mover board's step per frame (cells); a step that is not the steady one is a jerk."""
import re, sys, collections
fr = 0; pos = {}
for l in open(sys.argv[1]):
    m = re.match(r"@frame (\d+)", l)
    if m: fr = int(m.group(1)); continue
    m = re.match(r"ds_tilt: bb foot \(([\d.-]+), ([\d.-]+)\) 24x(\d+) rank (\d+) last (\w+) tag (.*?) whitish (\d+) at \((-?\d+), (-?\d+)\)", l)
    if m: pos[fr] = (float(m.group(1)), float(m.group(2)))
steps = collections.Counter(); bad = []
for f in sorted(pos):
    if f - 1 in pos and f - 2 in pos:
        d = (round(pos[f][0] - pos[f-1][0], 2), round(pos[f][1] - pos[f-1][1], 2))
        d0 = (round(pos[f-1][0] - pos[f-2][0], 2), round(pos[f-1][1] - pos[f-2][1], 2))
        steps[d] += 1
        if max(abs(d[0]), abs(d[1])) > 0.3 or (max(abs(d[0]), abs(d[1])) > 0 and d != d0 and max(abs(d0[0]), abs(d0[1])) > 0 and abs(abs(d[0]) + abs(d[1]) - abs(d0[0]) - abs(d0[1])) > 0.15):
            bad.append((f, d0, d))
print(len(pos), "frames with a mover; steps", steps.most_common(8)); print(len(bad), bad[:30])
