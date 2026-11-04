---
name: aw2-add-weather
description: Add or change a weather (rain, snow, sandstorm, per-commander weather) in tangoAW2; no dedicated aw2dev tool yet, so this lists the code, tests and checks to use (planned kit command)
---

Status: **planned kit**. There is no the planned weather kit command command yet; the first real weather feature adds it (devkit/CONTRIBUTING-KIT.md). Until then:
1. Rules: Dual Strike's weather rules with the pack on (`ds_weather.rs`: snow doubles fuel use except for Olaf's army, rain lowers vision and brings fog) and the fourth weather (`sandstorm.rs`); with the pack off everything is AW2's own. The forecast byte is NEXT_WEATHER (0x03003FEE; while rain is forecast it forces fog every frame, so clear it when taking fog-off pictures).
2. A mission sets its weather in its `MissionDef` (`look` and weather: `aw2dev bh2 check` lists each BH2 mission's look, weather and fog); per-commander weather has no action yet (docs/dev/bh2-maps.md "Hooks left open").
3. The CPU reacts to weather and biome: `test_cpu_weather_biome.py`; Silver Nova's: `test_es_weather.py`; plain behaviour: `test_weather.py`, `test_biome.py`.
4. Art (rain/snow/sand overlays) is read from the DS pack at run time; check AW2, DS + tilt and DS flat looks.
5. Checks: `./aw2dev test`, `python3 tools/aw2test/run.py -k weather --mode ds`, and look at the pictures; online peers must agree, so bump `inspect::SIM_VERSION` for a rule change.
6. Grow the kit: add the planned weather kit command (the same turn in each weather, with fuel and vision numbers) and rewrite this skill around it.
