#!/bin/sh
# The ROM-gated tests of the AI debug channel: the channel being on must not change the console's state hashes.
# Runs only when an Advance Wars 2 ROM is at hand: TANGOAW2_AW2_ROM, else the ROMs folder of the usual profile.
# Usage (from the repo root): tools/aidebug/rom_tests.sh   -> prints nothing when it passes, FAIL ... and exits 1 otherwise.
command -v cargo >/dev/null 2>&1 || PATH="$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin:$PATH"
ROM="${TANGOAW2_AW2_ROM:-$HOME/Documents/TangoAW2/roms/Advance_wars_2.gba}"
[ -f "$ROM" ] || { echo "rom_tests: no ROM ($ROM), skipped" >&2; exit 0; }
TANGOAW2_AW2_ROM="$ROM" cargo test --release -p tango-gamesupport-aw2 --lib the_channel_on -- --ignored >/tmp/aidebug_rom_tests.log 2>&1 \
  || { echo "FAIL the_channel_on_does_not_change_the_state_hashes (see /tmp/aidebug_rom_tests.log)"; exit 1; }
