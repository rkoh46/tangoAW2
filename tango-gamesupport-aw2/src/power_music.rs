//! Dual Strike's power music, with the Dual Strike pack: its CO Power,
//! Super CO Power and Tag Power themes (converted by crate::ds_music,
//! [`crate::ds_music::POWER_SONGS`]) in place of AW2's.
//!
//! **Dual Strike** (`Player_PlayTheme`): the front CO's power state picks
//! the theme: a CO Power `BGM_BREAK_ALLY1` / `_ENEMY1` (sequences 0x1D /
//! 0x1C), a Super CO Power `BGM_SPECIAL_BREAK_ALLY1` / `_ENEMY1` (0x1F /
//! 0x20), and a Super while a Tag Power is on (either half)
//! `BGM_TAG_BREAK_ALLY1` / `_ENEMY1` (0x2E / 0x2F). Allied or Black Hole
//! (`Player_IsAlliedNations`): the front CO's nation, but in the campaign
//! every human player is Allied and the computer's armies are not (on
//! Jake's Trial, Lightning Strikes and Verdant Hills every army is
//! Allied). The tag theme starts during the Tag Power's thunder, before
//! its screen (script `0x0215C4F4`, frame 256).
//!
//! **AW2** (`sub_08043DAC(army)`): player +0x1E picks the music: 1 calls
//! `sub_08043DF4(co)`, which plays song 0x1A3 (Black Hole, `sub_08044BA0`)
//! or 0x1A4, 2 calls `sub_08043E18(co)`, 0x199 or 0x19A, each through
//! `sub_0803B4EC(song)` (which leaves a song already playing alone). The
//! power screens call those two directly as well (`0x08080EE4`,
//! `0x08080EF8`), for the army whose turn it is.
//!
//! **Here.** The four calls of `sub_0803B4EC` in those two functions are
//! trapped and their song switched for Dual Strike's ([`song`]): the army
//! is the one `sub_08043DAC` was called for (kept at its entry, [`ARMY`])
//! when the call came from there, else the current army; Allied or Black
//! Hole by Dual Strike's rule: in the DS Campaign the player's armies are
//! Allied (every army on its three missions), in the BH Campaign the
//! player is Black Hole (the computer's armies by their CO), elsewhere the
//! front CO's nation as AW2's own test gives it (the new COs as the CO they
//! take after). The tag theme also starts at the Tag Power's frame 256
//! (crate::tag_extras, [`tag_theme`]), so the power screen's call finds it
//! playing. Without the songs (no pack, or one saved before them) AW2's
//! power music plays.

use mgba::core::Core;

use crate::ds_music::PowerSong;

/// The army `sub_08043DAC` was last called for (EWRAM, crate::ram_map).
pub const ARMY: u32 = 0x0203_C601;
pub const ARMY_LEN: u32 = 1;

const PICK_MUSIC: u32 = 0x0804_3DAC;
/// `sub_08043DF4` and `sub_08043E18` return there when `sub_08043DAC`
/// called them.
const FROM_PICK: [u32; 2] = [0x0804_3DE6, 0x0804_3DEE];
/// The `bl sub_0803B4EC` calls: (address, the power's mode).
const CALLS: [(u32, u8); 4] = [(0x0804_3E02, 1), (0x0804_3E10, 1), (0x0804_3E26, 2), (0x0804_3E34, 2)];

const CURRENT_ARMY: u32 = 0x0300_33EC;
const PL_HUMAN: u32 = 0x1B;
const PL_CO: u32 = 0x1D;
/// Dual Strike's campaign missions on which every army counts as Allied
/// (`MAP_JAKES_TRIAL`, `MAP_LIGHTNING_STRIKES`, `MAP_VERDANT_HILLS`: map
/// ids 0xE0 + these).
const ALL_ALLIED: [usize; 3] = [0, 10, 12];
const DS_SOURCE: usize = 0;

fn pick_music(core: &mut Core) {
    let army = core.gba().cpu().gpr(0) as u8;
    if core.raw_read_8(ARMY, -1) != army {
        core.raw_write_8(ARMY, -1, army);
    }
}

fn call(core: &mut Core, mode: u8) {
    if !crate::ds_weather::is_on(core) {
        return;
    }
    // (the caller's return address, pushed by the function's `push {lr}`)
    let sp = core.gba().cpu().gpr(13) as u32;
    let back = core.raw_read_32(sp, -1) & !1;
    let army = if FROM_PICK.contains(&back) {
        core.raw_read_8(ARMY, -1)
    } else {
        core.raw_read_8(CURRENT_ARMY, -1)
    } as u32;
    if let Some(s) = song(core, army, mode) {
        core.gba_mut().cpu_mut().set_gpr(0, s as i32);
    }
}

/// Dual Strike's theme for army `army`'s power `mode` (1 CO Power, 2 Super),
/// when the pack has it.
pub fn song(core: &Core, army: u32, mode: u8) -> Option<u16> {
    if !(1..=5).contains(&army) {
        return None;
    }
    let which = match mode {
        1 => PowerSong::CoPower,
        2 if crate::tag::phase(core, army) != 0 => PowerSong::Tag,
        2 => PowerSong::Super,
        _ => return None,
    };
    crate::ds_music::power_song(which, allied(core, army))
}

/// The Tag Power's theme for army `army` (crate::tag_extras starts it at
/// the thunder's end, as Dual Strike's script does).
pub fn tag_theme(core: &Core, army: u32) -> Option<u16> {
    if !crate::ds_weather::is_on(core) || !(1..=5).contains(&army) {
        return None;
    }
    crate::ds_music::power_song(PowerSong::Tag, allied(core, army))
}

/// Whether army `army` gets the Allied Nations' themes
/// (`Player_IsAlliedNations`, as module docs say).
fn allied(core: &Core, army: u32) -> bool {
    let p = crate::tag::player(core, army);
    let human = core.raw_read_8(p + PL_HUMAN, -1) == 1;
    let by_nation = || !crate::co_new::black_hole_power_music(core, core.raw_read_8(p + PL_CO, -1));
    if crate::ds_campaign::active(core) {
        if crate::ds_campaign::source(core) == DS_SOURCE {
            let all = crate::ds_campaign::mission_info(core).is_some_and(|m| ALL_ALLIED.contains(&m.index));
            return all || human;
        }
        // The BH Campaign: the player is Black Hole.
        return !human && by_nation();
    }
    by_nation()
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    let mut t: Vec<(u32, Box<dyn Fn(&mut Core)>)> = vec![(PICK_MUSIC, Box::new(pick_music))];
    for (at, mode) in CALLS {
        t.push((at, Box::new(move |core: &mut Core| call(core, mode))));
    }
    t
}
