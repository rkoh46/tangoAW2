---
name: aw2-add-unit
description: Add a custom unit to tangoAW2 (content kit; not built yet)
---

TODO: kit not built yet.

Until it exists: read docs/dev/README.md and CLAUDE.md, compose any art from AW2/DS assets read from the ROMs at runtime (never draw it, never commit game data), keep the engine data-driven, and ask the user before inventing a format.

A new unit must also be one the CPU uses: AW2's role code moves a unit by its role byte (record +0x1B), and a unit type AW2 never moves that way sits where it was built (a boat on a port blocks it). Read docs/dev/cpu-unit-use.md, give the unit a rule in `cpu_units.rs` where it needs one and an action test in `tools/aw2test/tests/test_cpu_unit_use.py` (`-k cpu_unit_use`).
