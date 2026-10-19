//! A room of 3..5 players on one console, driven by a script (no network): the SELECT YOUR ARMY page with teams,
//! the battle the teams make (allies cannot attack each other, the waiting seats' fog pictures), and shots.
//!
//! Usage: aw2_room_teams <rom> <out-dir> <script>
//!
//! Script (blank lines and # comments skipped):
//!   n N               players (first line)
//!   wait N            N frames, nobody pressing
//!   press SEAT KEYS   SEAT holds KEYS (A B SELECT START RIGHT LEFT UP DOWN R L, `+`-joined) 4 frames, then 6 idle
//!   until COND MAX    wait for selectmap | teams | battle | turnended | army=N | maparmies=N (MAX x 10 frames)
//!   shot NAME SEAT    NAME_sSEAT.bmp: that seat's own window
//!   shotall NAME      the same for every seat
//!   same A B SEATS [TOL]  the seats' pictures of shots A and B (shotall) differ in at most TOL pixels (default 300: the
//!                     game's animations; a leaked page is thousands), exit 1 otherwise
//!   fv                print the main loop, the turn's army, the running procs and the waiting view's phase
//!   props ARMY        print the army's properties
//!   sel               print the page's per-seat state: CO colour team partner field ready
//!   rec               print the Teams record's teams and the battle's player blocks' teams, colours
//!   peek ADDR LEN     print bytes
//!   poke ADDR HEX     write bytes (hex string) after a few idle frames
//!   goto SEAT X Y     walk SEAT's cursor to the cell
//!   hash              print a hash of the console's work RAM (compare two runs)
//!   phase NAME        label the following samples (printed in the black-run report)
//!   AW2_SAMPLE=N      every N ticks (default off) every seat's window is sampled for blackness; at the end the longest
//!                     run of black samples (>99% of the picture above the status bar under luma 8) of each seat is
//!                     printed per phase, and the program exits 1 when one lasts over AW2_MAX_BLACK ticks (default 20); only seat pictures black while the
//!                     console's own is not count (the game's wipes are black everywhere).
//!                     AW2_DUMP=<dir> also writes every seat's picture at each sample (NAME_tTICK_sSEAT.bmp)
//!   AW2_DS=1 / TANGOAW2_DS_ROM: the Dual Strike pack, as with the other examples.

use tango_match::{HostInput, Link};

