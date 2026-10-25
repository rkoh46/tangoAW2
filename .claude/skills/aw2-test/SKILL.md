---
name: aw2-test
description: Pick and run the right tangoAW2 checks for a change (lib tests, offline suite, live runs, audits, aw2test). Use before calling any Rust or UI change done.
---

1. Build fresh: `./aw2dev build --all` (aw2dev refuses stale binaries; rebuild after every merge).
2. Choose by what changed (full table: docs/dev/testing.md):
   - game/session logic: `./aw2dev test`
   - waiting view, `fog_view.rs`, `pvp.rs`, `result_view.rs`: `./aw2dev suite` (must end `suite done bad=0`; do not rebuild while it runs), then `./aw2dev live moveview --fog on --local` and `--fog off` from the SAME build, `./aw2dev check latest`
   - new/changed text or screens: `./aw2dev audit text` and view the BMPs
   - maps: `./aw2dev audit maps`
   - rules, saves, DS content: `python3 tools/aw2test/run.py`
   - online/session: skill aw2-online-debug
3. LOOK at pictures: `./aw2dev sheet latest --around 0 --kind move --strip`. A pass on a checker is not proof; check `meta.json` build stamps match across compared runs.
4. A small fix the user will playtest: skip suites; `./aw2dev build --release && ./aw2dev install-mac`.
5. Respect politeness (one live run at a time, local signalling, never close the user's app, delete captures and `target/` when done).
6. Waiting for a long run: `./aw2dev wait PID` or `./aw2dev wait LOG --text "passed in"` (never `until ! pgrep -f ...`: it matches its own shell and never ends).
