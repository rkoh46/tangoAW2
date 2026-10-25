//! What a suspended online match shows in the list of saved matches (ONLINE > LOBBY > RESUME): the map, the day and
//! the rules, read from the console's memory as it stood at the saved state (`ewram`, `iwram`) with the live
//! console for the ROM's texts.

use mgba::core::Core;
use tango_match::StateInfo;

const EWRAM: u32 = 0x0200_0000;
const IWRAM: u32 = 0x0300_0000;
const MAP_ID: u32 = 0x0300_3FC2;
const DAY: u32 = 0x0300_4080;
const FOG: u32 = 0x0300_3FCD;
/// AW2's text table (`+ 4 * id` points at the string).
const TEXT_TABLE: u32 = 0x0861_0A38;

struct Mem<'a> {
    core: &'a Core,
    ewram: &'a [u8],
    iwram: &'a [u8],
}

impl Mem<'_> {
    fn u8(&self, a: u32) -> u8 {
        if (EWRAM..EWRAM + 0x40000).contains(&a) {
            self.ewram.get((a - EWRAM) as usize).copied().unwrap_or(0)
        } else if (IWRAM..IWRAM + 0x8000).contains(&a) {
            self.iwram.get((a - IWRAM) as usize).copied().unwrap_or(0)
        } else {
            self.core.raw_read_8(a, -1)
        }
    }
    fn u16(&self, a: u32) -> u16 {
        self.u8(a) as u16 | (self.u8(a + 1) as u16) << 8
    }
    fn u32(&self, a: u32) -> u32 {
        self.u16(a) as u32 | (self.u16(a + 2) as u32) << 16
    }
}

/// The saved state's map name, day and rules.
pub fn describe(core: &Core, ewram: &[u8], iwram: &[u8]) -> Option<StateInfo> {
    let m = Mem { core, ewram, iwram };
    // Only a state in a room's battle is worth keeping (online.rs's BATTLE byte: the whole of a battle, its menus
    // and the moments between its screens).
    if m.u8(crate::online::STATE + 0x64) != 1 {
        return None;
    }
    let id = m.u8(MAP_ID) as u32;
    let table = crate::five_map::table(core);
    let entry = table + crate::five_map::ENTRY * id;
    let text_id = m.u16(entry + 0x14) as u32;
    let armies = m.u8(entry + 0x18);
    let p = m.u32(TEXT_TABLE + 4 * text_id);
    let mut name = String::new();
    if (0x0800_0000..0x0A00_0000).contains(&p) || (EWRAM..EWRAM + 0x40000).contains(&p) {
        for k in 0..40 {
            let c = m.u8(p + k);
            if c == 0 {
                break;
            }
            name.push(if c == b'~' {
                '\''
            } else if (32..127).contains(&c) {
                c as char
            } else {
                ' '
            });
        }
    }
    if name.trim().is_empty() {
        name = format!("Map {id}");
    }
    let day = m.u16(DAY) as u32;
    let mut rules = format!("{armies} armies");
    if m.u8(FOG) != 0 {
        rules.push_str(", fog");
    }
    Some(StateInfo {
        map: name.trim().to_string(),
        day,
        rules,
    })
}
