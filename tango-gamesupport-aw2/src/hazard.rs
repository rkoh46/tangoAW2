//! A custom campaign mission's volcano as a neutral hazard
//! ([`crate::campaign_model::VolcanoDef`]). The map carries a Volcano
//! structure so AW2's turn-start loop runs the eruption (`0x0803EE3C`, the
//! call [`crate::ds_campaign_rules::eruption`] hooks): this gives it the
//! mission's cells (any army's unit there is hit) on its schedule, none on
//! the days between, and the damage. The cells are marked from the day before
//! with a pulsing orange mark on each (sprites, [`flush_sprites`]).

use mgba::core::Core;

const CELLS: u32 = 0x0203_F708;
const CELLS_LEN: usize = 12;
const DAY: u32 = 0x0300_4080;
const MAP_POINTER: u32 = 0x0849_9590;
/// Free OBJ tiles in a battle (772..799) and a palette bank nothing uses.
const TILE: u32 = 772;
const BANK: u16 = 4;
const OBJ_TILES: u32 = 0x0601_0000;
const PAL_BUFFER: u32 = 0x0300_20C0;
const PAL_RAM: u32 = 0x0500_0000;

/// At the eruption call: the cells it takes now (r0) and its damage (r1).
pub fn eruption(core: &mut Core) {
    let Some(v) = crate::ds_campaign::volcano_spec(core) else { return };
    let day = core.raw_read_16(DAY, -1);
    let mut at = CELLS;
    if v.erupts(day) {
        for &(x, y) in v.cells.iter().take(CELLS_LEN) {
            core.raw_write_16(at, -1, x as u16);
            core.raw_write_16(at + 2, -1, y as u16);
            at += 4;
        }
    }
    core.raw_write_16(at, -1, 0xFFFF);
    core.raw_write_16(at + 2, -1, 0);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, CELLS as i32);
    cpu.set_gpr(1, v.damage as i32 * 10);
}

/// 16x16 mark: a hollow diamond with a dot, palette indices 1 black, 2 orange, 3 yellow.
fn mark_pixels(phase: bool) -> Vec<u8> {
    let mut px = vec![0u8; 256];
    for y in 0..16i32 {
        for x in 0..16i32 {
            let d = (x - 8).abs() + (y - 8).abs();
            px[(y * 16 + x) as usize] = if d == 7 || d == 8 {
                1
            } else if d == 5 || d == 6 {
                if phase { 3 } else { 2 }
            } else if d <= 1 {
                2
            } else {
                0
            };
        }
    }
    px
}

fn to_tiles(px: &[u8]) -> Vec<u8> {
    let mut out = vec![0u8; 128];
    for t in 0..4usize {
        let (tx, ty) = (t % 2, t / 2);
        for r in 0..8 {
            for c in 0..8 {
                out[32 * t + 4 * r + c / 2] |= (px[(8 * ty + r) * 16 + 8 * tx + c] & 15) << (4 * (c & 1));
            }
        }
    }
    out
}

fn write_if_changed(core: &mut Core, at: u32, bytes: &[u8]) {
    let mut now = vec![0u8; bytes.len()];
    core.raw_read_range(at, -1, &mut now);
    if now != bytes {
        core.raw_write_range(at, -1, bytes);
    }
}

/// At the sprite flush in a battle: the cells of the next day's eruption,
/// marked (all the day before it, pulsing).
pub fn flush_sprites(core: &mut Core, at: u32, end: u32) -> u32 {
    if std::env::var_os("NO_HAZARD").is_some() {
        return at;
    }
    let Some(v) = crate::ds_campaign::volcano_spec(core) else { return at };
    if core.raw_read_32(0x0300_0000, -1) != 0x0802_2049 {
        return at;
    }
    let day = core.raw_read_16(DAY, -1);
    if !v.erupts(day + 1) {
        return at;
    }
    // (the mark pulses: a visual only, never read by the game)
    static FRAMES: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
    let pulse = (FRAMES.fetch_add(1, std::sync::atomic::Ordering::Relaxed) >> 4) & 1 != 0;
    for base in [PAL_BUFFER, PAL_RAM] {
        let mut pal = [0u8; 32];
        for (i, c) in [(1usize, 0x0000u16), (2, 0x021F), (3, 0x03FF)] {
            pal[2 * i..2 * i + 2].copy_from_slice(&c.to_le_bytes());
        }
        write_if_changed(core, base + 0x200 + 32 * BANK as u32, &pal);
    }
    write_if_changed(core, OBJ_TILES + 32 * TILE, &to_tiles(&mark_pixels(pulse)));
    let map = core.raw_read_32(MAP_POINTER, -1);
    let (sx, sy) = (core.raw_read_16(map + 4, -1) as i16 as i32, core.raw_read_16(map + 6, -1) as i16 as i32);
    let mut at = at;
    for &(x, y) in &v.cells {
        let (px, py) = (x as i32 * 16 - sx, y as i32 * 16 - sy);
        if at + 8 > end || !(-16..240).contains(&px) || !(-16..160).contains(&py) {
            continue;
        }
        core.raw_write_16(at, -1, py as u16 & 0xFF);
        core.raw_write_16(at + 2, -1, (px as u16 & 0x1FF) | 1 << 14);
        core.raw_write_16(at + 4, -1, TILE as u16 | BANK << 12 | 1 << 10);
        core.raw_write_16(at + 6, -1, 0);
        at += 8;
    }
    at
}
