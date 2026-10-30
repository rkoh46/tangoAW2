---
name: aw2-add-mode
description: Add a custom game mode to tangoAW2 (a gauntlet, staged battles, a new rule set); start from the engine pieces the campaigns already use
---

There is no mode kit yet. Build a new mode on the engine pieces that already exist instead of mission-specific code, and grow the kit as you go (docs/dev entry, aw2dev tool, harness test, this skill).

Engine pieces to reuse (all data on a `MissionDef`, mission-agnostic):
- **Gauntlet** (docs/dev/gauntlet.md): armies off the battlefield until the line before falls. `MissionDef::hidden` (army, HQ cell, zone), `sleepers` (which HQs must fall first), `cut_off` (a fallen line earns nothing), `Cond::LineFallen`, `Action::Reveal`; put the wave (`Action::Spawn`) and its funds in the same trigger as the reveal. A map header `hidden 2 3 4` lets the map leave out those armies' HQs. Worked example: `bh2_campaign::bh2_31` (`wake`, `fell`, `war_chest`). The user wants this reused for a brand-new mode.
- **Stages** (docs/dev/stages.md): the same battle moves on to another map (`Action::NextStage`, `MissionDef::stages`), with carry-over and suspend.
- **Five-army suspend** (docs/dev/five-suspend.md): battles with five armies save and continue.
- Triggers, scenes, spawns and held HQs: docs/dev/bh2-maps.md, docs/dev/campaign-scenes.md.

Checks every mode needs (copy the M31 tests in tools/aw2test/tests/test_bh2_*.py): hidden armies absent and turnless, each reveal, a rout before the HQ falls, suspend and resume byte for byte after each reveal, online determinism (bump `inspect::SIM_VERSION` when the simulation changes). Pictures: `aw2dev campaign playthrough ... --waves` (docs/dev/playthrough.md).

Rules: compose any art from AW2/DS assets read from the ROMs at runtime (never draw it, never commit game data), keep the engine data-driven, and ask the user before inventing a format or the mode's menu entry.
