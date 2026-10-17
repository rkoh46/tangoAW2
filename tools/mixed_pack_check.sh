#!/bin/bash
# A room that mixes players with and without the Dual Strike pack must play the same console everywhere.
# Runs one harness script twice, as a peer WITH the pack in a match that lacks it (AW2_PACK_ONLY) and as a peer without the pack,
# and compares the console's per-tick state hashes (IWRAM, EWRAM; every 30 ticks ROM, VRAM, palette, OAM). Prints the differing
# regions (none = equal). usage: tools/mixed_pack_check.sh <aw2.gba> <dual-strike.nds> <script.txt> [out-dir]
set -e
ROM=$1; DS=$2; SC=$3; OUT=${4:-/tmp/mixed_pack_check}
B=$(dirname "$0")/../target/release/examples/aw2_room_teams
mkdir -p "$OUT"; rm -f "$OUT"/hA.txt "$OUT"/hB.txt
AW2_HASH_LOG="$OUT/hA.txt" TANGOAW2_DS_ROM="$DS" AW2_PACK_ONLY=1 "$B" "$ROM" "$OUT/oA" "$SC" > "$OUT/A.log" 2>&1 &
AW2_HASH_LOG="$OUT/hB.txt" "$B" "$ROM" "$OUT/oB" "$SC" > "$OUT/B.log" 2>&1 &
wait
python3 - "$OUT/hA.txt" "$OUT/hB.txt" <<'P'
import sys
a=[l.split() for l in open(sys.argv[1])];b=[l.split() for l in open(sys.argv[2])]
first={}
for x,y in zip(a,b):
    dx=dict(zip(x[1::2],x[2::2]));dy=dict(zip(y[1::2],y[2::2]))
    for k in dx:
        if dx[k]!=dy.get(k): first.setdefault(k,[]).append(int(x[0]))
for k,v in first.items(): print(k,len(v),'ticks differ, first',v[:6])
print('ticks',len(a),len(b),'DIFFERENT' if first or len(a)!=len(b) else 'EQUAL')
sys.exit(1 if first or len(a)!=len(b) else 0)
P
