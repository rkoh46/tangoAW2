//! Test tools (the decoding is [`crate::inspect`]'s, shared with the AI debug channel): the game state of a live run as a machine-readable log (`TANGOAW2_RUN_DIR=<fresh dir>`,
//! `TANGOAW2_RUN_SEAT=<k>`), beside the window's frames (`s<k>_<NNNN>.png`) and `meta_s<k>.json` (the build stamp and
//! the client's start on the shared wall clock) that the app writes. Never drawn, never read back into the game: it is
//! for tools (QA's leak and claim check) and for the AI-only debug menu to come.
//!
//! `state_s<k>.jsonl`, one JSON object per line, all times in milliseconds of the shared wall clock (`ms`):
//! - `{"ms","tick","k":"state","seat","army","mover","mine","over","ended","fog","ml","funds":[a1..a5],"owners":N}`
//!   ten times a second: the army whose turn it is and the seat that plays it, whether it is this window's own turn,
//!   the match decided, the turn ended (NEXT TURN banner), fog on, the main-loop callback, every army's funds.
//! - `{"ms","tick","k":"act","what":"build|move|attack|kill|capture|load|unload|power","actor":army,"unit":..,"from":[x,y],"to":[x,y],
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
    last_powers: [u8; 6],
    last_alive: [bool; 6],
    last_hash_frame: u32,
    prev_fc: u32,
    last_carried: std::collections::BTreeMap<u32, (u32, u8)>,
    ready: bool,
}

static DUMP: Mutex<Option<Dump>> = Mutex::new(None);
static ENABLED: std::sync::OnceLock<Option<(std::path::PathBuf, u32)>> = std::sync::OnceLock::new();

fn enabled() -> Option<&'static (std::path::PathBuf, u32)> {
    ENABLED
        .get_or_init(|| {
            let dir = std::env::var("TANGOAW2_RUN_DIR").ok()?;
            let seat = std::env::var("TANGOAW2_RUN_SEAT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(0);
            Some((std::path::PathBuf::from(dir), seat))
        })
        .as_ref()
}

/// `TANGOAW2_DUMP_FRAME=<n>` or `<a>-<b>`: the frames whose RAM is kept (and hashed even off the 60-frame grid).
fn dump_range() -> Option<(u32, u32)> {
    static R: std::sync::OnceLock<Option<(u32, u32)>> = std::sync::OnceLock::new();
    *R.get_or_init(|| {
        let v = std::env::var("TANGOAW2_DUMP_FRAME").ok()?;
        match v.split_once('-') {
            Some((a, b)) => Some((a.trim().parse().ok()?, b.trim().parse().ok()?)),
            None => v.trim().parse().ok().map(|n| (n, n)),
        }
    })
}

fn ms() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0, |d| d.as_millis())
}

/// Every tick of the match's console (any peer): note the state (cheap unless the aid is on).
/// The console ticks this client has run (for the frame sidecar: which tick a picture was taken at).
static TICKS: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
pub fn ticks() -> u32 {
    TICKS.load(std::sync::atomic::Ordering::Relaxed)
}

