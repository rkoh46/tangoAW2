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
//! - it is a target at the middle of its bottom row, as a Black Cannon is
//!   (one open square beside it: the middle door), and everything after
//!   that is the game's own for an invention: the attack menu, the damage
//!   (the game's, the same as against a Black Cannon), the HP in the terrain
//!   panel, the hit animation;
//! - at 0 HP it is destroyed as a Black Cannon is (the explosion, [`destroy`]),
//!   its entry staying in the list with 0 HP, which the game saves with the
//!   battle; it is drawn as the Black Cannon's ruin ([`ruin`]) and its doors
//!   spawn nothing any more ([`destroyed`]). The battle goes on.

use mgba::core::Core;

pub const HP: u8 = 99;
const FACTORY_KIND: u32 = 7;

const REGISTER: u32 = 0x0803_E348;
const TARGET_POSITION: u32 = 0x0803_DFE0;
/// The hit-and-destroy step (a process, proc in r3): the start of its
/// "no HP left" branch, which has a case for each kind but the factory.
const DESTROY_BRANCH: u32 = 0x0804_0818;
/// What a Black Cannon facing down does there: `(entry, proc)`.
const CANNON_DESTROYED: u32 = 0x0804_026C;
const STEP_EXIT: u32 = 0x0804_0879;
/// The factory's sprite: the instruction after the definition is loaded
/// (r0 x, r1 y, r2 definition, r3 palette).
const FACTORY_SPRITE: u32 = 0x0803_FD52;
/// The Black Cannon's ruin (its destroyed sprite definition).
const RUIN_DEF: u32 = 0x0849_FA3C;
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

/// A destroyed factory is drawn as the Black Cannon's ruin, on the lower
/// three rows.
fn ruin(core: &mut Core) {
    if !in_scope(core) {
        return;
    }
    let cpu = core.gba().cpu();
    let (y, entry) = (cpu.gpr(1), cpu.gpr(5) as u32);
    if core.raw_read_8(entry + 4, -1) != 0 {
        return;
    }
    let cpu = core.gba_mut().cpu_mut();
    cpu.set_gpr(1, y + 1);
    cpu.set_gpr(2, RUIN_DEF as i32);
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
    ]
}
