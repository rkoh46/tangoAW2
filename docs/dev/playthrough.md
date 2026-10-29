# Playing a mission through (`aw2dev campaign playthrough`)

`aw2dev campaign playthrough bh2 31 [--player cpu|bot] [--days 60]` plays a BH2 mission from its CO screen to its end in the offline harness and writes `report.md`, `report.json` and `contact.png` under
`devkit/work/campaign/playthrough/bh2-m31-<player>/`. It builds on the harness's `autoplay` / `play` (the Emerald Sun `campaign sim` uses the same: the computer on every side, or the test player for the player's army):

- `--player cpu`: the game's computer plays every army, the player's too (every army the player commands is set to computer control each half second, a five-army mission's fifth and the player's army after a stage switch included);
- `--player bot`: the test player (`aw2test/bot.py`) plays the player's army through the pad, going for the HQs of the stage (a `HQS` row in `tests/test_playthrough.py`), the computer the others.

The report: the outcome and the reason, the days taken, the takeovers and stage switches reached (each with a picture), each army's units and funds at the start of every day, the stalls (three days in which nothing changed, or
the day limit) and a contact sheet of the key moments: the start, each takeover, the switch, a stall, the end. Missions need a `HQS` row (the HQs whose takeover is photographed, by stage). Test:
`playthrough_report_formats` (the Markdown); the run itself is opt-in (`AW2TEST_PLAY_MISSION`), like `campaign sim`.
