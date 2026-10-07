//! The Black Factory can be destroyed in Versus with the pack (not in the
//! campaigns, where it falls with its pipe seam).
//!
//! AW2 keeps the factory in its invention list (`0x02028360`, kind 7, hit
//! points 0), next to the Black Cannons (kinds 3 and 5, HP 99) the game
//! lets units attack. The kind's code is shared: an invention is a target
//! when [`TARGET_POSITION`] (`0x0803DFE0`) gives it one, and its HP byte
//! (+4) is above 0. In Versus with the pack:
//! - the factory is registered with [`HP`] hit points (a trap before the
//!   registration call, `0x0803E348`; the campaign's 0 stays);
//! - [`HP`] is 200, not the game's 99: the HP byte (+4) holds 200 and the
//!   game's own hit takes the same damage from it as from a Black Cannon's
//!   99 (a Tank's 16 leaves 184), so the factory takes twice as many hits;
//!   the terrain panel, which draws two digits, draws three ([`panel_heart`],
//!   [`panel_number`]);
//! - it is a target at the middle of its bottom row, as a Black Cannon is
//!   (one open square beside it: the middle door), and everything after
//!   that is the game's own for an invention: the attack menu, the damage
//!   (the game's, the same as against a Black Cannon), the HP in the terrain
//!   panel, the hit animation;
//! - at 0 HP it is destroyed as a Black Cannon is (the explosion, [`destroy`]),
//!   its entry staying in the list with 0 HP, which the game saves with the
//!   battle; it is drawn as the Black Cannon's wreck over its whole footprint ([`ruin`]) and its doors
//!   spawn nothing any more ([`destroyed`]). The battle goes on.

use mgba::core::Core;

/// Twice what a Black Cannon takes to destroy: a byte has room for it.
pub const HP: u8 = 200;
const FACTORY_KIND: u32 = 7;

const REGISTER: u32 = 0x0803_E348;
const TARGET_POSITION: u32 = 0x0803_DFE0;
/// The hit-and-destroy step (a process, proc in r3): the start of its
/// "no HP left" branch, which has a case for each kind but the factory.
const DESTROY_BRANCH: u32 = 0x0804_0818;
/// What a Black Cannon facing down does there: `(entry, proc)`.
const CANNON_DESTROYED: u32 = 0x0804_026C;
const STEP_EXIT: u32 = 0x0804_0879;
/// The factory's sprite call (r0 x, r1 y, r2 definition, r3 the owner's army
/// slot, which picks the building palette).
const FACTORY_SPRITE: u32 = 0x0803_FD54;
const INVENTIONS: u32 = 0x0202_8360;

fn in_scope(core: &Core) -> bool {
    crate::ds_weather::is_on(core) && crate::pvp::in_versus(core) && !crate::ds_campaign::active(core)
}

/// The factory's registration: its HP argument (`[sp + 4]`) is [`HP`].
fn register(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let sp = core.gba().cpu().gpr(13) as u32;
    core.raw_write_32(sp + 4, -1, HP as u32);
}

/// `sub_0803DFE0(entry, out)`: the position units aim at (and 1), or 0 for
/// an invention that cannot be attacked. The factory's is the middle of
/// its bottom row.
fn target_position(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (entry, out, lr) = (cpu.gpr(0) as u32, cpu.gpr(1) as u32, cpu.gpr(14) as u32);
    if (core.raw_read_16(entry + 2, -1) as u32 >> 6) & 15 != FACTORY_KIND {
        return;
    }
    let (x, y) = (core.raw_read_8(entry, -1) as u32, core.raw_read_8(entry + 1, -1) as u32);
    let height = (core.raw_read_8(entry + 2, -1) as u32 >> 3) & 7;
    core.raw_write_16(out, -1, (x + 1) as u16);
    core.raw_write_16(out + 2, -1, (y + height - 1) as u16);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, 1);
    cpu.set_thumb_pc(lr & !1);
}

// --- Three digits in the terrain panel ---------------------------------------------------

