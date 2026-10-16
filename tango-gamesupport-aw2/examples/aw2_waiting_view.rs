//! A room's match on one console (no network), every seat's window written to BMPs: the waiting seats' pictures
//! (crate::fog_view) with the mover's HUD, cursor and panel handling checked.
//!
//! Usage: [AW2_SHARED_ART=1 TANGOAW2_DS_ROM=<nds>] aw2_waiting_view <rom> <save> <out-dir> <players> <script-file>
//!
//! Script tokens (whitespace separated): `@N` presses come from seat N; `A B D U L R S` press that button (6 ticks
//! held, 10 released); `wN` wait N ticks; `s:NAME` write NAME_seatK.bmp for every seat; `c:X,Y` walk the map cursor
//! (seat's own) to tile X,Y; `fog` turns Fog of War on in the rules page (not needed with the map's rule).
use tango_match::{HostInput, Link};

const CURSOR_X: u32 = 0x0300_33E4;
const CURSOR_Y: u32 = 0x0300_33E6;

fn write_bmp(path: &std::path::Path, rgba: &[u8]) {
    let (w, h) = (240u32, 160u32);
    let mut out = Vec::new();
    out.extend_from_slice(b"BM");
    out.extend_from_slice(&(54 + w * h * 3).to_le_bytes());
    out.extend_from_slice(&[0, 0, 0, 0, 54, 0, 0, 0, 40, 0, 0, 0]);
    out.extend_from_slice(&(w as i32).to_le_bytes());
    out.extend_from_slice(&(-(h as i32)).to_le_bytes());
    out.extend_from_slice(&[1, 0, 24, 0]);
    out.extend_from_slice(&[0u8; 24]);
    for px in rgba.chunks(4) {
        out.extend_from_slice(&[px[2], px[1], px[0]]);
    }
    std::fs::write(path, out).unwrap();
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let save = std::fs::read(&args[2]).expect("save");
    let out = std::path::PathBuf::from(&args[3]);
    let players: usize = args[4].parse().unwrap();
    let script = std::fs::read_to_string(&args[5]).expect("script");
    std::fs::create_dir_all(&out).ok();
    let shared = std::env::var_os("AW2_SHARED_ART").is_some();
    let mt = (0u8, if shared { tango_gamesupport_aw2::ds_art::SHARED_ART } else { 0 } | tango_gamesupport_aw2::online::ONLINE_MATCH);
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    tango_gamesupport_aw2::ds_pack::pack();
    if std::env::var("AW2_TILT").is_ok_and(|v| v == "1") {
        tango_gamesupport_aw2::ds_graphics::set_enabled(true);
    }
    let mut link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, Some(mt), None).expect("boot");
    link.set_players(players);
    let names: Vec<String> = ["Hostname", "Guest", "Nell", "Gamertag10", "Fifth"][..players].iter().map(|s| s.to_string()).collect();
    tango_gamesupport_aw2::online::set_room(names, 0);
    let mut seat = 0usize;
    let tick = |link: &mut tango_backend_mgba::SharedLink, seat: usize, k: u32| {
        let mut a = [HostInput::keys(0), HostInput::keys(0)];
        match seat {
            0 => a[0].keys = k,
            1 => a[1].keys = k,
            s => a[1].extra[s - 2] = k as u16,
        }
        link.tick(a);
        // (the console's own picture every tick: the Teams page's presses are read only while pictures are made)
        let _ = link.side(0).frame();
    };
    for _ in 0..400 {
        tick(&mut link, 0, 0);
    }
    for tok in script.split_whitespace() {
        if let Some(n) = tok.strip_prefix('@') {
            seat = n.parse().unwrap();
        } else if let Some(name) = tok.strip_prefix("s:") {
            for _ in 0..10 {
                tick(&mut link, seat, 0);
            }
            for s in 0..players {
                if let Some(f) = link.side(s).frame() {
                    write_bmp(&out.join(format!("{name}_seat{s}.bmp")), &f);
                }
            }
        } else if tok == "dbg" {
            let c = link.core();
            let mut b = [0u8; 0x60];
            c.raw_read_range(0x0203_CB00, -1, &mut b);
            println!("sel: init {} done {} players {} | ready {:?} | on teams {} | armies {} map {:02x}", b[0], b[1], b[2], (0..3).map(|s| b[0x10 + 0x10 * s + 4]).collect::<Vec<_>>(), tango_gamesupport_aw2::pvp::on_teams_screen(c), c.raw_read_8(0x0201_7C58, -1), c.raw_read_8(0x0300_3FC2, -1));
        } else if tok == "rec" {
            let mut b = [0u8; 0x60];
            link.core().raw_read_range(0x0201_7C50, -1, &mut b);
            println!("rec {:02x?}", b);
        } else if tok == "trace" {
            for i in 0..120 {
                tick(&mut link, seat, if i < 6 { 1 } else { 0 });
                let c = link.core();
                if i % 2 == 0 {
                    let tasks: Vec<String> = (0x0300_1500u32..0x0300_1A00).step_by(4).filter_map(|a| { let v = c.raw_read_32(a, -1); ((0x0800_0000..0x0A00_0000).contains(&v) && v & 1 == 1).then(|| format!("{v:x}")) }).collect();
                    println!("tasks {tasks:?}");
                    println!("{i}: init {} done {} pulse {} ready {} {} {} teams {} loop {:08x}", c.raw_read_8(0x0203_CB00, -1), c.raw_read_8(0x0203_CB01, -1), c.raw_read_8(0x0203_CB03, -1), c.raw_read_8(0x0203_CB14, -1), c.raw_read_8(0x0203_CB24, -1), c.raw_read_8(0x0203_CB34, -1), tango_gamesupport_aw2::pvp::on_teams_screen(c), c.raw_read_32(0x0300_0000, -1));
                }
            }
        } else if let Some(n) = tok.strip_prefix('w') {
            (0..n.parse::<usize>().unwrap()).for_each(|_| tick(&mut link, seat, 0));
        } else if let Some(xy) = tok.strip_prefix("c:") {
            let (x, y) = xy.split_once(',').unwrap();
            let (x, y): (i32, i32) = (x.parse().unwrap(), y.parse().unwrap());
            for _ in 0..60 {
                let (cx, cy) = (link.core().raw_read_8(CURSOR_X, -1) as i32, link.core().raw_read_8(CURSOR_Y, -1) as i32);
                let key = if cx < x { 1 << 4 } else if cx > x { 1 << 5 } else if cy < y { 1 << 7 } else if cy > y { 1 << 6 } else { break };
                for _ in 0..4 {
                    tick(&mut link, seat, key);
                }
                for _ in 0..6 {
                    tick(&mut link, seat, 0);
                }
            }
            (0..20).for_each(|_| tick(&mut link, seat, 0));
        } else {
            for c in tok.chars() {
                let k = match c {
                    'D' => 1 << 7,
                    'U' => 1 << 6,
                    'L' => 1 << 5,
                    'R' => 1 << 4,
                    'A' => 1,
                    'B' => 2,
                    'S' => 1 << 3,
                    _ => continue,
                };
                (0..6).for_each(|_| tick(&mut link, seat, k));
                (0..10).for_each(|_| tick(&mut link, seat, 0));
            }
        }
    }
    let c = link.core_mut();
    println!("army {}, cursor {},{}", c.raw_read_8(0x0300_33EC, -1), c.raw_read_8(CURSOR_X, -1), c.raw_read_8(CURSOR_Y, -1));
}
