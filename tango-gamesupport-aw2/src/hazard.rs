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

/// Writes the list the mission's eruption takes today to [`CELLS`] (x, y halfwords, 0xFFFF ends it) and returns the
/// mission's volcano, if it has one.
fn fill(core: &mut Core) -> Option<crate::campaign_model::VolcanoDef> {
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
    spec
}

/// At the eruption call: the cells it takes now (r0) and its damage (r1).
pub fn eruption(core: &mut Core) {
    let spec = fill(core);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, CELLS as i32);
    cpu.set_gpr(1, spec.as_ref().map_or(0, |v| v.damage as i32 * 10));
}

/// The call of the turn-start loop that plays the eruption's show (`sub_0803F2B8(x, y, cells, ..)`: the camera visits
/// each cell of its list and a boulder lands on it). It reads AW2's own list for AW2's own mission (r2), so the rocks
/// fell on cells of AW2's map while the damage went to the mission's: the same list is handed to both.
pub const SHOW_CALL: u32 = 0x0803_EC52;
pub fn show(core: &mut Core) {
    fill(core);
    core.gba_mut().cpu_mut().set_gpr(2, CELLS as i32);
}