/// The terrain panel's hit-point row (inside `sub_0802AAxx`'s per-cell
/// update): the heart's sprite call, then the number's call
/// `sub_0802BAFC(x, y, value)` (r4 holds the hit points at both), which
/// draws the ones digit at x and the tens digit 7 pixels left of it, only
/// when the tens digit is not 0. A value of 100 or more would draw a letter
/// glyph as the tens digit. The panel is 30 pixels wide (a heart 10, two
/// digits 15), so three digits need the heart 3 pixels to the left (the
/// panel's edge) and the digits 2 to the right (the star row's number ends
/// there), the heart's outline meeting the hundreds digit's as digits' do.
const HEART_CALL: u32 = 0x0802_B23A;
const NUMBER_CALL: u32 = 0x0802_B266;
const NUMBER_AFTER: u32 = 0x0802_B26A;
const DRAW_NUMBER: u32 = 0x0802_BAFC;
/// The marker (high half) and step (low half) a digit draw in flight keeps
/// in its stack frame, 16 bytes under the panel code's stack: x, y, hit
/// points, marker.
const DRAWING: u32 = 0x4844_0000;
const HEART_SHIFT: i32 = 3;
const NUMBER_SHIFT: i32 = 2;
const DIGIT_PITCH: i32 = 7;

fn panel_heart(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let cpu = core.gba().cpu();
    if cpu.gpr(4) < 100 {
        return;
    }
    let x = (cpu.gpr(3) - HEART_SHIFT) & 0x1FF;
    core.gba_mut().cpu_mut().set_gpr(3, x);
}

/// 100 or more hit points: three digits, one `sub_0802BAFC` call each (a
/// value under 10 draws its ones digit alone), the call re-entering this
/// trap on return until the digits are done.
fn panel_number(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let sp = core.gba().cpu().gpr(13) as u32;
    let (step, frame) = if core.raw_read_32(sp + 12, -1) & 0xFFFF_0000 == DRAWING {
        (core.raw_read_32(sp + 12, -1) & 0xFFFF, sp)
    } else {
        let cpu = core.gba().cpu();
        let (x, y, hp) = (cpu.gpr(0) as u32, cpu.gpr(1) as u32, cpu.gpr(2));
        if hp < 100 {
            return;
        }
        let frame = sp - 16;
        core.raw_write_32(frame, -1, x);
        core.raw_write_32(frame + 4, -1, y);
        core.raw_write_32(frame + 8, -1, hp as u32);
        (0, frame)
    };
    if step == 3 {
        core.raw_write_32(frame + 12, -1, 0);
        let cpu = core.gba_mut().cpu_mut();
        cpu.set_gpr(13, (frame + 16) as i32);
        cpu.set_thumb_pc(NUMBER_AFTER);
        return;
    }
    let (x, y, hp) = (core.raw_read_32(frame, -1) as i32, core.raw_read_32(frame + 4, -1), core.raw_read_32(frame + 8, -1));
    let digit = hp / 10u32.pow(step) % 10;
    core.raw_write_32(frame + 12, -1, DRAWING | (step + 1));
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(13, frame as i32);
    cpu.set_gpr(0, (x + NUMBER_SHIFT - DIGIT_PITCH * step as i32) & 0xFFFF);
    cpu.set_gpr(1, y as i32);
    cpu.set_gpr(2, digit as i32);
    cpu.set_gpr(14, (NUMBER_CALL | 1) as i32);
    cpu.set_thumb_pc(DRAW_NUMBER);
}

/// The factory's entry in the invention list.
fn entry(core: &Core) -> Option<u32> {
    (0..16).map(|k| INVENTIONS + 8 * k).take_while(|&a| core.raw_read_16(a + 2, -1) & 0x3C0 != 0).find(|&a| (core.raw_read_16(a + 2, -1) as u32 >> 6) & 15 == FACTORY_KIND)
}

/// This battle's factory has been destroyed (Versus with the pack).
pub fn destroyed(core: &Core) -> bool {
    in_scope(core) && entry(core).is_some_and(|a| core.raw_read_8(a + 4, -1) == 0)
}

/// The hit step's destroy branch: the factory is destroyed with the
/// Black Cannon's explosion at the square it was aimed at.
fn destroy(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let proc = core.gba().cpu().gpr(3) as u32;
    if core.raw_read_16(proc + 0x64, -1) as u32 != FACTORY_KIND {
        return;
    }
    let entry = core.raw_read_32(proc + 0x4C, -1);
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, entry as i32);
    cpu.set_gpr(1, proc as i32);
    cpu.set_gpr(14, STEP_EXIT as i32);
    cpu.set_thumb_pc(CANNON_DESTROYED);
}

