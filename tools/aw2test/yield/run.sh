#!/bin/bash
# The end of a room's match, in each window: the winner sees VICTORY!, the player who yielded sees DEFEAT (the game's
# own screen, made on a scratch console: crate::result_view). Two scripts: the host yields on its turn (seat 0 loses),
# and the guest yields on its (seat 1 loses). Both peers' pictures must agree and the simulations stay identical
# (the runner's own checks), and at the VICTORY! screen (shot z08) the two seats' windows must differ. Look at the
# pictures: z08_peer0 / z08_peer1 in each output folder. Usage: run.sh <rom> <save> [out-dir]; needs
#   cargo build --release -p tango-gamesupport-aw2 --example aw2_netplay_script
set -e
ROM=$1; SAVE=$2; OUT=${3:-/tmp/yield}
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=${BIN:-$HERE/../../../target/release/examples/aw2_netplay_script}
mkdir -p "$OUT"
bad=0
for who in host guest; do
  AW2_ONLINE=1 "$BIN" "$ROM" "$SAVE" "$HERE/${who}_yields.txt" "$OUT/$who" | tee "$OUT/$who.log" | grep -E "agree|identical"
  # (the peers must agree on every seat's picture and the simulations stay identical)
  if grep -q "agree false\|identical: false" "$OUT/$who.log"; then echo "PEERS DISAGREE ($who yields)"; bad=1; fi
  if cmp -s "$OUT/$who/z08_peer0.bmp" "$OUT/$who/z08_peer1.bmp"; then echo "SAME picture in both windows ($who yields)"; bad=1; fi
done
[ $bad = 0 ] && echo "the two seats' windows differ at the result screen, as they should"
exit $bad
