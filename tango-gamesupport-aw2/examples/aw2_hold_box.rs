//! The reconnect countdown's message box (`hold_box`) over the room page of 2..5 players, with 10 and 12 letter names
//! and 57 / 38 / 9 seconds, as BMPs (<out-dir>/NAME.bmp), with the text audit.
//!
//! Usage: [TANGOAW2_DS_ROM=<nds>] aw2_hold_box <rom> <out-dir>
//!
//! Prints `PROBLEM <case>: ...` for each string that leaves its box, and `done: N problems`.

use tango_gamesupport_aw2::online::{audit, mailbox, Status, HOST, LINK_DIRECT, LINK_RELAY, YOU};
use tango_match::{HostInput, Link};

const STATE: u32 = tango_gamesupport_aw2::online::STATE;

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

struct Ctx {
    link: tango_backend_mgba::SharedLink,
    out: std::path::PathBuf,
    problems: usize,
}

fn w(core: &mut mgba::core::Core) -> impl FnMut(u32, &[u8]) + '_ {
    move |a, b| core.raw_write_range(a, -1, b)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
    std::fs::create_dir_all(&out).unwrap();
    if std::env::var_os("TANGOAW2_DS_ROM").is_some() {
        tango_gamesupport_aw2::ds_pack::pack();
    }
    mailbox::boot_to_lobby();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    let rtc = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000);
    let link = tango_backend_mgba::SharedLink::boot(&rom, Some(&save), Some(rtc), &tango_gamesupport_aw2::pvp::AW2E, None, None).expect("boot");
    let mut c = Ctx { link, out, problems: 0 };
    let mut t = 0;
    while t < 3000 && tango_gamesupport_aw2::online_menu::cursor(c.link.core()).is_none() {
        c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
        t += 1;
    }
    for _ in 0..120 {
        c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
    }
    let names5 = ["WWWWWWWWWWWW", "Gamertag10", "Nell", "WWWWWWWWWW", "Fifth"];
    let kinds = [(0, 0), (LINK_RELAY, 255), (LINK_DIRECT, 23), (LINK_RELAY, 140), (LINK_DIRECT, 7)];
    let cases = [("WWWWWWWWWWWW", 57u32), ("WWWWWWWWWW", 38), ("Guest", 9), ("Gamertag10", 57), ("iiiiiiiiiiii", 38), ("MMMMMMMMMMMM", 9)];
    for n in 2..=5usize {
        for (k, (name, secs)) in cases.iter().enumerate() {
            let core = c.link.core_mut();
            core.raw_write_range(STATE, -1, &[0u8; 0x100]);
            core.raw_write_8(STATE, -1, 2);
            for (i, nm) in names5[..n].iter().enumerate() {
                let flags = if i == 0 { HOST | YOU } else { 0 };
                mailbox::write_player(&mut w(core), i, Some((nm, false, flags)));
                if i != 0 {
                    mailbox::write_link(&mut w(core), i, kinds[i].0, kinds[i].1);
                }
            }
            mailbox::write_room(&mut w(core), "WWWWWW");
            mailbox::write_status(&mut w(core), Status::Waiting, "");
            for _ in 0..3 {
                c.link.tick([HostInput::keys(0), HostInput::keys(0)]);
            }
            tango_gamesupport::hold::set(Some((name.to_string(), *secs)));
            audit::start();
            let frame = c.link.solo_side().frame().expect("frame");
            let bad = audit::finish();
            tango_gamesupport::hold::set(None);
            let name_ = format!("hold_{n}p_{k}");
            write_bmp(&c.out.join(format!("{name_}.bmp")), &frame);
            for b in &bad {
                println!("PROBLEM {name_}: {b}");
            }
            c.problems += bad.len();
        }
    }
    println!("done: {} problems", c.problems);
}