/// The Black Cannon's wreck, drawn over the factory's whole footprint.
///
/// AW2's `LoadInventionGraphics` (`0x0803FD80`) loads the Black Cannon sheet
/// (`0x080D24E0`, LZ77) at OBJ tile `0xC4` for every battle map, cannons or
/// not: its first 36 tiles are the cannon's wreck (the 48x48 sprite
/// definition `0x0849FA3C`, four sprites on tiles `0xC4..0xE7`, in the army's
/// building palette). The wreck is 3x3 and the factory 3x4, so two wrecks are
/// drawn from one sprite definition of ours: one on the lower three rows, the
/// other behind it on the upper three, a heap over the whole footprint. No
/// tile or palette is loaded or changed here, so nothing else's is touched;
/// should the tiles not be the sheet's (a screen that borrowed them) the
/// factory is drawn in the neutral grey of a building without an owner.
const WRECK_DEF: u32 = 0x0864_8000;
const WRECK_TILES: u32 = 0x0601_0000 + 0xC4 * 32;
const WRECK_TILE_BYTES: usize = 36 * 32;
const CANNON_SHEET: u32 = 0x080D_24E0;
/// The sprite definition: a count, then (attr0, attr1, attr2) a sprite, the
/// cannon's wreck (`0x0849FA3C`) once 16 pixels down (in front) and once at
/// the top (behind it).
const WRECK_WORDS: [u16; 25] = [
    8, //
    0x0010, 0x8000, 0x0C7C, 0x8010, 0x8020, 0x0C8C, 0x4030, 0x8000, 0x0C94, 0x0030, 0x4020, 0x0C9C, //
    0x0000, 0x8000, 0x0C7C, 0x8000, 0x8020, 0x0C8C, 0x4020, 0x8000, 0x0C94, 0x0020, 0x4020, 0x0C9C,
];
const NEUTRAL_OWNER: i32 = 0;

/// The wreck's tiles as the game's sheet has them (decoded once).
fn wreck_tiles(core: &Core) -> &'static [u8] {
    static TILES: std::sync::OnceLock<Vec<u8>> = std::sync::OnceLock::new();
    TILES.get_or_init(|| {
        // GBA BIOS LZ77: a header (0x10, size), then blocks of a flag byte
        // (bit 7 first; 1 = a back-reference of 3..18 bytes at 1..4096 back).
        let header = core.raw_read_32(CANNON_SHEET, -1);
        let size = (header >> 8) as usize;
        let (mut src, mut out) = (CANNON_SHEET + 4, Vec::with_capacity(size));
        while out.len() < size {
            let flags = core.raw_read_8(src, -1);
            src += 1;
            for bit in (0..8).rev() {
                if out.len() >= size {
                    break;
                }
                if flags & (1 << bit) == 0 {
                    out.push(core.raw_read_8(src, -1));
                    src += 1;
                } else {
                    let (b0, b1) = (core.raw_read_8(src, -1) as usize, core.raw_read_8(src + 1, -1) as usize);
                    src += 2;
                    let (len, back) = ((b0 >> 4) + 3, (((b0 & 15) << 8) | b1) + 1);
                    for _ in 0..len {
                        let v = out[out.len() - back];
                        out.push(v);
                    }
                }
            }
        }
        out.truncate(WRECK_TILE_BYTES);
        out
    })
}

/// The wreck's tiles are in place in VRAM.
fn wreck_loaded(core: &Core) -> bool {
    let want = wreck_tiles(core);
    want.len() == WRECK_TILE_BYTES && want.chunks(4).enumerate().all(|(i, w)| core.raw_read_32(WRECK_TILES + 4 * i as u32, -1).to_le_bytes() == *w)
}

fn put_wreck_definition(core: &mut Core) {
    for (i, w) in WRECK_WORDS.iter().enumerate() {
        let at = WRECK_DEF + 2 * i as u32;
        if core.raw_read_16(at, -1) != *w {
            core.raw_write_16(at, -1, *w);
        }
    }
}