fn key_bits(s: &str) -> u32 {
    s.split('+')
        .map(|k| match k.to_ascii_uppercase().as_str() {
            "A" => 1,
            "B" => 1 << 1,
            "SELECT" => 1 << 2,
            "START" => 1 << 3,
            "RIGHT" => 1 << 4,
            "LEFT" => 1 << 5,
            "UP" => 1 << 6,
            "DOWN" => 1 << 7,
            "R" => 1 << 8,
            "L" => 1 << 9,
            _ => 0,
        })
        .fold(0, |a, b| a | b)
}

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
    let out = std::path::PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    let script = std::fs::read_to_string(&args[3]).expect("script");
    let mut lines = script.lines().map(str::trim).filter(|l| !l.is_empty() && !l.starts_with('#'));
    let n: usize = lines.next().and_then(|l| l.strip_prefix("n ")).expect("first line: n N").parse().unwrap();
    let ds = std::env::var_os("TANGOAW2_DS_ROM").is_some();
    if ds {
        tango_gamesupport_aw2::ds_pack::pack();
    }
    // (AW2_PACK_ONLY: this peer has the pack but the match does not, as in a room with a player who has none)
    let shared = ds && std::env::var_os("AW2_PACK_ONLY").is_none();
    let mode = (0u8, tango_gamesupport_aw2::online::ONLINE_MATCH | if shared { tango_gamesupport_aw2::ds_art::SHARED_ART } else { 0 });
    let names: Vec<String> = ["Hostname", "Guest", "Guest3", "Guest4", "Guest5"][..n].iter().map(|s| s.to_string()).collect();
    tango_gamesupport_aw2::online::set_room(names.clone(), 0);
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    let mut link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, Some(mode), None).expect("boot");
    link.set_players(n);
    for seat in 0..n {
        link.side(seat).set_render(true);
    }
    let sample_every: usize = std::env::var("AW2_SAMPLE").ok().and_then(|v| v.parse().ok()).unwrap_or(0);
    let max_black: usize = std::env::var("AW2_MAX_BLACK").ok().and_then(|v| v.parse().ok()).unwrap_or(20);
    let dump = std::env::var_os("AW2_DUMP").map(std::path::PathBuf::from);
    if let Some(d) = &dump {
        std::fs::create_dir_all(d).unwrap();
    }
    // (per seat: current black run start and length in ticks, longest run with its phase and start tick)
    #[derive(Clone, Default)]
    struct Run {
        cur: usize,
        longest: usize,
        at: usize,
        phase: String,
        cur_start: usize,
        phase_now: String,
    }
    let runs = std::cell::RefCell::new(vec![Run::default(); n]);
    let ticks = std::cell::Cell::new(0usize);
    let native = std::cell::Cell::new(0usize);
    let phase = std::cell::RefCell::new(String::from("start"));
    let merge_last = std::cell::RefCell::new(String::new());
    // (AW2_LEAK_CHECK=1: every tick, no watching seat may show the console's picture)
    let leak_check = std::env::var_os("AW2_LEAK_CHECK").is_some();
    let leaks: std::cell::RefCell<Vec<(usize, usize, String)>> = Default::default();
    let power_ticks = std::cell::Cell::new((0usize, 0usize));
    let power_ticks_nofog = std::cell::Cell::new(0usize);
    let tag_ticks = std::cell::Cell::new(0usize);
    let super_nofog = std::cell::Cell::new((0usize, 0usize));
    let vram_last: std::cell::RefCell<(Vec<u8>, Vec<u8>)> = Default::default();
    // (watch BASE TOL: every tick, until unwatch, the waiting seats' pictures are compared with the BASE shotall's)
    let watch: std::cell::RefCell<Option<(String, Vec<Vec<u8>>, usize, Vec<(usize, usize, usize)>, usize)>> = std::cell::RefCell::new(None);
    let tick = |link: &mut tango_backend_mgba::SharedLink, keys: &[u32]| {
        // (the maps are picked in private: every seat's window keeps a console of its own, driven by its keys, and the pick it makes
        // goes out as two words of the seat's input, as the session sends them)
        let picking = tango_gamesupport_aw2::unranked::picking(link.core());
        let mut sent = keys.to_vec();
        if picking {
            for (seat, k) in sent.iter_mut().enumerate() {
                tango_gamesupport::private::set_keys(seat, *k);
                if let Some(word) = tango_gamesupport::private::next_word(seat) {
                    *k = word;
                }
            }
        }
        let inputs: Vec<HostInput> = sent.iter().map(|&k| HostInput::keys(k)).collect();
        tango_match::Link::test_aid(link, ticks.get() as u32);
        link.tick_n(&inputs);
        let t = ticks.get() + 1;
        ticks.set(t);
        if picking && t % 2 == 0 {
            for seat in 0..n {
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let _ = link.side(seat).frame();
            }
        }
        if let Ok(path) = std::env::var("AW2_HASH_LOG") {
            // (test aid: one line per tick, FNV hashes of the console's IWRAM and EWRAM, and every 30 ticks of its ROM, VRAM, palette and OAM;
            // run the same script with and without the Dual Strike pack (AW2_PACK_ONLY) and diff the two files: they must be equal)
            use std::io::Write;
            let fnv = |b: &[u8]| b.iter().fold(0xcbf29ce484222325u64, |h, x| (h ^ *x as u64).wrapping_mul(0x100000001b3));
            let c = link.core();
            let mut line = String::new();
            let mut buf = vec![0u8; 0x8000];
            c.raw_read_range(0x0300_0000, -1, &mut buf);
            line += &format!("{t} iw {:016x}", fnv(&buf));
            let mut buf = vec![0u8; 0x40000];
            c.raw_read_range(0x0200_0000, -1, &mut buf);
            line += &format!(" ew {:016x}", fnv(&buf));
            if t % 30 == 0 {
                for (name, at, len) in [("rom", 0x0800_0000u32, 0x0080_0000usize), ("vram", 0x0600_0000, 0x18000), ("pal", 0x0500_0000, 0x400), ("oam", 0x0700_0000, 0x400)] {
                    let mut buf = vec![0u8; len];
                    c.raw_read_range(at, -1, &mut buf);
                    line += &format!(" {name} {:016x}", fnv(&buf));
                }
            }
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&path) {
                let _ = writeln!(f, "{line}");
            }
        }
        if let Some(t0) = std::env::var("AW2_RAM_DUMP").ok().and_then(|v| v.parse::<usize>().ok()).filter(|&a| a == t) {
            // (test aid: the whole console at that tick, in AW2_RAM_DIR)
            if let Ok(dir) = std::env::var("AW2_RAM_DIR") {
                let c = link.core();
                for (name, at, len) in [("rom", 0x0800_0000u32, 0x0080_0000usize), ("vram", 0x0600_0000, 0x18000), ("pal", 0x0500_0000, 0x400), ("oam", 0x0700_0000, 0x400), ("iw", 0x0300_0000, 0x8000), ("ew", 0x0200_0000, 0x40000)] {
                    let mut buf = vec![0u8; len];
                    c.raw_read_range(at, -1, &mut buf);
                    let _ = std::fs::write(format!("{dir}/{name}_{t0}.bin"), &buf);
                }
            }
        }
        if let Ok(range) = std::env::var("AW2_MEMSCAN") {
            // (test aid: "from-to": the console's IWRAM and EWRAM every tick in that range, files in /tmp/memscan)
            let (a, b) = range.split_once('-').map(|(x, y)| (x.parse::<usize>().unwrap_or(0), y.parse::<usize>().unwrap_or(0))).unwrap_or((0, 0));
            if (a..=b).contains(&(t as usize)) {
                let c = link.core();
                let mut iw = vec![0u8; 0x8000];
                c.raw_read_range(0x0300_0000, -1, &mut iw);
                let mut ew = vec![0u8; 0x40000];
                c.raw_read_range(0x0200_0000, -1, &mut ew);
                let dir = std::path::Path::new("/tmp/memscan");
                let _ = std::fs::create_dir_all(dir);
                let _ = std::fs::write(dir.join(format!("i{t}.bin")), &iw);
                let _ = std::fs::write(dir.join(format!("e{t}.bin")), &ew);
            }
        }
        if let Some((a, b)) = std::env::var("AW2_WATCH_LOG").ok().and_then(|v| v.split_once('-').map(|(a, b)| (a.parse::<usize>().unwrap_or(0), b.parse::<usize>().unwrap_or(0)))) {
            // (test aid: "from-to": what the game says about the waiting seats' pictures, tick by tick)
            if (a..=b).contains(&t) {
                use tango_backend_mgba::SharedGame;
                let c = link.core();
                eprintln!("watchlog t{t}: picking {} phase {:?} watching [{}, {}] selecting {} unranked-phase picks {} mask {:#x}", tango_gamesupport_aw2::unranked::picking(c), tango_gamesupport_aw2::fog_view::phase(c), tango_gamesupport_aw2::pvp::AW2E.watching(c, 0), tango_gamesupport_aw2::pvp::AW2E.watching(c, 1), 0, tango_gamesupport_aw2::unranked::picks_made(c), tango_gamesupport_aw2::unranked::picked_mask(c));
            }
        }
        if std::env::var_os("AW2_CONSOLE_PROCS").is_some() {
            // (the console's own running procs when they change: where a walk, a menu or a selection begins and ends)
            thread_local!(static LAST_P: std::cell::RefCell<Vec<u32>> = const { std::cell::RefCell::new(Vec::new()) });
            let p = tango_gamesupport_aw2::fog_view::procs(link.core());
            if LAST_P.with(|l| l.replace(p.clone())) != p {
                eprintln!("consoleprocs tick {t} {p:x?}");
            }
        }
        if std::env::var("AW2_CAM_LOG").is_ok_and(|v| v == "ticks") {
            eprintln!("tickmark {t}");
        }
        if std::env::var_os("AW2_CAM_LOG").is_some() {
            // (the console's own camera: where it moves, tick by tick, as the game scrolls to the mover)
            let c = link.core();
            let now = (c.raw_read_16(0x0201_E454, -1) as i16, c.raw_read_16(0x0201_E456, -1) as i16);
            thread_local!(static LAST: std::cell::Cell<(i16, i16)> = const { std::cell::Cell::new((0, 0)) });
            if LAST.with(|l| l.replace(now)) != now {
                eprintln!("concam tick {t} px ({}, {})", now.0, now.1);
            }
        }
        if leak_check {
            // a seat the game says is watching must never show the console's own picture (the mover's) unless that is dark
            use tango_backend_mgba::SharedGame;
            let console = link.solo_side().frame().unwrap_or_default();
            let dark = console.chunks(4).filter(|px| (px[0] as u32 + px[1] as u32 + px[2] as u32) < 30).count() * 10 > 9 * 38400;
            // (a seat the game says is NOT watching shows the console's own picture: any other picture is stale)
            for seat in 0..n {
                if (1..=5).contains(&link.core().raw_read_8(0x0300_33EC, -1)) && !tango_gamesupport_aw2::pvp::AW2E.watching(link.core(), seat) {
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    if diff > 3000 {
                        leaks.borrow_mut().push((t, seat, format!("not watching but shows another picture ({diff} px) {:?}", tango_gamesupport_aw2::fog_view::phase(link.core()))));
                    }
                }
            }
            // (and the mover's cursor on the console: no other seat may show that picture, watching or not)
            let cursor_up = {
                let c = link.core();
                let (start, end) = (c.raw_read_32(0x0300_0268, -1), c.raw_read_32(0x0300_2F2C, -1));
                let mut up = false;
                let mut at = start;
                while (0x0300_0000..0x0300_8000).contains(&start) && at + 8 <= end && end - start <= 1024 {
                    let (a0, a2) = (c.raw_read_16(at, -1), c.raw_read_16(at + 4, -1));
                    up |= a2 >> 12 == 1 && matches!(a2 & 0x3FF, 0x365 | 0x369) && a0 & 0x300 != 0x200;
                    at += 8;
                }
                up
            };
            let army = link.core().raw_read_8(0x0300_33EC, -1);
            // (a CO Power with fog: the cut-in frames are the console's for everybody, every other frame of the scene is a seat's
            // own map, never the console's)
            let (scene, cutin) = (tango_gamesupport_aw2::fog_view::power_scene(link.core()), tango_gamesupport_aw2::fog_view::power_cutin(link.core()));
            if scene && link.core().raw_read_8(0x0300_3FCD, -1) == 0 {
                // (without fog the scene is the console's for everybody)
                power_ticks_nofog.set(power_ticks_nofog.get() + 1);
                for seat in 0..n {
                    if tango_gamesupport_aw2::pvp::seat_of_n(army, n) == seat {
                        continue;
                    }
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    // (a Super CO Power without fog: its scene is the console's picture; the banner wipes in over the map and the scene
                    // fades out into it, frames that differ from the console's by the seat's own CO panel or a frame's lag: most of
                    // the scene's ticks must be equal, see the end)
                    if tango_gamesupport_aw2::pvp::chosen_main_item(link.core()) == Some(tango_gamesupport_aw2::pvp::MENU_SUPER) {
                        super_nofog.set((super_nofog.get().0 + 1, super_nofog.get().1 + (diff <= 3000) as usize));
                    } else if diff > 3000 {
                        leaks.borrow_mut().push((t, seat, format!("power scene (no fog) not the console's ({diff} px)")));
                    }
                }
            }
            // (a tag screen, CO SWAP or the Tag Power's: full screen, no map in it: every seat but the mover shows the console's picture; the
            // maps are picked in private: the windows are not the console's, see `private_picks`)
            let tag_screen = tango_gamesupport_aw2::tag_extras::screen_up(link.core()) || tango_gamesupport_aw2::fog_view::power_screen(link.core());
            if tag_screen {
                tag_ticks.set(tag_ticks.get() + 1);
                if tango_gamesupport_aw2::fog_view::power_screen(link.core()) {
                    // (a Super CO Power's own screen counts as its full cut-in)
                    power_ticks.set((power_ticks.get().0, power_ticks.get().1 + 1));
                }
                for seat in 0..n {
                    if tango_gamesupport_aw2::pvp::seat_of_n(army, n) == seat {
                        continue;
                    }
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    if diff > 300 && !dark {
                        leaks.borrow_mut().push((t, seat, format!("tag screen not shown ({diff} px)")));
                    }
                }
            }
            let skip_generic = tag_screen || tango_gamesupport_aw2::unranked::picking(link.core()) || (scene && link.core().raw_read_8(0x0300_3FCD, -1) != 0);
            if skip_generic && !tag_screen && scene && link.core().raw_read_8(0x0300_3FCD, -1) != 0 {
                power_ticks.set((power_ticks.get().0 + 1, power_ticks.get().1 + cutin as usize));
                for seat in 0..n {
                    if tango_gamesupport_aw2::pvp::seat_of_n(army, n) == seat {
                        continue;
                    }
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    if cutin && diff > 3000 {
                        leaks.borrow_mut().push((t, seat, format!("power cut-in not shown ({diff} px)")));
                    }
                    if !cutin && !dark && diff <= 300 {
                        leaks.borrow_mut().push((t, seat, "power scene frame is the mover's map".to_string()));
                    }
                }
            }
            for seat in (0..n).filter(|_| !skip_generic) {
                let mover = (1..=5).contains(&army) && tango_gamesupport_aw2::pvp::seat_of_n(army, n) == seat;
                if cursor_up && !mover && !dark {
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    if f == console {
                        leaks.borrow_mut().push((t, seat, format!("cursor shown {:?} army {army}", tango_gamesupport_aw2::fog_view::phase(link.core()))));
                    }
                    continue;
                }
                // (with fog: a watching seat never shows the console's picture; without it the game's animations are shown as they
                // are and only the mover's cursor above is checked)
                if link.core().raw_read_8(0x0300_3FCD, -1) == 0 || !tango_gamesupport_aw2::pvp::AW2E.watching(link.core(), seat) {
                    continue;
                }
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let f = link.side(seat).frame().unwrap_or_default();
                if !dark && f == console {
                    leaks.borrow_mut().push((t, seat, format!("{:?} army {}", tango_gamesupport_aw2::fog_view::phase(link.core()), link.core().raw_read_8(0x0300_33EC, -1))));
                }
            }
        }
        if std::env::var_os("AW2_MERGE_CHECK").is_some() {
            // which seat's keys the console would take now: every seat presses its own bit
            let c = link.core();
            let seats: Vec<u32> = (0..n).map(|i| 1u32 << i).collect();
            let real = tango_gamesupport_aw2::online::merge(c, keys);
            if real.is_some_and(|w| w != 0) {
                println!("  t{t}: keys {:?} -> console word {:x} cursor y {}", keys, real.unwrap(), c.raw_read_16(0x0300_33E6, -1));
            }
            let word = tango_gamesupport_aw2::online::merge(c, &seats);
            let src = word.map(|w| if w == 0 { "none".to_string() } else { format!("{}", w.trailing_zeros()) }).unwrap_or_else(|| "pass".into());
            let ph = tango_gamesupport_aw2::fog_view::phase(c);
            let army = c.raw_read_8(0x0300_33EC, -1);
            let key = format!("src {src} army {army} phase {ph:?}");
            let mut last = merge_last.borrow_mut();
            if *last != key {
                println!("merge t{t}: {key}");
                *last = key;
            }
        }
        if let Some((a, b)) = std::env::var("AW2_TRACE").ok().and_then(|v| v.split_once('-').map(|(a, b)| (a.parse::<usize>().unwrap(), b.parse::<usize>().unwrap()))) {
            if (a..b).contains(&t) {
                let c = link.core();
                let procs: Vec<String> = tango_gamesupport_aw2::fog_view::procs(c).iter().map(|f| format!("{:x}", f & 0xFFFFFF)).collect();
                let io = |o: u32| c.raw_read_16(0x0400_0000 + o, -1);
                println!("trace t{t} army {} mm {}/{} keys {:03x} loop {:08x} phase {:?} disp {:04x} win {:04x}/{:04x} bld {:04x}/{:04x}/{:02x} mos {:04x} procs [{}]", c.raw_read_8(0x0300_33EC, -1), c.raw_read_8(0x0300_14E2, -1), c.raw_read_8(0x0300_14F0, -1), keys.iter().fold(0, |a, b| a | b), c.raw_read_32(0x0300_0000, -1), tango_gamesupport_aw2::fog_view::phase(c), io(0), io(0x48), io(0x4A), io(0x50), io(0x52), io(0x54), io(0x4C), procs.join(" "));
            }
        }
        // AW2_VRAMDIFF=A-B: every tick in A..B, the VRAM tiles (32 bytes) and palette entries that changed since the tick before
        if let Some((a, b)) = std::env::var("AW2_VRAMDIFF").ok().and_then(|v| v.split_once('-').map(|(a, b)| (a.parse::<usize>().unwrap(), b.parse::<usize>().unwrap()))) {
            if (a..b).contains(&t) {
                let mut now = vec![0u8; 0x18000];
                link.peek(0x0600_0000, &mut now);
                let mut pal = vec![0u8; 0x400];
                link.peek(0x0500_0000, &mut pal);
                let mut last = vram_last.borrow_mut();
                if !last.0.is_empty() {
                    let ch: Vec<String> = (0..0x18000 / 32).filter(|i| now[i * 32..i * 32 + 32] != last.0[i * 32..i * 32 + 32]).map(|i| format!("{:x}", i)).collect();
                    let pc: Vec<String> = (0..0x200).filter(|i| pal[i * 2..i * 2 + 2] != last.1[i * 2..i * 2 + 2]).map(|i| format!("{:x}", i)).collect();
                    if !ch.is_empty() || !pc.is_empty() {
                        let procs: Vec<String> = tango_gamesupport_aw2::fog_view::procs(link.core()).iter().map(|f| format!("{:x}", f & 0xFFFFFF)).collect();
                        println!("vram t{t} loop {:08x} procs [{}] tiles({}) {} pal {}", link.core().raw_read_32(0x0300_0000, -1), procs.join(" "), ch.len(), ch.iter().take(40).cloned().collect::<Vec<_>>().join(","), pc.join(","));
                    }
                }
                *last = (now, pal);
            }
        }
        if let Some((label, base, tol, bad, count)) = watch.borrow_mut().as_mut() {
            for seat in 1..n {
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let Some(f) = link.side(seat).frame() else { continue };
                let diff = f.chunks(4).zip(base[seat].chunks(4)).filter(|(x, y)| x != y).count();
                if diff > *tol {
                    bad.push((t, seat, diff));
                    if let Some(d) = &dump {
                        write_bmp(&d.join(format!("{label}_t{t:06}_s{seat}_DIFF{diff}.bmp")), &f);
                    }
                }
            }
            *count += 1;
        }
        if sample_every > 0 && t % sample_every == 0 {
            for seat in 0..n {
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let Some(f) = link.side(seat).frame() else { continue };
                let top = &f[..f.len() * 140 / 160];
                let dark = top.chunks(4).filter(|p| (p[0] as u32 * 30 + p[1] as u32 * 59 + p[2] as u32 * 11) / 100 < 8).count();
                let frac = dark as f64 / (top.len() / 4) as f64;
                // (a fault: the seat's picture is black and the console's own is not; the game's wipes are black everywhere)
                let console_black = {
                    let c = link.solo_side().frame().unwrap_or_default();
                    let top = &c[..c.len() * 140 / 160];
                    top.chunks(4).filter(|p| (p[0] as u32 * 30 + p[1] as u32 * 59 + p[2] as u32 * 11) / 100 < 8).count() * 100 > (top.len() / 4) * 99
                };
                let black = frac > 0.99 && !console_black;
                if frac > 0.99 && console_black {
                    native.set(native.get() + sample_every);
                }
                let mut r = runs.borrow_mut();
                let r = &mut r[seat];
                if black {
                    if r.cur == 0 {
                        r.cur_start = t;
                        r.phase_now = phase.borrow().clone();
                    }
                    r.cur += sample_every;
                    if r.cur > r.longest {
                        r.longest = r.cur;
                        r.at = r.cur_start;
                        r.phase = r.phase_now.clone();
                    }
                } else {
                    r.cur = 0;
                }
                let from: usize = std::env::var("AW2_DUMP_FROM").ok().and_then(|v| v.parse().ok()).unwrap_or(0);
                let to: usize = std::env::var("AW2_DUMP_TO").ok().and_then(|v| v.parse().ok()).unwrap_or(usize::MAX);
                if let Some(d) = dump.as_ref().filter(|_| (from..to).contains(&t)) {
                    write_bmp(&d.join(format!("t{t:06}_s{seat}{}.bmp", if black { "_BLACK" } else { "" })), &f);
                }
            }
        }
    };
    let mut keys = vec![0u32; n];
    let rd = |link: &mut tango_backend_mgba::SharedLink, a: u32, len: usize| {
        let mut b = vec![0u8; len];
        link.peek(a, &mut b);
        b
    };
    let hex = |b: &[u8]| b.iter().map(|x| format!("{x:02x}")).collect::<Vec<_>>().join(" ");
    let parse = |s: &str| u32::from_str_radix(s.trim_start_matches("0x"), 16).unwrap();
    let mut shots: std::collections::HashMap<String, Vec<u8>> = Default::default();
    let mut failed = false;
    let mut t = 0usize;
    for line in lines {
        let p: Vec<&str> = line.split_whitespace().collect();
        match p[0] {
            "wait" => {
                for _ in 0..p[1].parse::<usize>().unwrap() {
                    tick(&mut link, &keys);
                    t += 1;
                }
            }
            "press" => {
                let seat: usize = p[1].parse().unwrap();
                let bits = key_bits(p[2]);
                for _ in 0..p.get(3).map_or(4, |v| v.parse().unwrap()) {
                    let mut k = vec![0; n];
                    k[seat] = bits;
                    tick(&mut link, &k);
                    t += 1;
                }
                for _ in 0..6 {
                    tick(&mut link, &keys);
                    t += 1;
                }
            }
            "until" => {
                let max: usize = p[2].parse().unwrap();
                let mut ok = false;
                for _ in 0..max * 10 {
                    let mut read = |_: u32, b: &mut [u8]| b.fill(0);
                    if tango_gamesupport_aw2::online::mailbox::condition(&mut read, p[1]) {
                        ok = true;
                        break;
                    }
                    tick(&mut link, &keys);
                    t += 1;
                }
                println!("until {} @{t}: {}", p[1], if ok { "ok" } else { "TIMEOUT" });
                // (AW2_STRICT_UNTIL=1: a wait that times out fails the run, except the map-select count, which the walk to SELECT MAP
                // does not always reach in time)
                if !ok && std::env::var_os("AW2_STRICT_UNTIL").is_some() && !p[1].starts_with("maparmies") {
                    failed = true;
                }
            }
            "shot" => {
                let seat: usize = p[2].parse().unwrap();
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                if let Some(f) = link.side(seat).frame() {
                    write_bmp(&out.join(format!("{}_s{seat}.bmp", p[1])), &f);
                    shots.insert(format!("{}_s{seat}", p[1]), f);
                }
            }
            "phase" => *phase.borrow_mut() = p[1].to_string(),
            // shotall NAME: every seat's window
            "shotall" => {
                for seat in 0..n {
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    if let Some(f) = link.side(seat).frame() {
                        write_bmp(&out.join(format!("{}_s{seat}.bmp", p[1])), &f);
                        shots.insert(format!("{}_s{seat}", p[1]), f);
                    }
                }
            }
            // same NAME1 NAME2 SEATS(comma list or all): the seats' pictures of the two shotall/shot names are identical
            // (a waiting seat's picture must not change with what the mover has open); exits 1 at the end when not
            "same" => {
                let seats: Vec<usize> = if p[3] == "all" { (0..n).collect() } else { p[3].split(',').map(|v| v.parse().unwrap()).collect() };
                for seat in seats {
                    let (a, b) = (shots.get(&format!("{}_s{seat}", p[1])), shots.get(&format!("{}_s{seat}", p[2])));
                    let diff = match (a, b) {
                        (Some(a), Some(b)) => a.chunks(4).zip(b.chunks(4)).filter(|(x, y)| x != y).count(),
                        _ => usize::MAX,
                    };
                    let tol: usize = p.get(4).map_or(300, |v| v.parse().unwrap());
                    println!("same {} {} seat {seat}: {} differing pixels {}", p[1], p[2], diff, if diff <= tol { "ok" } else { "FAIL" });
                    failed |= diff > tol;
                }
            }
            // watch LABEL BASE TOL: from now every tick the seats 1.. pictures are compared with the shotall BASE (dumped to
            // the out dir when AW2_DUMP is set, as LABEL_tTICK_sSEAT_DIFFn.bmp); unwatch LABEL: the report, exit 1 at the end
            "watch" => {
                let base: Vec<Vec<u8>> = (0..n).map(|seat| shots.get(&format!("{}_s{seat}", p[2])).cloned().unwrap_or_default()).collect();
                *watch.borrow_mut() = Some((p[1].to_string(), base, p[3].parse().unwrap(), Vec::new(), 0));
            }
            "unwatch" => {
                if let Some((label, _, tol, bad, count)) = watch.borrow_mut().take() {
                    let first = bad.first().map_or(String::new(), |b| format!(" first at tick {} seat {}", b.0, b.1));
                    let worst = bad.iter().map(|b| b.2).max().unwrap_or(0);
                    println!("watch {label}: {count} ticks, {} frames over {tol} differing pixels (worst {worst}){first} {}", bad.len(), if bad.is_empty() { "ok" } else { "FAIL" });
                    failed |= !bad.is_empty();
                }
            }
            // region NAME1 NAME2 SEATS(comma list or all) X0 Y0 X1 Y1 [TOL]: the seats' pictures of two shotall/shot names are identical
            // within the pixel box (240x160 screen); like `same` for a part of the picture (a banner's text row between armies)
            "region" => {
                let seats: Vec<usize> = if p[3] == "all" { (0..n).collect() } else { p[3].split(',').map(|v| v.parse().unwrap()).collect() };
                let b: Vec<usize> = p[4..8].iter().map(|v| v.parse().unwrap()).collect();
                let tol: usize = p.get(8).map_or(20, |v| v.parse().unwrap());
                for seat in seats {
                    let (a, c) = (shots.get(&format!("{}_s{seat}", p[1])), shots.get(&format!("{}_s{seat}", p[2])));
                    let diff = match (a, c) {
                        (Some(a), Some(c)) => (b[1]..b[3]).flat_map(|y| (b[0]..b[2]).map(move |x| y * 240 + x)).filter(|&i| a[i * 4..i * 4 + 4] != c[i * 4..i * 4 + 4]).count(),
                        _ => usize::MAX,
                    };
                    println!("region {} {} seat {seat}: {} differing pixels {}", p[1], p[2], diff, if diff <= tol { "ok" } else { "FAIL" });
                    failed |= diff > tol;
                }
            }
            // consoleis SEATS [TOL]: SEAT's window shows the console's own picture (the mover's: its cursor, its menus), exit 1 otherwise
            // notconsole SEATS: none of those seats' windows shows it (waiting seats: never the mover's cursor, menus or ranges)
            "consoleis" | "notconsole" => {
                let seats: Vec<usize> = p[1].split(',').map(|v| v.parse().unwrap()).collect();
                let console = link.solo_side().frame().unwrap_or_default();
                for seat in seats {
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    let tol: usize = p.get(2).map_or(0, |v| v.parse().unwrap());
                    let same = diff <= tol;
                    let ok = same == (p[0] == "consoleis");
                    println!("{} seat {seat}: {diff} pixels from the console's {}", p[0], if ok { "ok" } else { "FAIL" });
                    failed |= !ok;
                }
            }
            // aid CMD...: a test-aid command on the console (unit ARMY KIND X Y [HP], move, kill, funds, meter, poke ...)
            "aid" => {
                let cmd: Vec<String> = p[1..].iter().map(|s| s.to_string()).collect();
                tango_gamesupport_aw2::test_aid::run(link.core_mut(), ticks.get() as u32, &cmd);
            }
            // sprites: the sprite list the game copies to OAM at the flush (a0 a1 a2 per sprite), and the cursor's pixel position
            "sprites" => {
                let c = link.core();
                let (start, end) = (c.raw_read_32(0x0300_0268, -1), c.raw_read_32(0x0300_2F2C, -1));
                let sx = c.raw_read_16(0x0300_33E0, -1) as i16 as i32 - c.raw_read_16(0x0201_E454, -1) as i16 as i32;
                let sy = c.raw_read_16(0x0300_33E2, -1) as i16 as i32 - c.raw_read_16(0x0201_E456, -1) as i16 as i32;
                println!("sprites @{t}: cursor screen ({sx},{sy}) list {start:08x}..{end:08x}");
                if p.get(1) == Some(&"short") {
                    let mut v = Vec::new();
                    let mut at = start;
                    while at + 8 <= end && end - start <= 1024 {
                        let (a0, a1, a2) = (c.raw_read_16(at, -1), c.raw_read_16(at + 2, -1), c.raw_read_16(at + 4, -1));
                        let x = ((a1 & 0x1FF) as i32) << 23 >> 23;
                        if a2 >> 12 <= 3 && (a2 & 0x3FF) < 0x3C0 && (a2 & 0x3FF) != 0x352 && !(0x35e..=0x360).contains(&(a2 & 0x3FF)) {
                            v.push(format!("{:03x}p{}@{},{}", a2 & 0x3FF, a2 >> 12, x, a0 & 0xFF));
                        }
                        at += 8;
                    }
                    println!("  {}", v.join(" "));
                    continue;
                }
                let mut at = start;
                while at + 8 <= end && end - start <= 1024 {
                    let (a0, a1, a2) = (c.raw_read_16(at, -1), c.raw_read_16(at + 2, -1), c.raw_read_16(at + 4, -1));
                    let x = ((a1 & 0x1FF) as i32) << 23 >> 23;
                    println!("  spr x {x:4} y {:3} a0 {a0:04x} a1 {a1:04x} a2 {a2:04x} shape {} size {} tile {:03x} pal {} prio {} mode {}", a0 & 0xFF, a0 >> 14, a1 >> 14, a2 & 0x3FF, a2 >> 12, (a2 >> 10) & 3, (a0 >> 8) & 3);
                    at += 8;
                }
            }
            // consolesheet NAME N EVERY: N console pictures, EVERY ticks apart, as NAME_k.bmp
            "consoleshot" => {
                let (n_shots, every): (usize, usize) = (p[2].parse().unwrap(), p[3].parse().unwrap());
                for k in 0..n_shots {
                    let army = link.core().raw_read_8(0x0300_33EC, -1);
                    if let Some(f) = link.solo_side().frame() {
                        let dark = f.chunks(4).filter(|px| (px[0] as u32 + px[1] as u32 + px[2] as u32) < 30).count();
                        println!("console {} {k} @{t}: dark {dark}/38400 army {army}", p[1]);
                        write_bmp(&out.join(format!("{}_{k}.bmp", p[1])), &f);
                    }
                    for _ in 0..every {
                        tick(&mut link, &keys);
                        t += 1;
                    }
                }
            }
            // mash SEATS N: for N ticks every listed seat presses pseudo-random keys (a new set every 3 ticks), the others nothing
            "mash" => {
                let seats: Vec<usize> = p[1].split(',').map(|v| v.parse().unwrap()).collect();
                let mut x: u32 = 0x1234_5678 ^ t as u32;
                for i in 0..p[2].parse::<usize>().unwrap() {
                    if i % 3 == 0 {
                        for &s in &seats {
                            x = x.wrapping_mul(1664525).wrapping_add(1013904223);
                            // (A B SELECT START and the directions, L R: the reset chord is stripped by the game)
                            keys[s] = (x >> 8) & 0x3FF;
                        }
                    }
                    tick(&mut link, &keys);
                    t += 1;
                }
                for &s in &seats {
                    keys[s] = 0;
                }
            }
            // waitfor victory|over|armysel MAX: ticks (MAX x 10 at most) until the console shows VICTORY! / the match is over
            // (crate::online::match_over); fails the run when it does not come
            "waitfor" => {
                let max: usize = p[2].parse().unwrap();
                let mut ok = false;
                for _ in 0..max * 10 {
                    let c = link.core();
                    let now = match p[1] {
                        "victory" => tango_gamesupport_aw2::result_view::victory_showing(c),
                        "over" => tango_gamesupport_aw2::online::match_over(c),
                        // (the room is back on SELECT YOUR ARMY for the next match)
                        "armysel" => {
                            let mut read = |_: u32, b: &mut [u8]| b.fill(0);
                            tango_gamesupport_aw2::online::mailbox::condition(&mut read, "teams")
                        }
                        // (the room is on SELECT MAP for the next match)
                        "selectmap" => {
                            let mut read = |_: u32, b: &mut [u8]| b.fill(0);
                            tango_gamesupport_aw2::online::mailbox::condition(&mut read, "selectmap")
                        }
                        other => panic!("waitfor {other}"),
                    };
                    if now {
                        ok = true;
                        break;
                    }
                    // (waitfor COND MAX pressA SEATS: those seats press A for 4 ticks of every 60 while waiting)
                    let mut k = keys.clone();
                    if let (Some("pressA"), Some(list)) = (p.get(3).copied(), p.get(4)) {
                        if t % 60 < 4 {
                            for seat in list.split(',').filter_map(|v| v.parse::<usize>().ok()) {
                                k[seat] = 1;
                            }
                        }
                    }
                    tick(&mut link, &k);
                    t += 1;
                }
                println!("waitfor {} @{t}: {}", p[1], if ok { "ok" } else { "TIMEOUT FAIL" });
                failed |= !ok;
            }
            // expect winner SEAT: SEAT's window shows the console's picture (VICTORY!, then the result pages);
            // expect loser SEAT: it shows its own DEFEAT, not the console's
            // expect alive A,B,..: exactly those armies are still in the match
            "expect" if p[1] == "alive" => {
                let want: Vec<u8> = p[2].split(',').filter_map(|v| v.parse().ok()).collect();
                let have = tango_gamesupport_aw2::result_view::alive_armies(link.core());
                let ok = have == want;
                println!("expect alive {want:?}: {have:?} {}", if ok { "ok" } else { "FAIL" });
                failed |= !ok;
            }
            // expect roster A,B,C: the seats the console is played by, in its order, and that the page and the room agree
            // (`expect roster -`: the whole room); expect over: the match is over (the room fell to one player)
            "expect" if p[1] == "roster" => {
                let want: Vec<usize> = p[2].split(',').filter_map(|v| v.parse().ok()).collect();
                let c = link.core();
                let have = tango_gamesupport_aw2::proxy_seat::seat_order(c).unwrap_or_default();
                let size = if want.is_empty() { n } else { want.len() };
                let page = tango_gamesupport_aw2::online_teams::players(c);
                let room = tango_gamesupport_aw2::online::room_players();
                let named: Vec<String> = (0..size).map(tango_gamesupport_aw2::online::room_name).collect();
                let ok = have == want && page == size.clamp(2, 5) && room == size.clamp(2, 5);
                println!("expect roster {want:?}: order {have:?} page {page} room {room} names {named:?} departed {:#04x} {}", tango_gamesupport_aw2::proxy_seat::departed(c), if ok { "ok" } else { "FAIL" });
                failed |= !ok;
            }
            "expect" if p[1] == "over" => {
                let ok = tango_gamesupport_aw2::online::match_over(link.core());
                println!("expect over: {}", if ok { "ok" } else { "FAIL" });
                failed |= !ok;
            }
            "expect" => {
                let seat: usize = p[2].parse().unwrap();
                let console = link.solo_side().frame().unwrap_or_default();
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let f = link.side(seat).frame().unwrap_or_default();
                let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                let ok = match p[1] {
                    "winner" => diff <= 3000,
                    // (the game counts the seats still in the room)
                    "loser" => {
                        let game_seat = tango_gamesupport_aw2::online::room_seats().iter().position(|&p| p == seat).unwrap_or(seat);
                        tango_gamesupport_aw2::result_view::loser(link.core(), game_seat) && diff > 3000
                    }
                    other => panic!("expect {other}"),
                };
                println!("expect {} seat {seat}: {diff} px from the console's {}", p[1], if ok { "ok" } else { "FAIL" });
                failed |= !ok;
            }
            // unitcolours X Y SEAT MIN_PERCENT: the colours of the 16 x 16 pixels of cell (X, Y) in the console's picture (the mover's
            // unit, as the console has it) must appear on SEAT's window as often as MIN_PERCENT of their count on the console: the unit moved or done is drawn in
            // its owner's colours there too, not recoloured for the window's own army
            "unitcolours" => {
                let (x, y, seat, min): (i32, i32, usize, usize) = (p[1].parse().unwrap(), p[2].parse().unwrap(), p[3].parse().unwrap(), p[4].parse().unwrap());
                let (sx, sy) = {
                    let c = link.core();
                    (x * 16 - c.raw_read_16(0x0201_E454, -1) as i16 as i32, y * 16 - c.raw_read_16(0x0201_E456, -1) as i16 as i32)
                };
                let console = link.solo_side().frame().unwrap_or_default();
                let mut set = std::collections::HashSet::new();
                for py in sy.max(0)..(sy + 16).min(160) {
                    for px in sx.max(0)..(sx + 16).min(240) {
                        let o = 4 * (py as usize * 240 + px as usize);
                        set.insert([console[o], console[o + 1], console[o + 2]]);
                    }
                }
                // (the colours of the cell that are the map's too tell nothing: leave out those of the picture's other 16 x 16 blocks)
                let mut common = std::collections::HashSet::new();
                for by in 0..9 {
                    for bx in 0..15 {
                        if (bx * 16, by * 16) == (sx.div_euclid(16) * 16, sy.div_euclid(16) * 16) {
                            continue;
                        }
                        for py in by * 16..by * 16 + 16 {
                            for px in bx * 16..bx * 16 + 16 {
                                let o = 4 * (py as usize * 240 + px as usize);
                                common.insert([console[o], console[o + 1], console[o + 2]]);
                            }
                        }
                    }
                }
                set.retain(|c| !common.contains(c));
                tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                let f = link.side(seat).frame().unwrap_or_default();
                let n = f.chunks(4).filter(|px| set.contains(&[px[0], px[1], px[2]])).count();
                let n_console = console.chunks(4).filter(|px| set.contains(&[px[0], px[1], px[2]])).count();
                // (MIN percent of the console's own count)
                let ok = n * 100 >= n_console * min;
                println!("unitcolours ({x},{y}) seat {seat}: {} unit colours, {n} pixels on the window, {n_console} on the console (need {min}%) {}", set.len(), if ok { "ok" } else { "FAIL" });
                failed |= !ok;
            }
            // fv: the game's state the waiting view decides from
            "fv" => {
                let c = link.core();
                let procs: Vec<String> = tango_gamesupport_aw2::fog_view::procs(c).iter().map(|f| format!("{f:08x}")).collect();
                {
                    use tango_backend_mgba::SharedGame;
                    let w: Vec<bool> = (0..n).map(|s| tango_gamesupport_aw2::pvp::AW2E.watching(c, s)).collect();
                    println!("watching {w:?} alive {:?} decided {}", tango_gamesupport_aw2::result_view::alive_armies(c), tango_gamesupport_aw2::result_view::decided(c));
                }
                println!("fv @{t} tick {} army {}: fog {} loop {:08x} phase {:?} procs [{}] dispcnt {:04x} menu {}", ticks.get(), c.raw_read_8(0x0300_33EC, -1), c.raw_read_8(0x0300_3FCD, -1), c.raw_read_32(0x0300_0000, -1), tango_gamesupport_aw2::fog_view::phase(c), procs.join(" "), c.raw_read_16(0x0400_0000, -1), c.raw_read_8(0x0300_14E2, -1));
            }
            "status" => {
                let b = tango_gamesupport_aw2::online::probe::bits();
                println!("status @{t}: select_mode {} selectmap {} teams {} battle {} versus {} nav {} army {} sel_init {:?} loop {:08x}", b & 1, b >> 2 & 1, b >> 3 & 1, b >> 4 & 1, b >> 5 & 1, b >> 6 & 1, b >> 24 & 255, rd(&mut link, tango_gamesupport_aw2::online_teams::SEL, 4), link.core().raw_read_32(0x0300_0000, -1));
            }
            "sel" => {
                for s in 0..n {
                    let b = rd(&mut link, tango_gamesupport_aw2::online_teams::SEL + 0x10 + 0x10 * s as u32, 6);
                    println!("seat {s}: co {} colour {} partner {:02x} field {} ready {} team {}", b[0], b[1], b[2], b[3], b[4], b[5]);
                }
                println!("note {}", rd(&mut link, tango_gamesupport_aw2::online_teams::SEL + 4, 1)[0]);
            }
            "rec" => {
                let five = tango_gamesupport_aw2::five::active(link.core());
                let (team, colour, ctl) = if five { (0x0203_0300 + 0xA0, 0x0203_0300 + 0x98, 0x0203_0300 + 0x90) } else { (0x0201_7C50 + 0x11, 0x0201_7C50 + 0x0D, 0x0201_7C50 + 9) };
                println!("record: five {five} controller {} colour {} team {}", hex(&rd(&mut link, ctl, 5)), hex(&rd(&mut link, colour, 5)), hex(&rd(&mut link, team, 5)));
                for a in 1..=5u32 {
                    let base = if five { 0x0203_0000 + 0x3C * a } else { 0x0202_32C0 + 0x3C * a };
                    println!("army {a}: block {}", hex(&rd(&mut link, base, 0x3C)));
                }
            }
            // menuend SEAT: with the map menu open, DOWN until its cursor is on End, then A (the menu keeps its row between uses)
            "menuend" => {
                let seat: usize = p[1].parse().unwrap();
                for _ in 0..10 {
                    let cur = rd(&mut link, 0x0300_14F0, 1)[0] as u32;
                    let item = rd(&mut link, 0x0300_14A1 + cur.min(7), 1)[0];
                    if std::env::var_os("AW2_MENU_LOG").is_some() {
                        eprintln!("menu cursor {cur} item {item} items {:?}", rd(&mut link, 0x0300_14A1, 8));
                    }
                    let want: u8 = p.get(2).and_then(|v| v.parse().ok()).unwrap_or(6);
                    let mut k = vec![0; n];
                    k[seat] = if item == want { 1 } else { key_bits("DOWN") };
                    for _ in 0..4 {
                        tick(&mut link, &k);
                    }
                    for _ in 0..10 {
                        tick(&mut link, &keys);
                    }
                    if item == want {
                        break;
                    }
                }
            }
            // dump NAME: the console's IWRAM and EWRAM to /tmp/dump_NAME_i.bin / _e.bin (a test aid, to diff two runs)
            "dump" => {
                let c = link.core();
                let mut iw = vec![0u8; 0x8000];
                c.raw_read_range(0x0300_0000, -1, &mut iw);
                let mut ew = vec![0u8; 0x40000];
                c.raw_read_range(0x0200_0000, -1, &mut ew);
                let _ = std::fs::write(format!("/tmp/dump_{}_i.bin", p[1]), &iw);
                let _ = std::fs::write(format!("/tmp/dump_{}_e.bin", p[1]), &ew);
            }
            "peek" => println!("{} @{t}: {}", p[1], hex(&rd(&mut link, parse(p[1]), p[2].parse().unwrap()))),
            "poke" => {
                for _ in 0..4 {
                    tick(&mut link, &keys);
                }
                let bytes: Vec<u8> = (0..p[2].len() / 2).map(|i| u8::from_str_radix(&p[2][2 * i..2 * i + 2], 16).unwrap()).collect();
                link.poke(parse(p[1]), &bytes);
            }
            "goto" => {
                let seat: usize = p[1].parse().unwrap();
                let (x, y): (i32, i32) = (p[2].parse().unwrap(), p[3].parse().unwrap());
                for _ in 0..40 {
                    let c = rd(&mut link, 0x0300_33E4, 4);
                    let (cx, cy) = (c[0] as i32 | (c[1] as i32) << 8, c[2] as i32 | (c[3] as i32) << 8);
                    let key = if cx < x { "RIGHT" } else if cx > x { "LEFT" } else if cy < y { "DOWN" } else if cy > y { "UP" } else { break };
                    let mut k = vec![0; n];
                    k[seat] = key_bits(key);
                    for _ in 0..4 {
                        tick(&mut link, &k);
                    }
                    for _ in 0..6 {
                        tick(&mut link, &keys);
                    }
                }
            }
            "units" => {
                // every unit: army, id, kind, x, y, hp
                let base = link.core().raw_read_32(0x0849_9594, -1);
                for id in 1..255u32 {
                    let u = base + 12 * id;
                    let c = link.core();
                    if c.raw_read_8(u, -1) != 0 {
                        println!("unit id {id} army {} kind {} at ({},{}) hp {}", tango_gamesupport_aw2::five::army_of_index(c, id), c.raw_read_8(u, -1), c.raw_read_8(u + 2, -1), c.raw_read_8(u + 3, -1), c.raw_read_16(u + 4, -1) & 0x7f);
                    }
                }
            }
            // place ID X Y: move unit ID (both unit planes and its record) to an empty cell
            "place" => {
                let id: u32 = p[1].parse().unwrap();
                let (x, y): (u32, u32) = (p[2].parse().unwrap(), p[3].parse().unwrap());
                let m = 0x0201_E450u32;
                let base = link.core().raw_read_32(0x0849_9594, -1);
                let u = base + 12 * id;
                let (ox, oy) = (link.core().raw_read_8(u + 2, -1) as u32, link.core().raw_read_8(u + 3, -1) as u32);
                let row = |c: &mgba::core::Core, y: u32| c.raw_read_16(m + 0x417A + 2 * y, -1) as u32;
                let core = link.core_mut();
                for plane in [m + 0x12, m + 0x51A] {
                    let o = plane + row(core, oy) + ox;
                    let n = plane + row(core, y) + x;
                    assert_eq!(core.raw_read_8(n, -1), 0, "target cell is occupied");
                    core.raw_write_8(o, -1, 0);
                    core.raw_write_8(n, -1, id as u8);
                }
                core.raw_write_8(u + 2, -1, x as u8);
                core.raw_write_8(u + 3, -1, y as u8);
            }
            // kill ID: remove unit ID from the map (both planes and its record)
            "kill" => {
                let id: u32 = p[1].parse().unwrap();
                let m = 0x0201_E450u32;
                let base = link.core().raw_read_32(0x0849_9594, -1);
                let u = base + 12 * id;
                let (ox, oy) = (link.core().raw_read_8(u + 2, -1) as u32, link.core().raw_read_8(u + 3, -1) as u32);
                let row = link.core().raw_read_16(m + 0x417A + 2 * oy, -1) as u32;
                let core = link.core_mut();
                for plane in [m + 0x12, m + 0x51A] {
                    core.raw_write_8(plane + row + ox, -1, 0);
                }
                core.raw_write_range(u, -1, &[0u8; 12]);
            }
            // hq: where each army's HQ is
            "hq" => {
                let m = 0x0201_E450u32;
                let c = link.core();
                let (w, h) = (c.raw_read_16(m, -1) as u32, c.raw_read_16(m + 2, -1) as u32);
                for y in 0..h {
                    let row = c.raw_read_16(m + 0x417A + 2 * y, -1) as u32;
                    for x in 0..w {
                        let class = c.raw_read_8(m + 0x1432 + row + x, -1);
                        if class & 0x1F == 8 {
                            println!("hq of army {} at ({x},{y})", class >> 5);
                        }
                    }
                }
            }
            // props ARMY: that army's properties (terrain class low bits) with their cells
            "props" => {
                let m = 0x0201_E450u32;
                let c = link.core();
                let (w, h) = (c.raw_read_16(m, -1) as u32, c.raw_read_16(m + 2, -1) as u32);
                for y in 0..h {
                    let row = c.raw_read_16(m + 0x417A + 2 * y, -1) as u32;
                    for x in 0..w {
                        let class = c.raw_read_8(m + 0x1432 + row + x, -1);
                        if (class >> 5) as u32 == p[1].parse::<u32>().unwrap() {
                            println!("army {} kind {} at ({x},{y})", p[1], class & 0x1F);
                        }
                    }
                }
            }
            // vram NAME: the console's VRAM, palette and OAM to NAME.vram (for diffing two runs)
            "vram" => {
                let mut v = vec![0u8; 0x18000 + 0x400 + 0x400];
                link.peek(0x0600_0000, &mut v[..0x18000]);
                link.peek(0x0500_0000, &mut v[0x18000..0x18400]);
                link.peek(0x0700_0000, &mut v[0x18400..]);
                std::fs::write(out.join(format!("{}.vram", p[1])), v).unwrap();
            }
            "hash" => {
                let w = rd(&mut link, 0x0200_0000, 0x40000);
                let h = w.iter().fold(0xcbf29ce484222325u64, |h, &b| (h ^ b as u64).wrapping_mul(0x100000001b3));
                println!("hash @{t}: {h:016x}");
            }
            other => panic!("unknown command {other}"),
        }
    }
    if leak_check {
        if super_nofog.get().0 > 0 {
            let (total, same) = super_nofog.get();
            println!("super power without fog: {same} of {total} scene ticks equal to the console's picture");
            if same * 2 < total {
                leaks.borrow_mut().push((0, 0, format!("super power without fog: only {same} of {total} ticks show the console's picture")));
            }
        }
        let l = leaks.borrow();
        if tag_ticks.get() > 0 {
            println!("tag screens: {} ticks shown to every seat", tag_ticks.get());
        }
        if power_ticks_nofog.get() > 0 {
            println!("power scene without fog: {} ticks", power_ticks_nofog.get());
        }
        let (pt, pc) = power_ticks.get();
        if pt > 0 {
            println!("power scene: {pt} ticks, {pc} of them the full cut-in");
            failed |= pc == 0;
        }
        println!("leak check: {} ticks where a watching seat showed the console's picture{}", l.len(), l.first().map_or(String::new(), |(t, s, _)| format!(" (first tick {t} seat {s})")));
        let mut by: std::collections::BTreeMap<String, (usize, usize, usize)> = Default::default();
        for (t, _, ph) in l.iter() {
            let e = by.entry(ph.clone()).or_insert((0, *t, *t));
            e.0 += 1;
            e.2 = *t;
        }
        for (ph, (n, a, b)) in by {
            println!("  {ph}: {n} seat-ticks, ticks {a}..{b}");
        }
        failed |= !l.is_empty();
    }
    if failed {
        println!("SAME CHECK FAILED");
        std::process::exit(1);
    }
    if sample_every > 0 {
        let mut bad = false;
        for (seat, r) in runs.borrow().iter().enumerate() {
            println!("black seat {seat}: longest run {} ticks at tick {} (phase {})", r.longest, r.at, r.phase);
            bad |= r.longest > max_black;
        }
        println!("native black (console's own picture black too): {} seat-ticks", native.get());
        if bad {
            println!("BLACK RUN OVER {max_black} TICKS");
            std::process::exit(1);
        }
    }
}
