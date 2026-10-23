//! Does a save + load of the console between two ticks leave the machine exactly where it was? (It does not: docs/dev/architecture-online.md 6.1.)
//!
//! A waiting seat's picture used to be made on the match's own console (snapshot, tick, picture, load the snapshot back) while the mover's console
//! never loaded anything. If a load is not exact, the two peers' consoles drift apart in timing (the PC the last IRQ interrupted, the dead words of the
//! stack) although every game variable agrees. This runs three single-core links over the same keys: one never loaded (`plain`), a second never loaded
//! (`twin`, whose differences from `plain` would be noise: there are none), and `trip`, saved and loaded every `period`-th tick. It prints
//! - what a load changes in the console's own registers (`save, load, save` differs; the io block before and after the load),
//! - the first tick at which the digests of `plain` and `trip` differ, with the registers and RAM bytes that differ.
//!
//! Usage: `aw2dev net roundtrip [--ticks N] [--period P]`, or `roundtrip_probe <aw2.gba> [ticks=6000] [period=1]`.
//! Environment: `NOIDLE=1` switches mgba's idle-loop optimisation off on every machine (still differs: it is not the idle loop);
//! `RAW=<tick>` prints every 4-byte word of mgba's C-side GBA and ARMCore structs that differs between `plain` and `trip` after that tick (heap
//! pointers differ by nature: they show as differing high halves of the machine's own addresses).
use mgba_rollback::{Link, LinkOptions, Peripheral, SideOptions};

fn boot(rom: &[u8]) -> Link {
    let mut l = Link::with_options(LinkOptions {
        sides: vec![SideOptions {
            rom: rom.to_vec(),
            save: None,
        }],
        rtc: Some(std::time::UNIX_EPOCH + std::time::Duration::from_secs(1_700_000_000)),
        peripheral: Peripheral::Cable,
    })
    .expect("boot");
    l.set_frameskip(0, i32::MAX);
    if std::env::var_os("NOIDLE").is_some() {
        unsafe {
            (*l.core_mut(0).gba_mut().as_raw()).idleOptimization = -1;
        }
    }
    l
}

/// A mash of START, A, B and the directions that walks AW2's intro and menus; no keys while it boots.
fn keys(t: u32) -> u32 {
    let x = t / 6;
    let h = x.wrapping_mul(2654435761) >> 13;
    if t < 400 || x % 3 != 0 {
        0
    } else {
        [1u32, 8, 1, 2, 1, 16, 1, 32, 1, 64, 1, 128][(h % 12) as usize]
    }
}

fn io_block(l: &mut Link) -> Vec<u16> {
    unsafe { (*l.core_mut(0).gba_mut().as_raw()).memory.io.to_vec() }
}

fn words(name: &str, x: *const u8, y: *const u8, n: usize) {
    for off in (0..n).step_by(4) {
        let (u, v) = unsafe { (*(x.add(off) as *const u32), *(y.add(off) as *const u32)) };
        if u != v {
            println!("  {name}+{off:#x}: {u:#x} vs {v:#x}");
        }
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let rom = std::fs::read(a.get(1).expect("usage: roundtrip_probe <aw2.gba> [ticks] [period]")).expect("rom");
    let ticks: u32 = a.get(2).and_then(|v| v.parse().ok()).unwrap_or(6000);
    let period: u32 = a.get(3).and_then(|v| v.parse().ok()).unwrap_or(1);
    let raw_at: Option<u32> = std::env::var("RAW").ok().and_then(|v| v.parse().ok());
    let (mut plain, mut twin, mut trip) = (boot(&rom), boot(&rom), boot(&rom));
    let mut last_io: Vec<String> = Vec::new();
    let mut last_again: Vec<usize> = Vec::new();
    for t in 0..ticks {
        let k = keys(t);
        plain.tick(&[k]);
        twin.tick(&[k]);
        trip.tick(&[k]);
        if t % period == 0 {
            let s = trip.save().expect("save");
            let before = io_block(&mut trip);
            trip.load(&s).expect("load");
            let after = io_block(&mut trip);
            let d: Vec<String> = (0..512)
                .filter(|&i| before[i] != after[i])
                .map(|i| format!("io[{:#x}] {:#x}->{:#x}", i * 2, before[i], after[i]))
                .collect();
            if d != last_io {
                println!(
                    "tick {t}: a load changes the io registers: {}",
                    if d.is_empty() { "nothing".into() } else { d.join(", ") }
                );
                last_io = d;
            }
            // (load, then save again: bytes of the header that change are fields the savestate cannot hold)
            let again = trip.save().expect("save");
            let (x, y) = (
                &s.core_state(0).as_slice()[..0x1000],
                &again.core_state(0).as_slice()[..0x1000],
            );
            let d: Vec<usize> = (0..x.len()).filter(|&i| x[i] != y[i]).collect();
            if d != last_again {
                println!(
                    "tick {t}: save, load, save changes header bytes: {}",
                    d.iter()
                        .map(|&i| format!("{i:#x}: {:#x}->{:#x}", x[i], y[i]))
                        .collect::<Vec<_>>()
                        .join(", ")
                );
                last_again = d;
            }
        }
        if raw_at == Some(t) {
            unsafe {
                let (gp, gt) = (
                    plain.core_mut(0).gba_mut().as_raw(),
                    trip.core_mut(0).gba_mut().as_raw(),
                );
                println!("tick {t}: differing words of mgba's GBA and ARMCore structs");
                words(
                    "GBA",
                    gp as *const u8,
                    gt as *const u8,
                    std::mem::size_of::<mgba_sys::GBA>(),
                );
                words(
                    "cpu",
                    (*gp).cpu as *const u8,
                    (*gt).cpu as *const u8,
                    std::mem::size_of::<mgba_sys::ARMCore>(),
                );
            }
        }
        let (sp, st, sw) = (
            plain.save().expect("save"),
            trip.save().expect("save"),
            twin.save().expect("save"),
        );
        assert_eq!(
            sp.digest(),
            sw.digest(),
            "two machines that never loaded differ at tick {t}: the probe is not deterministic"
        );
        if sp.digest() != st.digest() {
            let (p, q) = (sp.core_state(0), st.core_state(0));
            println!(
                "tick {t} (frame {}): the round-tripped console differs from the one that never loaded",
                plain.core(0).frame_counter()
            );
            println!(
                "  plain registers: {}  cpsr {:#x}",
                (0..16)
                    .map(|r| format!("r{r}={:x}", p.gpr(r)))
                    .collect::<Vec<_>>()
                    .join(" "),
                p.cpsr()
            );
            for r in 0..16 {
                if p.gpr(r) != q.gpr(r) {
                    println!("  r{r}: plain {:#x}, round-trip {:#x}", p.gpr(r), q.gpr(r));
                }
            }
            for (name, x, y) in [("EWRAM", p.wram(), q.wram()), ("IWRAM", p.iwram(), q.iwram())] {
                let d = (0..x.len()).filter(|&i| x[i] != y[i]).count();
                if d > 0 {
                    println!("  {name}: {d} bytes differ");
                }
            }
            return;
        }
    }
    println!("no difference in {ticks} ticks (period {period})");
}
