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
    let mode = (0u8, tango_gamesupport_aw2::online::ONLINE_MATCH | if ds { tango_gamesupport_aw2::ds_art::SHARED_ART } else { 0 });
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
    let vram_last: std::cell::RefCell<(Vec<u8>, Vec<u8>)> = Default::default();
    // (watch BASE TOL: every tick, until unwatch, the waiting seats' pictures are compared with the BASE shotall's)
    let watch: std::cell::RefCell<Option<(String, Vec<Vec<u8>>, usize, Vec<(usize, usize, usize)>, usize)>> = std::cell::RefCell::new(None);
    let tick = |link: &mut tango_backend_mgba::SharedLink, keys: &[u32]| {
        let inputs: Vec<HostInput> = keys.iter().map(|&k| HostInput::keys(k)).collect();
        link.tick_n(&inputs);
        let t = ticks.get() + 1;
        ticks.set(t);
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
            // consoleis SEAT: SEAT's window shows the console's own picture (the mover's: its cursor, its menus), exit 1 otherwise
            // notconsole SEATS: none of those seats' windows shows it (waiting seats: never the mover's cursor, menus or ranges)
            "consoleis" | "notconsole" => {
                let seats: Vec<usize> = p[1].split(',').map(|v| v.parse().unwrap()).collect();
                let console = link.solo_side().frame().unwrap_or_default();
                for seat in seats {
                    tango_gamesupport_aw2::online::set_room(names.clone(), seat);
                    let f = link.side(seat).frame().unwrap_or_default();
                    let diff = f.chunks(4).zip(console.chunks(4)).filter(|(x, y)| x != y).count();
                    let same = diff == 0;
                    let ok = same == (p[0] == "consoleis");
                    println!("{} seat {seat}: {diff} pixels from the console's {}", p[0], if ok { "ok" } else { "FAIL" });
                    failed |= !ok;
                }
            }
            // fv: the game's state the waiting view decides from
            "fv" => {
                let c = link.core();
                let procs: Vec<String> = tango_gamesupport_aw2::fog_view::procs(c).iter().map(|f| format!("{f:08x}")).collect();
                {
                    use tango_backend_mgba::SharedGame;
                    let w: Vec<bool> = (0..n).map(|s| tango_gamesupport_aw2::pvp::AW2E.watching(c, s)).collect();
                    println!("watching {w:?}");
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