/// A destroyed factory is drawn as the wreck (above).
fn ruin(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let entry = core.gba().cpu().gpr(5) as u32;
    if core.raw_read_8(entry + 4, -1) != 0 {
        return;
    }
    if wreck_loaded(core) {
        put_wreck_definition(core);
        core.gba_mut().cpu_mut().set_gpr(2, WRECK_DEF as i32);
    } else {
        core.gba_mut().cpu_mut().set_gpr(3, NEUTRAL_OWNER);
    }
}

// --- The building is a wall ---------------------------------------------------------------

const MAP: u32 = 0x0201_E450;
/// The invention underlay's terrain class: no unit enters it.
const WALL: u8 = 9;
const FACTORY_CLASS: u8 = 0x1D;

/// Every frame, in Versus with the pack: the factory's building squares (its
/// footprint but the doors' row below it) are impassable to every unit, as
/// AW2's own maps make them (underlay class 9, the factory's 0x1D), the pipe
/// end at its top included (a Piperunner would ride in there) and a map that
/// carries just the anchor tile too.
pub fn tick(core: &mut Core, on: bool) {
    if !on || !in_scope(core) {
        return;
    }
    let Some(a) = entry(core) else { return };
    let (x0, y0) = (core.raw_read_8(a, -1) as u32, core.raw_read_8(a + 1, -1) as u32);
    let (w, h) = ((core.raw_read_8(a + 2, -1) & 7) as u32, ((core.raw_read_8(a + 2, -1) >> 3) & 7) as u32);
    let (mw, mh) = (core.raw_read_16(MAP, -1) as u32, core.raw_read_16(MAP + 2, -1) as u32);
    for y in y0..(y0 + h).min(mh) {
        let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
        for x in x0..(x0 + w).min(mw) {
            let at = MAP + 0x1432 + row + x;
            let class = core.raw_read_8(at, -1);
            if class & 0x1F != WALL && class & 0x1F != FACTORY_CLASS {
                core.raw_write_8(at, -1, (class & !0x1F) | WALL);
            }
        }
    }
}

// --- The CPU strikes a factory ---------------------------------------------------------

/// A CPU unit's strike, queued in [`crate::cpu_tactics`]'s pending list with
/// this bit set on the unit's record pointer.
pub const STRIKE: u32 = 0x8000_0000;
/// The game's own "attack the structure at (x, y)" step, which AW2's CPU
/// runs for a pipe seam: `sub_08042634(x, y)`, from the unit selected
/// (`0x030040D8`, its id in `0x03003F38`, its square in `0x03003100`).
const STRUCTURE_ATTACK: u32 = 0x0804_2634;
const SELECTED: u32 = 0x0300_40D8;
const SELECTED_ID: u32 = 0x0300_3F38;
const DEST: u32 = 0x0300_3100;
const ORIGIN: u32 = 0x0300_3F24;
const UNITS_POINTER: u32 = 0x0849_9594;
const PLAYERS_SIDE: u32 = 0x2A;
/// The hit's processes (scripts): while one runs the next strike waits.
const HIT_SCRIPTS: [u32; 3] = [0x0849_FE78, 0x0849_FB04, 0x0849_FADC];

fn pos(core: &Core, u: u32) -> (i32, i32) {
    (core.raw_read_8(u + 2, -1) as i32, core.raw_read_8(u + 3, -1) as i32)
}

/// The square the factory is aimed at, when it stands.
fn aim(core: &Core) -> Option<(i32, i32)> {
    let a = entry(core).filter(|&a| core.raw_read_8(a + 4, -1) != 0)?;
    let height = (core.raw_read_8(a + 2, -1) as i32 >> 3) & 7;
    Some((core.raw_read_8(a, -1) as i32 + 1, core.raw_read_8(a + 1, -1) as i32 + height - 1))
}

/// A hit's animation is playing.
pub fn busy(core: &Core) -> bool {
    [(0x0300_1500u32, 0x0300_1F00u32), (0x0200_D610, 0x0200_E000)]
        .iter()
        .any(|&(lo, hi)| (lo..hi).step_by(4).any(|a| HIT_SCRIPTS.contains(&core.raw_read_32(a, -1))))
}

/// The army that owns the factory: the one in Black Hole's colour (5).
fn owner(core: &Core) -> Option<u32> {
    let p = crate::five::players(core);
    (1..=5u32).find(|&a| core.raw_read_8(p + 0x3C * a + 0x1A, -1) == 5)
}

