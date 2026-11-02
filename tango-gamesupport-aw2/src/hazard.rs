//! A custom campaign mission's volcano as a neutral hazard
//! ([`crate::campaign_model::VolcanoDef`]). The map carries a Volcano
//! structure so AW2's turn-start loop runs the eruption (`0x0803EE3C`, the
//! call [`crate::ds_campaign_rules::eruption`] hooks): this gives it the
//! mission's cells (any army's unit there is hit) on its schedule, none on
//! the days between, and the damage. Nothing is drawn on the cells beforehand
//! (the original game shows no warning either).

use mgba::core::Core;

const CELLS: u32 = 0x0203_F708;
const CELLS_LEN: usize = 12;
const DAY: u32 = 0x0300_4080;

/// At the eruption call: the cells it takes now (r0) and its damage (r1).
pub fn eruption(core: &mut Core) {
    // (a Volcano on a mission without `volcano` data erupts on no cell: the
    // game's own list is AW2's own mission's coordinates)
    let spec = crate::ds_campaign::volcano_spec(core);
    let day = core.raw_read_16(DAY, -1);
    let mut at = CELLS;
    if let Some(v) = spec.as_ref().filter(|v| v.erupts(day)) {
        for (x, y) in v.cells_on(day).into_iter().take(CELLS_LEN) {
            core.raw_write_16(at, -1, x as u16);
            core.raw_write_16(at + 2, -1, y as u16);
            at += 4;
        }
    }
    core.raw_write_16(at, -1, 0xFFFF);
    core.raw_write_16(at + 2, -1, 0);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, CELLS as i32);
    cpu.set_gpr(1, spec.as_ref().map_or(0, |v| v.damage as i32 * 10));
}
