#!/bin/bash
# The turn lock of a room's match, proved: the same match twice, once with the seat that has no turn mashing every
# button (noise.txt) and once with nobody pressing (quiet.txt, the same frames). Every shot of both peers must be
# byte for byte the same. Usage: run.sh <rom> <save> [out-dir]; needs
#   cargo build --release -p tango-gamesupport-aw2 --example aw2_netplay_script
set -e
ROM=$1; SAVE=$2; OUT=${3:-/tmp/turn_lock}
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$HERE/../../../target/release/examples/aw2_netplay_script
for m in noise quiet; do
  AW2_ONLINE=1 "$BIN" "$ROM" "$SAVE" "$HERE/$m.txt" "$OUT/$m" | tail -1
done
bad=0
for f in "$OUT"/noise/*_peer*.bmp; do
  g=$OUT/quiet/$(basename "$f")
  if cmp -s "$f" "$g"; then :; else echo "DIFFERS: $(basename "$f")"; bad=1; fi
done
[ $bad = 0 ] && echo "turn lock holds: every shot is identical"
exit $bad
