import re, sys, collections
for p in sys.argv[1:]:
    fr = 0; sk = collections.OrderedDict(); lk = {}
    for l in open(p):
        m = re.match(r"@frame (\d+)", l)
        if m: fr = int(m.group(1)); continue
        m = re.match(r"ds_tilt skip line (\d+)", l)
        if m: sk.setdefault(int(m.group(1)), []).append(fr)
        m = re.match(r"ds_tilt leak (\d+)", l)
        if m and int(m.group(1)) > 0: lk[fr] = int(m.group(1))
    def rng(v):
        out = []; 
        for f in sorted(v):
            if out and f - out[-1][1] <= 1: out[-1][1] = f
            else: out.append([f, f])
        return ["%d-%d" % (a, b) for a, b in out]
    print(p.split("/")[-1], "skips", {k: rng(v) for k, v in sk.items()}, "leaks", rng(lk))
