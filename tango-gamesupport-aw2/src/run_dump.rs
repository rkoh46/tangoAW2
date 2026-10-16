//! Test tools: the game state of a live run as a machine-readable log (`TANGOAW2_RUN_DIR=<fresh dir>`,
//! `TANGOAW2_RUN_SEAT=<k>`), beside the window's frames (`s<k>_<NNNN>.png`) and `meta_s<k>.json` (the build stamp and
//! the client's start on the shared wall clock) that the app writes. Never drawn, never read back into the game: it is
//! for tools (QA's leak and claim check) and for the AI-only debug menu to come.
//!
//! `state_s<k>.jsonl`, one JSON object per line, all times in milliseconds of the shared wall clock (`ms`):
//! - `{"ms","tick","k":"state","seat","army","mover","mine","over","ended","fog","ml","funds":[a1..a5],"owners":N}`
//!   ten times a second: the army whose turn it is and the seat that plays it, whether it is this window's own turn,
//!   the match decided, the turn ended (NEXT TURN banner), fog on, the main-loop callback, every army's funds.
//! - `{"ms","tick","k":"act","what":"build|move|attack|kill|capture","actor":army,"unit":..,"from":[x,y],"to":[x,y],
//!   "hp":[a,b],"seat","army"}` whenever the unit list or the property owners change (compared ten times a second).
//! - `{"ms","tick","k":"seen","army","cells":"hex"}` at every action: the cells the displayed army sees (the plane the
//!   game drew from: the mover's own when this window is the mover's).
use mgba::core::Core;
use std::io::Write;
use std::sync::Mutex;

struct Dump {
    file: std::fs::File,
    tick: u32,
    last_units: std::collections::BTreeMap<u32, (u32, u8, i32, i32, u32)>,
    last_owner: std::collections::BTreeMap<u32, u8>,
    ready: bool,
}

static DUMP: Mutex<Option<Dump>> = Mutex::new(None);
static ENABLED: std::sync::OnceLock<Option<(std::path::PathBuf, u32)>> = std::sync::OnceLock::new();

fn enabled() -> Option<&'static (std::path::PathBuf, u32)> {
    ENABLED
        .get_or_init(|| {
            let dir = std::env::var("TANGOAW2_RUN_DIR").ok()?;
            let seat = std::env::var("TANGOAW2_RUN_SEAT").ok().and_then(|v| v.parse().ok()).unwrap_or(0);
            Some((std::path::PathBuf::from(dir), seat))
        })
        .as_ref()
}

fn ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_millis())
}