fn team(core: &Core, army: u32) -> u8 {
    core.raw_read_8(crate::five::players(core) + 0x3C * army + PLAYERS_SIDE, -1)
}

/// `u` can hurt the factory from where it stands (nothing it could shoot
/// instead): its range takes in the aimed square, it has a weapon that does
/// damage to a structure, and no unit of another team is in its range.
fn can_strike(core: &Core, u: u32, target: (i32, i32), my_team: u8) -> bool {
    let t = core.raw_read_8(u, -1);
    let table = crate::roster::table(core);
    let (rmin, rmax) = (
        core.raw_read_8(table + 0x5C * t as u32 + 0x0E, -1).max(1) as i32,
        core.raw_read_8(table + 0x5C * t as u32 + 0x0F, -1).max(1) as i32,
    );
    let p = pos(core, u);
    let d = (p.0 - target.0).abs() + (p.1 - target.1).abs();
    if d < rmin || d > rmax {
        return false;
    }
    let ammo = (core.raw_read_16(u + 4, -1) >> 7) & 0xF;
    // Column 3 is the structures' (the game's own: `sub_080251D8`).
    if !(crate::roster::chart(t, 3, 1) > 0 || (ammo > 0 && crate::roster::chart(t, 3, 0) > 0)) {
        return false;
    }
    let base = core.raw_read_32(UNITS_POINTER, -1);
    !(1..255u32).any(|i| {
        let v = base + 12 * i;
        if core.raw_read_8(v, -1) == 0 || core.raw_read_8(v + 1, -1) & 0x08 != 0 || v == u {
            return false;
        }
        if team(core, crate::five::army_of_index(core, i)) == my_team {
            return false;
        }
        let q = pos(core, v);
        let dv = (p.0 - q.0).abs() + (p.1 - q.1).abs();
        dv >= rmin && dv <= rmax
    })
}

/// The units of the CPU army `army` that hit the enemy factory this turn,
/// each marked moved and queued by the caller ([`crate::cpu_tactics`]).
pub fn cpu_strikers(core: &Core, army: u32) -> Vec<u32> {
    if !in_scope(core) {
        return Vec::new();
    }
    let (Some(target), Some(owner)) = (aim(core), owner(core)) else { return Vec::new() };
    let my_team = team(core, army);
    if my_team == team(core, owner) {
        return Vec::new();
    }
    let base = core.raw_read_32(UNITS_POINTER, -1);
    (1..255u32)
        .filter(|&i| crate::five::army_of_index(core, i) == army)
        .map(|i| base + 12 * i)
        .filter(|&u| {
            core.raw_read_8(u, -1) != 0
                && core.raw_read_8(u + 1, -1) & 0x09 == 0
                && can_strike(core, u, target, my_team)
        })
        .collect()
}

/// Plays a queued strike: the game's structure attack by `u`, returning to
/// `ret`. `false` when the factory is gone or a hit is still playing.
pub fn strike(core: &mut Core, u: u32, ret: u32) -> bool {
    let Some(target) = aim(core) else { return false };
    if core.raw_read_8(u, -1) == 0 {
        return false;
    }
    let id = (u - core.raw_read_32(UNITS_POINTER, -1)) / 12;
    let (x, y) = pos(core, u);
    crate::bh_factory::log(&format!(
        "strike: unit {id} type {} at ({x},{y}) aims at {target:?}, factory hp {}",
        core.raw_read_8(u, -1),
        entry(core).map_or(0, |a| core.raw_read_8(a + 4, -1))
    ));
    core.raw_write_8(SELECTED_ID, -1, id as u8);
    core.raw_write_32(SELECTED, -1, u);
    for at in [DEST, ORIGIN] {
        core.raw_write_16(at, -1, x as u16);
        core.raw_write_16(at + 2, -1, y as u16);
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(0, target.0);
    cpu.set_gpr(1, target.1);
    cpu.set_gpr(14, ret as i32);
    cpu.set_thumb_pc(STRUCTURE_ATTACK);
    true
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (REGISTER, Box::new(register)),
        (TARGET_POSITION, Box::new(target_position)),
        (DESTROY_BRANCH, Box::new(destroy)),
        (FACTORY_SPRITE, Box::new(ruin)),
        (HEART_CALL, Box::new(panel_heart)),
        (NUMBER_CALL, Box::new(panel_number)),
    ]
}
