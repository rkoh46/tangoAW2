//! The offline Versus SELECT MAP (tabs and lists): boots single-player, walks to Versus > New and plays a script on the map list.
//!
//! Usage: aw2_offline_tabs <rom> <out-dir> [script]   (script tokens as aw2_mapsel_preview, plus `S` SELECT, `s:NAME` shot, `t` print the tab and the list ids)
use tango_match::{HostInput, Link};

const A: u32 = 1;
const START: u32 = 1 << 3;
const DOWN: u32 = 1 << 7;

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

struct Run {
    link: tango_backend_mgba::SharedLink,
}

impl Run {
    fn wait(&mut self, n: u32) {
        for _ in 0..n {
            self.link.tick([HostInput::keys(0), HostInput::keys(0)]);
        }
    }
    fn press(&mut self, keys: u32) {
        for _ in 0..4 {
            self.link.tick([HostInput::keys(keys), HostInput::keys(0)]);
        }
        self.wait(8);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(&args[1]).expect("rom");
    let out = std::path::PathBuf::from(&args[2]);
    let script = args.get(3).cloned().unwrap_or_else(|| "s:a w S s:b".to_string());
    std::fs::create_dir_all(&out).ok();
    let save = vec![0xffu8; tango_gamesupport_aw2::SAVE_SIZE];
    if std::env::var_os("AW2_DS_PACK").is_some() {
        tango_gamesupport_aw2::ds_pack::pack();
    }
    let shared = if std::env::var_os("AW2_SHARED_ART").is_some() {
        tango_gamesupport_aw2::ds_art::SHARED_ART
    } else {
        0
    };
    let link = tango_backend_mgba::SharedLink::boot(
        &rom,
        Some(&save),
        None,
        &tango_gamesupport_aw2::pvp::AW2E,
        Some((0, shared)),
        None,
    )
    .expect("boot");
    let mut r = Run { link };
    r.wait(700);
    r.press(START);
    r.wait(300);
    r.press(A);
    r.wait(150);
    r.press(DOWN);
    r.wait(60);
    r.press(A); // Versus
    r.wait(150);
    r.press(A); // New
    r.wait(200);
    for tok in script.split_whitespace() {
        if let Some(name) = tok.strip_prefix("s:") {
            r.wait(10);
            write_bmp(&out.join(format!("{name}.bmp")), &r.link.solo_side().frame().unwrap());
            continue;
        }
        for c in tok.chars() {
            match c {
                'D' => r.press(1 << 7),
                'U' => r.press(1 << 6),
                'L' => r.press(1 << 5),
                'R' => r.press(1 << 4),
                'A' => r.press(1),
                'B' => r.press(2),
                'S' => r.press(1 << 2),
                'X' => r.press((1 << 8) | (1 << 9)),
                'l' => r.press(1 << 9),
                'r' => r.press(1 << 8),
                'w' => r.wait(120),
                't' => {
                    let core = r.link.core();
                    println!("{}", tango_gamesupport_aw2::online_maps::probe(r.link.core()));
                }
                'c' => {
                    // The check: every tab of the player-count lists, walked with R; each audited map is on exactly one.
                    let mut seen: std::collections::BTreeMap<u8, Vec<u16>> = Default::default();
                    let mut tabs = Vec::new();
                    for _ in 0..12 {
                        let (tab, ids) = tango_gamesupport_aw2::online_maps::list_rows(r.link.core());
                        if tabs.contains(&tab) {
                            break;
                        }
                        println!("tab {tab}: {} maps", ids.len());
                        tabs.push(tab);
                        for id in ids {
                            seen.entry(id).or_default().push(tab);
                        }
                        r.press(1 << 4);
                        r.wait(30);
                    }
                    let want = tango_gamesupport_aw2::online_maps::audit_ids(r.link.core());
                    let missing: Vec<u8> = want.iter().copied().filter(|i| !seen.contains_key(i)).collect();
                    let twice: Vec<_> = seen.iter().filter(|(_, t)| t.len() > 1).collect();
                    let extra: Vec<u8> = seen.keys().copied().filter(|i| !want.contains(i)).collect();
                    for row in tango_gamesupport_aw2::online_maps::audit(r.link.core()) {
                        let tab = seen.get(&row.id).and_then(|t| t.first()).copied().unwrap_or(0);
                        let expect = 2 + 2 * (row.armies as u16 - 2) + row.predeployed as u16;
                        if tab != expect {
                            println!(
                                "DIFF {:02x} {} armies {} pre {} (bases {} air {} ports {} placed {}) on tab {}",
                                row.id,
                                row.name,
                                row.armies,
                                row.predeployed,
                                row.bases,
                                row.airports,
                                row.ports,
                                row.placed,
                                tab
                            );
                        }
                    }
                    println!(
                        "check: {} audited, {} listed, missing {:?}, twice {:?}, not audited {:?}",
                        want.len(),
                        seen.len(),
                        missing,
                        twice,
                        extra
                    );
                }
                'F' => {
                    // A DOWN press, then every frame of it saved (f<n>.bmp).
                    for i in 0..30u32 {
                        r.link
                            .tick([HostInput::keys(if i < 3 { 1 << 7 } else { 0 }), HostInput::keys(0)]);
                        write_bmp(&out.join(format!("f{i:02}.bmp")), &r.link.solo_side().frame().unwrap());
                    }
                }
                'G' => {
                    // A DOWN press and its first 12 frames saved as g<n>_<i>.bmp (n counts the G presses): every scroll step of a long list
                    // (`aw2dev gfx` catalogue screen maplist_scroll reads the names on each frame)
                    static N: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
                    let n = N.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    for i in 0..12u32 {
                        r.link
                            .tick([HostInput::keys(if i < 3 { 1 << 7 } else { 0 }), HostInput::keys(0)]);
                        write_bmp(
                            &out.join(format!("g{n:02}_{i:02}.bmp")),
                            &r.link.solo_side().frame().unwrap(),
                        );
                    }
                    r.wait(8);
                }
                'v' => {
                    let core = r.link.core();
                    let io = |a: u32| core.raw_read_16(0x0400_0000 + a, -1);
                    println!(
                        "dispcnt {:04x} bgcnt {:04x} {:04x} {:04x} {:04x} hofs/vofs {:?}",
                        io(0),
                        io(8),
                        io(0xA),
                        io(0xC),
                        io(0xE),
                        (0..8).map(|k| io(0x10 + 2 * k)).collect::<Vec<_>>()
                    );
                }
                'V' => {
                    let core = r.link.core();
                    let mut v = vec![0u8; 0x18000];
                    core.raw_read_range(0x0600_0000, -1, &mut v);
                    std::fs::write(out.join("vram.bin"), v).unwrap();
                    // (and the palette, OAM and I/O registers: `aw2dev gfx explain` decodes them)
                    for (name, at, len) in [
                        ("pal", 0x0500_0000u32, 0x400usize),
                        ("oam", 0x0700_0000, 0x400),
                        ("io", 0x0400_0000, 0x60),
                    ] {
                        let mut b = vec![0u8; len];
                        core.raw_read_range(at, -1, &mut b);
                        std::fs::write(out.join(format!("{name}.bin")), b).unwrap();
                    }
                }
                _ => {}
            }
        }
    }
}
