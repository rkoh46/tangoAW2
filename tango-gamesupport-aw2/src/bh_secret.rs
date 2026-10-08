//! The secret mission. Its missions are `MissionDef`s (docs/AW2.md "BH Campaign": adding
//! a mission); this file is the act's alone, so builders can work on acts
//! in parallel. A mission names what it needs by key (`Needs::All(vec!["bh01"])`),
//! not by index.

// (the builders' imports: each act uses what it needs)
#![allow(unused_imports)]

use crate::bh_campaign::{region, roster};
use crate::custom_campaign::{co, colour, unit, *};

/// The secret mission (opens with `Needs::Bonds(..)`: every hidden bond earned).
pub fn missions() -> Vec<MissionDef> {
    Vec::new()
}