/// Every tick of the match's console (any peer): note the state (cheap unless the aid is on).
pub fn tick(core: &Core) {
    let Some((dir, seat)) = enabled() else { return };
    let mut guard = DUMP.lock().unwrap();
    let d = guard.get_or_insert_with(|| {
        let file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join(format!("state_s{seat}.jsonl")))
            .expect("run dump file");
        Dump { file, tick: 0, last_units: Default::default(), last_owner: Default::default(), ready: false }
    });
    d.tick += 1;
    if d.tick % 6 != 0 {
        return;
    }
    const MAP: u32 = 0x0201_E450;
    let (w, h) = (core.raw_read_16(MAP, -1) as u32, core.raw_read_16(MAP + 2, -1) as u32);
    let battle = crate::pvp::in_battle(core);
    if !battle || w == 0 || w > 64 || h == 0 || h > 64 {
        return;
    }
    let n = crate::online::room_players().max(2);
    let me = crate::online::room_local_seat();
    let army = crate::pvp::current_army(core);
    let mover = if (1..=5).contains(&army) { crate::pvp::seat_of_n(army, n) as i32 } else { -1 };
    let armies = crate::five::armies(core).clamp(2, 5);
    let funds: Vec<u32> = (1..=armies).map(|a| core.raw_read_32(crate::tag::player(core, a as u32), -1)).collect();
    let now = ms();
    let _ = writeln!(
        d.file,
        "{{\"ms\":{now},\"tick\":{},\"k\":\"state\",\"seat\":{me},\"army\":{army},\"mover\":{mover},\"mine\":{},\"over\":{},\"ended\":{},\"fog\":{},\"ml\":{},\"funds\":{funds:?}}}",
        d.tick,
        mover == me as i32,
        crate::result_view::decided(core),
        crate::pvp::turn_ended(core),
        core.raw_read_8(0x0300_3FCD, -1) != 0,
        core.raw_read_32(0x0300_0000, -1)
    );
    // The unit list and the property owners, compared with the last look.
    let base = core.raw_read_32(0x0849_9594, -1);
    let mut units = std::collections::BTreeMap::new();
    for y in 0..h {
        let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
        for x in 0..w {
            let id = core.raw_read_8(MAP + 0x51A + row + x, -1) as u32;
            if id == 0 {
                continue;
            }
            let u = base + 12 * id;
            let kind = core.raw_read_8(u, -1) as u32;
            if kind == 0 {
                continue;
            }
            let hp = core.raw_read_16(u + 4, -1) as u32 & 0x7F;
            units.insert(id, (kind, crate::five::army_of_index(core, id) as u8, x as i32, y as i32, hp));
        }
    }
    let mut owners = std::collections::BTreeMap::new();
    for y in 0..h {
        let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
        for x in 0..w {
            let class = core.raw_read_8(MAP + 0x1432 + row + x, -1);
            if matches!(class & 0x1F, 8..=12) {
                owners.insert(y * 64 + x, class >> 5);
            }
        }
    }
    let mut acts: Vec<String> = Vec::new();
    if d.ready {
        for (id, &(kind, a, x, y, hp)) in &units {
            match d.last_units.get(id) {
                None => acts.push(format!("\"what\":\"build\",\"actor\":{a},\"unit\":{kind},\"to\":[{x},{y}],\"hp\":[0,{hp}]")),
                Some(&(_, _, ox, oy, ohp)) => {
                    if (ox, oy) != (x, y) {
                        acts.push(format!("\"what\":\"move\",\"actor\":{a},\"unit\":{kind},\"from\":[{ox},{oy}],\"to\":[{x},{y}],\"hp\":[{ohp},{hp}]"));
                    } else if hp < ohp {
                        acts.push(format!("\"what\":\"attack\",\"actor\":{army},\"unit\":{kind},\"owner\":{a},\"to\":[{x},{y}],\"hp\":[{ohp},{hp}]"));
                    }
                }
            }
        }
        for (id, &(kind, a, x, y, hp)) in &d.last_units {
            if !units.contains_key(id) {
                acts.push(format!("\"what\":\"kill\",\"actor\":{army},\"unit\":{kind},\"owner\":{a},\"to\":[{x},{y}],\"hp\":[{hp},0]"));
            }
        }
        for (&cell, &o) in &owners {
            if let Some(&old) = d.last_owner.get(&cell) {
                if old != o {
                    acts.push(format!("\"what\":\"capture\",\"actor\":{o},\"to\":[{},{}],\"from_owner\":{old}", cell % 64, cell / 64));
                }
            }
        }
    }
    d.ready = true;
    d.last_units = units;
    d.last_owner = owners;
    if !acts.is_empty() {
        let plane: String = (0..h)
            .flat_map(|y| {
                let row = core.raw_read_16(MAP + 0x417A + 2 * y, -1) as u32;
                (0..w).map(move |x| (row, x))
            })
            .map(|(row, x)| if core.raw_read_8(MAP + 0x234A + row + x, -1) != 0 { '1' } else { '0' })
            .collect();
        for a in acts {
            let _ = writeln!(d.file, "{{\"ms\":{now},\"tick\":{},\"k\":\"act\",{a},\"seat\":{me},\"army\":{army}}}", d.tick);
        }
        let _ = writeln!(d.file, "{{\"ms\":{now},\"tick\":{},\"k\":\"seen\",\"army\":{army},\"w\":{w},\"h\":{h},\"cells\":\"{plane}\"}}", d.tick);
        let _ = d.file.flush();
    }
}