pub fn tick(core: &Core, keys: u32) {
    let Some((dir, seat)) = enabled() else { return };
    let mut guard = DUMP.lock().unwrap();
    let d = guard.get_or_insert_with(|| {
        let file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(dir.join(format!("state_s{seat}.jsonl")))
            .expect("run dump file");
        Dump {
            file,
            tick: 0,
            last_units: Default::default(),
            last_owner: Default::default(),
            last_powers: [0; 6],
            last_alive: [true; 6],
            last_hash_frame: 0,
            prev_fc: 0,
            last_carried: Default::default(),
            ready: false,
        }
    });
    d.tick += 1;
    TICKS.store(d.tick, std::sync::atomic::Ordering::Relaxed);
    // (every non-zero joypad word the console takes, with its tick: proof of what reached the game)
    if keys != 0 {
        let _ = writeln!(
            d.file,
            "{{\"ms\":{},\"tick\":{},\"k\":\"keys\",\"word\":{keys}}}",
            ms(),
            d.tick
        );
    }
    // (the console's state hash at every 60th frame of its own count: peers that play the same match agree at the same frame)
    let fc = core.frame_counter();
    // (a rollback re-simulates frames: hash them again, so the last line per frame is the corrected state, not the speculative first visit)
    // (a rollback of the last tick alone starts the same frame again: equal counts too)
    if fc <= d.prev_fc {
        d.last_hash_frame = 0;
    }
    d.prev_fc = fc;
    // (TANGOAW2_DUMP_FRAME=<a>-<b> hashes and dumps every frame of the range, to find the frame a desync starts at)
    let in_range = dump_range().is_some_and(|(a, b)| (a..=b).contains(&fc));
    if (fc % 60 == 0 || in_range) && fc != d.last_hash_frame {
        d.last_hash_frame = fc;
        let mut iw = vec![0u8; 0x8000];
        core.raw_read_range(0x0300_0000, -1, &mut iw);
        let mut ew = vec![0u8; 0x40000];
        core.raw_read_range(0x0200_0000, -1, &mut ew);
        // (test aid: TANGOAW2_DUMP_FRAME=<n> keeps the console's RAM at that frame, to find where two peers differ)
        if dump_range().is_some_and(|(a, b)| (a..=b).contains(&fc)) {
            if let (Ok(dir), Ok(seat)) = (std::env::var("TANGOAW2_RUN_DIR"), std::env::var("TANGOAW2_RUN_SEAT")) {
                let _ = std::fs::write(format!("{dir}/ram_s{seat}_{fc}_i.bin"), &iw);
                let _ = std::fs::write(format!("{dir}/ram_s{seat}_{fc}_e.bin"), &ew);
            }
        }
        let mut h: u64 = 0xcbf29ce484222325;
        for b in iw.iter().chain(ew.iter()) {
            h = (h ^ *b as u64).wrapping_mul(0x100000001b3);
        }
        // (the Visuals rule's three copies: the host's choice is shared by every peer; logged so a divergence would show)
        let vis = [
            core.raw_read_8(0x0200_C42E, -1),
            core.raw_read_8(0x0201_7C52, -1),
            core.raw_read_8(0x0201_7CDA, -1),
        ];
        // (test aid: TANGOAW2_HASH_PARTS=1 adds a short hash of every 4 KB of IWRAM then EWRAM, to find where two peers differ)
        let parts = if std::env::var_os("TANGOAW2_HASH_PARTS").is_some() {
            let hs: Vec<String> = iw
                .chunks(0x1000)
                .chain(ew.chunks(0x1000))
                .map(|c| {
                    format!(
                        "{:04x}",
                        (c.iter().fold(0xcbf29ce484222325u64, |h, b| (h ^ *b as u64)
                            .wrapping_mul(0x100000001b3))
                            >> 24) as u16
                    )
                })
                .collect();
            format!(",\"parts\":\"{}\"", hs.join(""))
        } else {
            String::new()
        };
        let _ = writeln!(
            d.file,
            "{{\"ms\":{},\"tick\":{},\"k\":\"hash\",\"frame\":{fc},\"h\":\"{h:016x}\",\"visuals\":{vis:?}{parts}}}",
            ms(),
            d.tick
        );
    }
    if d.tick % 6 != 0 {
        return;
    }
    // The battle as the one decoder ([`crate::inspect`], also what the AI debug channel answers with) reads it.
    let snap = crate::inspect::snapshot(core, false);
    let (w, h) = (snap.width, snap.height);
    if !snap.in_battle || w == 0 || w > 64 || h == 0 || h > 64 {
        return;
    }
    let n = crate::online::room_players().max(2);
    let me = crate::online::room_local_seat();
    let army = snap.active_army;
    let mover = if (1..=5).contains(&army) {
        crate::pvp::seat_of_n(army, n) as i32
    } else {
        -1
    };
    let armies = snap.armies.len() as u8;
    let funds: Vec<u32> = snap.armies.iter().map(|a| a.funds).collect();
    let now = ms();
    let _ = writeln!(
        d.file,
        "{{\"ms\":{now},\"tick\":{},\"k\":\"state\",\"seat\":{me},\"army\":{army},\"mover\":{mover},\"mine\":{},\"over\":{},\"ended\":{},\"fog\":{},\"ml\":{},\"menu\":{},\"mstate\":{},\"endrow\":{},\"funds\":{funds:?}}}",
        d.tick,
        mover == me as i32,
        snap.decided,
        snap.turn_ended,
        snap.fog,
        snap.main_loop,
        core.raw_read_8(0x0300_14F0, -1),
        core.raw_read_8(0x0300_14E2, -1),
        core.raw_read_8(crate::pvp::END_ROW, -1) & 0xF
    );
    // The unit list and the property owners, compared with the last look.
    let mut units = std::collections::BTreeMap::new();
    let mut carried = std::collections::BTreeMap::new();
    for u in &snap.units {
        if u.carried() {
            carried.insert(u.id, (u.kind as u32, u.owner));
        } else {
            units.insert(u.id, (u.kind as u32, u.owner, u.x, u.y, u.hp));
        }
    }
    let mut owners = std::collections::BTreeMap::new();
    for p in &snap.properties {
        owners.insert(p.y as u32 * 64 + p.x as u32, p.owner);
    }
    let mut acts: Vec<String> = Vec::new();
    if d.ready {
        for (id, &(kind, a, x, y, hp)) in &units {
            match d.last_units.get(id) {
                None if d.last_carried.contains_key(id) => {}
                None => acts.push(format!(
                    "\"what\":\"build\",\"actor\":{a},\"unit\":{kind},\"to\":[{x},{y}],\"hp\":[0,{hp}]"
                )),
                Some(&(_, _, ox, oy, ohp)) => {
                    if (ox, oy) != (x, y) {
                        acts.push(format!("\"what\":\"move\",\"actor\":{a},\"unit\":{kind},\"from\":[{ox},{oy}],\"to\":[{x},{y}],\"hp\":[{ohp},{hp}]"));
                    } else if hp < ohp {
                        acts.push(format!("\"what\":\"attack\",\"actor\":{army},\"unit\":{kind},\"owner\":{a},\"to\":[{x},{y}],\"hp\":[{ohp},{hp}]"));
                    }
                }
            }
        }
        for (id, &(kind, a)) in &carried {
            if !d.last_carried.contains_key(id) {
                acts.push(format!("\"what\":\"load\",\"actor\":{a},\"unit\":{kind},\"id\":{id}"));
            }
        }
        for (id, &(kind, a)) in &d.last_carried {
            if !carried.contains_key(id) {
                acts.push(format!("\"what\":\"unload\",\"actor\":{a},\"unit\":{kind},\"id\":{id}"));
            }
        }
        for (id, &(kind, a, x, y, hp)) in &d.last_units {
            if !units.contains_key(id) && !carried.contains_key(id) {
                acts.push(format!(
                    "\"what\":\"kill\",\"actor\":{army},\"unit\":{kind},\"owner\":{a},\"to\":[{x},{y}],\"hp\":[{hp},0]"
                ));
            }
        }
        for (&cell, &o) in &owners {
            if let Some(&old) = d.last_owner.get(&cell) {
                if old != o {
                    acts.push(format!(
                        "\"what\":\"capture\",\"actor\":{o},\"to\":[{},{}],\"from_owner\":{old}",
                        cell % 64,
                        cell / 64
                    ));
                }
            }
        }
    }
    // (an army out of the match: its HQ taken, or all its units gone)
    for a in 1..=armies {
        let alive = snap.armies[a as usize - 1].alive;
        if d.ready && d.last_alive[a as usize] && !alive {
            acts.push(format!("\"what\":\"eliminated\",\"actor\":{a}"));
        }
        d.last_alive[a as usize] = alive;
    }
    // (a CO Power or Super CO Power: the game's own count per army (crate::online_stats))
    for a in 1..=5u32 {
        let n = core.raw_read_8(crate::online_stats::POWERS + a, -1);
        if d.ready && n > d.last_powers[a as usize] {
            acts.push(format!("\"what\":\"power\",\"actor\":{a},\"count\":{n}"));
        }
        d.last_powers[a as usize] = n;
    }
    d.ready = true;
    d.last_carried = carried;
    d.last_units = units;
    d.last_owner = owners;
    if !acts.is_empty() {
        // The cells THIS window's seat sees: its own last view when it is waiting, the displayed plane when it is the
        // mover's own window.
        let plane: String = match (mover == me as i32, crate::fog_view::seat_vision(me)) {
            (false, Some((vw, vh, cells))) if vw as u32 == w && vh as u32 == h => (0..h)
                .flat_map(|y| (0..w).map(move |x| (x, y)))
                .map(|(x, y)| {
                    if cells.get((y * w + x) as usize).copied().unwrap_or(false) {
                        '1'
                    } else {
                        '0'
                    }
                })
                .collect(),
            _ => crate::inspect::seen_plane(core, w, h),
        };
        for a in acts {
            let _ = writeln!(
                d.file,
                "{{\"ms\":{now},\"tick\":{},\"k\":\"act\",{a},\"seat\":{me},\"army\":{army}}}",
                d.tick
            );
        }
        let _ = writeln!(d.file, "{{\"ms\":{now},\"tick\":{},\"k\":\"seen\",\"army\":{army},\"of_seat\":{me},\"w\":{w},\"h\":{h},\"cells\":\"{plane}\"}}", d.tick);
        let _ = d.file.flush();
    }
}
