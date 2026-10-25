//! Compares the input streams of room recordings: prints, for each replay file given, its player count, the ticks it holds and
//! a hash of every 600 ticks' rows, and (with two or more files) the first tick at which two of them differ. Peers of one
//! match must record the same settled rows whoever hosted them (a test aid for host migration).
//!
//! Usage: replay_inputs <file.tangoreplay>...

fn main() {
    let files: Vec<String> = std::env::args().skip(1).collect();
    let mut all = Vec::new();
    for f in &files {
        let r = tango_replay::Replay::decode(std::fs::File::open(f).expect("open")).expect("decode");
        let mut h: u64 = 0xcbf29ce484222325;
        let mut marks = Vec::new();
        for (t, row) in r.inputs.iter().enumerate() {
            for p in row {
                for b in [p.keys as u64, p.extra[0] as u64, p.extra[1] as u64, p.extra[2] as u64] {
                    h = (h ^ b).wrapping_mul(0x100000001b3);
                }
            }
            if (t + 1) % 600 == 0 {
                marks.push(format!("{:08x}", h as u32));
            }
        }
        println!(
            "{f}: players {} local {} ticks {} complete {} marks {}",
            r.players(),
            r.local_player_index,
            r.inputs.len(),
            r.is_complete,
            marks.join(",")
        );
        all.push(r);
    }
    for i in 1..all.len() {
        let (a, b) = (&all[0], &all[i]);
        let n = a.inputs.len().min(b.inputs.len());
        let first = (0..n).find(|&t| {
            let (x, y) = (&a.inputs[t], &b.inputs[t]);
            (0..2).any(|p| x[p].keys != y[p].keys || x[p].extra != y[p].extra)
        });
        match first {
            None => println!("{} vs {}: the first {n} ticks are identical", files[0], files[i]),
            Some(t) => println!(
                "{} vs {}: DIFFER at tick {t} (of {n}): {:?} / {:?}",
                files[0],
                files[i],
                a.inputs[t].map(|p| (p.keys, p.extra)),
                b.inputs[t].map(|p| (p.keys, p.extra))
            ),
        }
    }
}
