"""python3 fx/perf.py LOG...: per-picture times (TANGOAW2_TILT_US_LOG): average, 99th percentile, worst (ms) and how many are over 6 ms."""
import re, sys
for p in sys.argv[1:]:
    v = sorted(int(m.group(1)) for l in open(p) for m in [re.match(r"ds_tilt us (\d+)$", l.strip())] if m)
    if v: print(f"{p.split('/')[-1]}: {len(v)} pictures avg {sum(v)/len(v)/1000:.2f} ms  p99 {v[int(len(v)*.99)]/1000:.2f}  worst {v[-1]/1000:.2f}  over 6ms {sum(1 for x in v if x > 6000)}")
