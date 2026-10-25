//! The skin on Versus' own Teams screen, offline: R on army 1 walks the six choices to the skin, army 2 never gets the
//! colour it sits on, and the battle keeps both. With `cpu` army 1 is made a CPU army and plays a while.
//!
//! Usage: aw2_skin_offline <rom> <out-dir> [cpu]

use tango_match::{HostInput, Link};

const A: u32 = 1;
const START: u32 = 1 << 3;
const RIGHT: u32 = 1 << 4;
const LEFT: u32 = 1 << 5;
const DOWN: u32 = 1 << 7;
const R: u32 = 1 << 8;

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
    // `cpu`: army 1 is a CPU army (the CPU plays the skin's army)
    let cpu = args.iter().skip(3).any(|a| a == "cpu");
    tango_gamesupport_aw2::ds_pack::pack();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let mut link =
        tango_backend_mgba::SharedLink::boot(&rom, Some(&save), None, &tango_gamesupport_aw2::pvp::AW2E, None, None)
            .expect("boot");
    let wait = |link: &mut tango_backend_mgba::SharedLink, n: u32| {
        for _ in 0..n {
            link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
    };
    let press = |link: &mut tango_backend_mgba::SharedLink, keys: u32| {
        for _ in 0..8 {
            link.tick([HostInput::keys(keys), HostInput::keys(0)]);
        }
        for _ in 0..6 {
            link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
    };
    let shot = |link: &mut tango_backend_mgba::SharedLink, name: &str| {
        write_bmp(&out.join(format!("{name}.bmp")), &link.side(0).frame().unwrap());
    };
    wait(&mut link, 700);
    press(&mut link, START);
    wait(&mut link, 300);
    press(&mut link, A);
    wait(&mut link, 150);
    press(&mut link, DOWN);
    wait(&mut link, 60);
    for _ in 0..3 {
        press(&mut link, A); // Versus, New, Bean Island
        wait(&mut link, 150);
    }
    let mut failed = false;
    let mut expect = |ok: bool, what: &str| {
        println!("{} {what}", if ok { "ok  " } else { "FAIL" });
        failed |= !ok;
    };
    shot(&mut link, "teams_0");
    expect(
        tango_gamesupport_aw2::army_skin::host_of(link.core(), 0) == 0,
        "no skin to begin with",
    );
    // R on army 1: Blue Moon, Yellow Comet, Green Earth, Black Hole, then the skin
    for i in 1..=4 {
        press(&mut link, R);
        wait(&mut link, 20);
        shot(&mut link, &format!("teams_{i}"));
        let c = link.core();
        let same = |a: u32, n: usize| {
            let mut b = vec![0u8; n];
            c.raw_read_range(a, -1, &mut b);
            b == rom[(a & 0x01FF_FFFF) as usize..][..n]
        };
        println!(
            "R {i}: rom emblem original {} palette original {}",
            same(0x080F_8984, 128),
            same(0x0810_18E4, 32)
        );
        println!(
            "R {i}: host {} applied {} colour1 {} ident {:?}",
            tango_gamesupport_aw2::army_skin::host_of(c, 0),
            tango_gamesupport_aw2::army_skin::applied_on(c, 1).map_or(0, |i| i + 1),
            c.raw_read_8(0x0201_7C50 + 0x0D, -1),
            (0..4)
                .map(|k| c.raw_read_8(tango_gamesupport_aw2::army_skin::STATE + 4 + k, -1))
                .collect::<Vec<_>>()
        );
    }
    let host = tango_gamesupport_aw2::army_skin::host_of(link.core(), 0);
    expect(host != 0, "army 1 has the skin after four presses of R");
    println!("host colour {host}");
    // army 2: its R skips the skin's seat's colour and the skin
    press(&mut link, RIGHT);
    press(&mut link, RIGHT);
    for i in 0..6 {
        press(&mut link, R);
        wait(&mut link, 20);
        let colours = link.core().raw_read_8(0x0201_7C50 + 0x0D + 1, -1);
        println!("army 2 colour after R {}: {colours}", i + 1);
        let now = tango_gamesupport_aw2::army_skin::host_of(link.core(), 0);
        let c1 = link.core().raw_read_8(0x0201_7C50 + 0x0D, -1);
        expect(
            colours != 0 && colours != c1 && now == c1,
            "army 2 never has army 1's colour, and the skin sits on army 1's colour",
        );
    }
    shot(&mut link, "teams_army2");
    if cpu {
        // army 1 is a computer army (the record's controller byte: 1 human, 2 computer)
        link.core_mut().raw_write_8(0x0201_7C50 + 0x09, -1, 2);
        wait(&mut link, 10);
        shot(&mut link, "teams_cpu");
    }
    // A through the CO choices, the rules and the loading until the battle is on
    for _ in 0..60 {
        if tango_gamesupport_aw2::pvp::in_battle(link.core()) {
            break;
        }
        for k in 0..14 {
            link.tick([HostInput::keys(if k < 8 { A } else { 0 }), HostInput::keys(0)]);
            let c = link.core();
            let h = tango_gamesupport_aw2::army_skin::host_of(c, 0);
            if h == 0 && std::env::var_os("SKIN_TRACE").is_some() {
                println!(
                    "trace: host 0 at k {k}, loop {:08x} versus {} teams {}",
                    c.raw_read_32(0x0300_0000, -1),
                    tango_gamesupport_aw2::pvp::in_versus(c),
                    tango_gamesupport_aw2::pvp::on_teams_screen(c)
                );
            }
        }
        wait(&mut link, 60);
        println!(
            "flow: host {} seen {} teams {}",
            tango_gamesupport_aw2::army_skin::host_of(link.core(), 0),
            link.core()
                .raw_read_8(tango_gamesupport_aw2::army_skin::STATE + 0xF, -1),
            tango_gamesupport_aw2::pvp::on_teams_screen(link.core())
        );
    }
    wait(&mut link, 600);
    shot(&mut link, "battle");
    let (mode, colours) = tango_gamesupport_aw2::pvp::army_state(link.core());
    println!(
        "mode {mode}, battle army colours {colours:?}, host {}",
        tango_gamesupport_aw2::army_skin::host_of(link.core(), 0)
    );
    let host_now = tango_gamesupport_aw2::army_skin::host_of(link.core(), 0);
    expect(
        host_now != 0 && colours[0] == host_now,
        "army 1's colour in the battle is the colour the skin sits on",
    );
    for t in 0..(if cpu { 6 } else { 1 }) {
        wait(&mut link, 500);
        shot(&mut link, &format!("later_{t}"));
    }
    if failed {
        std::process::exit(1);
    }
}
