//! Lists the BH Campaign's (or, with `es` or `bh2`, the Emerald Sun or BH2 Campaign's) scenes with their songs: `aw2_campaign_scenes <aw2.gba>` prints one tab-separated line per scene:
//! mission, kind (prologue / intro / victory / after / trigger / front2), boxes, track label, AW2 song id (Dual Strike songs resolved with TANGOAW2_DS_ROM).
//! Used by `aw2dev campaign scenes` (docs/dev/campaign-scenes.md).
use tango_gamesupport_aw2::custom_campaign::{Action, Scene};

fn song(rom: &[u8], s: &Scene) -> (String, String) {
    match s.song {
        Some(t) => (t.label(), t.resolve_rom(rom).to_string()),
        None => ("-".into(), "-".into()),
    }
}

fn row(rom: &[u8], m: &str, kind: &str, s: &Scene) {
    if s.is_empty() {
        return;
    }
    let mut parts = vec![s];
    parts.extend(s.more.iter());
    for p in parts {
        let (l, id) = song(rom, p);
        println!("{m}\t{kind}\t{}\t{l}\t{id}", p.lines.len());
    }
}

fn main() {
    let rom = std::fs::read(
        std::env::args()
            .nth(1)
            .expect("usage: aw2_campaign_scenes <aw2.gba> [bh|es|bh2]"),
    )
    .unwrap();
    let def = match std::env::args().nth(2).as_deref() {
        Some("es") => tango_gamesupport_aw2::es_campaign::def(),
        Some("bh2") => tango_gamesupport_aw2::bh2_campaign::def(),
        _ => tango_gamesupport_aw2::bh_campaign::def(),
    };
    println!(
        "prologue\tprologue\t{}\t{}\t{}",
        def.prologue.len(),
        def.prologue_song.map_or("-".into(), |t| t.label()),
        def.prologue_song
            .map_or("-".into(), |t| t.resolve_rom(&rom).to_string())
    );
    for m in &def.missions {
        row(&rom, m.key, "intro", &m.intro);
        row(&rom, m.key, "victory", &m.victory);
        row(&rom, m.key, "after", &m.after);
        row(&rom, m.key, "front2", &m.front2_victory);
        for t in m.triggers.iter().chain(m.front2_triggers.iter()) {
            for a in &t.then {
                if let Action::Scene(s) = a {
                    row(&rom, m.key, "trigger", s);
                }
            }
        }
    }
}
