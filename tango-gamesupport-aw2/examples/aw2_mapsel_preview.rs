//! the online SELECT MAP with 2..5 fake seats (BMPs into <out-dir>), and a map chosen through it.
//!
//! Usage: [AW2_SHARED_ART=1 TANGOAW2_DS_ROM=<nds>] aw2_mapsel_preview <rom> <save> <out-dir> <players> [script]
//!
//! Boots a room's console (as a netplay match with `players` seats; the extra seats' pads are never touched), waits
//! for SELECT MAP's page, then plays the script from seat 0: `D` down, `U` up, `L`/`R` left/right, `A`, `B`, `w`
//! wait, `s:NAME` write NAME.bmp. Default: a shot, three downs, a shot, right, a shot, A, and the Teams screen's map.
use tango_match::{HostInput, Link};

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
    let script = args.get(5).cloned().unwrap_or_else(|| "s:a DDD w s:b R w s:c A w".to_string());
    std::fs::create_dir_all(&out).ok();
    let shared = std::env::var_os("AW2_SHARED_ART").is_some();
    let mt = (0u8, if shared { tango_gamesupport_aw2::ds_art::SHARED_ART } else { 0 } | tango_gamesupport_aw2::online::ONLINE_MATCH);
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    tango_gamesupport_aw2::ds_pack::pack();
    let mut link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, Some(mt), None).expect("boot");
    link.set_players(players);
    let names: Vec<String> = ["Hostname", "Guest", "Nell", "Gamertag10", "Fifth"][..players].iter().map(|s| s.to_string()).collect();
    tango_gamesupport_aw2::online::set_room(names, 0);
    let tick = |link: &mut tango_backend_mgba::SharedLink, k0: u32| {
        link.tick([HostInput::keys(k0), HostInput::keys(0)]);
    };
    for t in 0..8000 {
        tick(&mut link, 0);
        if t > 100 && tango_gamesupport_aw2::online_maps::idle(link.core_mut()) {
            break;
        }
    }
    for _ in 0..60 {
        tick(&mut link, 0);
    }
    let press = |link: &mut tango_backend_mgba::SharedLink, k: u32| {
        for _ in 0..4 {
            tick(link, k);
        }
        for _ in 0..8 {
            tick(link, 0);
        }
    };
    for tok in script.split_whitespace() {
        if let Some(name) = tok.strip_prefix("s:") {
            for _ in 0..10 {
                tick(&mut link, 0);
            }
            let f = link.side(0).frame().expect("frame");
            write_bmp(&out.join(format!("{name}.bmp")), &f);
            continue;
        }
        for c in tok.chars() {
            match c {
                'D' => press(&mut link, 1 << 7),
                'U' => press(&mut link, 1 << 6),
                'L' => press(&mut link, 1 << 5),
                'R' => press(&mut link, 1 << 4),
                'A' => press(&mut link, 1),
                'B' => press(&mut link, 2),
                'w' => (0..120).for_each(|_| tick(&mut link, 0)),
                _ => {}
            }
        }
    }
    if std::env::var_os("AW2_LIST").is_some() {
        let c = link.core_mut();
        for n in 2..=5 {
            for pre in [false, true] {
                for m in tango_gamesupport_aw2::online_maps::list(c, n, pre) {
                    println!("LIST {n}P pre={pre} {:02x} {:24} {}x{} props {} bases {}", m.id, m.name, m.w, m.h, m.props, m.bases);
                }
            }
        }
    }
    let c = link.core_mut();
    println!(
        "players {players}: map id {:02x}, teams {}, record armies {}, list idle {}",
        c.raw_read_8(0x0300_3FC2, -1),
        tango_gamesupport_aw2::pvp::on_teams_screen(c),
        c.raw_read_8(0x0201_7C58, -1),
        tango_gamesupport_aw2::online_maps::idle(c)
    );
}
