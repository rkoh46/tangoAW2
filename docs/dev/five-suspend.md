# Suspend and save for five-army battles

AW2's suspend block (`sub_08016F38`, 0xE28 bytes) holds four armies: the player table's slots 0..4 from the original table (`0x02023284`) and 4 x 51 unit records read at 64-unit strides. In a five-army battle
(`five.rs`: unit ids 51 an army, a moved player table with a fifth slot) none of that is the battle: the stride is wrong and army 5 is not in it. So AW2's part of the block is written as it is (it is only used to
carry the map id, the day, the weather and the other state tangoAW2 puts in its tail) and a **five-army record** follows it. The Save item is AW2's own (the old hook that hid it in five-army games is gone).

## The record

After whatever else the block carries (the pairs' tail, the stage's mark), `suspend.rs::five_save` writes:

| bytes | what |
| --- | --- |
| 4 | the mark `FIV5` |
| 2 | the state's length |
| 4 | an FNV-1a hash of AW2's part of the block (+0 .. +0xDAC): the battle the record belongs to |
| 1 | `FIVE_ON` (1 Versus, 2 a campaign's five-army mission) |
| 8 | army 5's picks and the five-army switches (`0x02030200..`) |
| 0xE0 | the Teams screen's record (`0x02030300`) |
| 6 x 0x3C | the player table as the game has it now (funds, CO, power meters, takeover counts, controllers) |
| 2 + 13 n | the live units: each its id (1..254) and its 12 bytes |

Typical size 1.1 KB (a 5P Versus map with 40 units) to 2.5 KB (M31's gauntlet); the worst case (every unit id in use) is 3.9 KB (`suspend::tests::a_five_army_record_fits_the_slot`: the slot never passes two sectors).
No new RAM: the record is built in AW2's staging buffer (`0x02000000`, 0x2000 bytes) after the block. Flash: a five-army game's slot takes **two sectors** instead of one (the writer splits a record in 0xFAD-byte parts,
as a two-front mission's does), 4.4 to 6.1 KB measured; every other game's slot is unchanged, byte for byte. A save needs one free sector more than before for a five-army game.

## Continue

AW2 loads its part with the five-army patches off (`five::before_resume`, as for any game). At the end of its apply (`suspend::APPLIED`, first in the chain) `five_restore` reads the record: it must carry the mark and
the hash of the block just read (a record left in the buffer by another game is skipped, and the mark is cleared once taken), then `five::restore_saved` switches the game back to five-army (`FIVE_ON`, the patches in the
ROM image), writes the player table, the switches and the Teams record, clears the unit table and writes the live units, sets the current army's unit base (`0x03003F2C`: 51 an army; AW2's apply made it 64 an army: the
first resumed turn could not select units) and rebuilds the map's two unit planes from the units. All before the first frame of play.

## Coverage and tests (`tools/aw2test/tests/test_five_suspend.py`)

- offline Versus: a design map (`five_versus_suspend_and_resume`, both modes) and tangoAW2's own 5P maps Five Seas and Black Rampart (`five_versus_builtin_maps_suspend_and_resume`);
- BH2 M31's gauntlet saved after each of three takeovers and continued each time, then played on to the stage switch (`bh2_m31_gauntlet_suspend_and_resume`); stage 2 saved (`bh2_m31_stage_two_suspend_and_resume`);
- BH Campaign M28 (`bh_m28_suspend_and_resume`);
- a stale record: the five-army record is put in the buffer where a two-army game's reader would look and the two-army game comes back untouched (`five_record_never_leaks_into_another_battle`).
Each compares the unit table, the six player slots, every cell's owner, the day and the army byte for byte before and after.
Not covered: the War Room (its maps have up to four armies); online play never suspends (rooms rejoin) and is untouched: the record is written only by the map menu's Save and read only by Continue.

## Tools

`aw2dev save inspect FILE.sav` (`devkit/aw2/savelib.py`) lists the suspended games of a save: slot, size, AW2's block (day, map), the marks after it, the five-army record (place, `FIVE_ON`, each army's funds /
colour / control / CO / unit count, whether its hash matches the block) and the Flash sectors used and free. `--json` for scripts. Test: `save_inspect_reads_the_five_army_record`.
