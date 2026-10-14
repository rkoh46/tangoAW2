//! Dual Strike's Design Room maps in AW2's (with the Dual Strike pack): its
//! random map generator and its preset map, behind AW2's own Fill > Random.
//!
//! AW2's editor menu has Fill > Random ("Let the computer design a map?",
//! Yes / No): `GenerateRandomMap` (`sub_08003B8C`) clears the units, makes
//! the map 30x20 and fills it by the keys held: L and R a built-in map
//! (`sub_08004724`), L or R alone one of its two generators, neither a
//! random pick of the two; then it refits the coasts and recounts the
//! properties and HQs. (Its key state reads nothing while the
//! confirmation's dialogue runs, so in practice it is always the random
//! pick.) Dual Strike's New map does the same with its own generator
//! (`Ov006_GenerateRandomMap`, the decompilation's
//! `src/game/ov006/ov006_generate_random_map.c` and callees) and, with L
//! and R held, its own preset (`Ov006_LoadPresetMap`). With the pack on,
//! Random runs Dual Strike's generator ([`generate`]), or lays Dual
//! Strike's preset ([`preset`], read from the pack's overlay 6) when L and
//! R are held as Yes is picked (read from the console's key register).
//! Traps at the branches write the map and continue at AW2's recount
//! (`0x08003C2E`), so the confirmation, the redraw and the HQ and property
//! bookkeeping are the game's own. (The map the editor opens with comes
//! from the same function and stays AW2's.)
//!
//! The generator is Dual Strike's step for step, with its random numbers
//! (`Rng_Next`, `Rng_NextMixed`, `Rng_Range`) in the same order, on a map of
//! Dual Strike cell codes: plain, then sea grown from 2..8 seeds, mountains
//! from 8..12, the two HQs at least 15 apart with 2..4 bases and 1..3
//! airports each, cities (owned, neutral near each HQ, neutral between
//! them) and Com Towers, roads between the HQs and the cities with bridges
//! over water, woods, shoals along the coast and reefs out at sea. Where
//! Dual Strike reads outside the map (a road at the map's edge, a base
//! tried off the map) or can search for ever (`Ov006_PickLinkTiles`), the
//! map's edge is checked first and the searches are bounded. It is seeded
//! from emulated RAM only (AW2's random number and frame counter), so a
//! replay or a save state draws the same map.
//!
//! The terrain is then drawn with AW2's tiles as `five/map.py` lays
//! tangoAW2's Versus maps ([`paint`]): sea edges from the editor's table
//! (`0x08485DC4`), mountains with their peaks, shaded plains, roads and
//! woods, bridges, shoals, pipes, properties by owner (army 1 Orange Star,
//! 2 Blue Moon) and the Com Tower ([`crate::com_tower`]).

use mgba::core::Core;

pub const W: usize = 30;
pub const H: usize = 20;

// --- Dual Strike's random numbers ---------------------------------------------

/// `Rng_Next`, `Rng_NextMixed` and `Rng_Range` (src/game/main/rng/).
pub struct Rng(pub u32);

impl Rng {
    pub fn next(&mut self) -> u32 {
        let f = self.0.wrapping_mul(4).wrapping_add(2);
        self.0 = f.wrapping_mul(f.wrapping_add(1)) >> 2;
        self.0
    }

    fn next_mixed(&mut self) -> u32 {
        let v = self.next();
        let v = v.wrapping_add((v & 2) >> 1);
        self.0 = v;
        v
    }

    /// min..=max. (The value is below 2^30 + 1, so Dual Strike's signed
    /// remainder is the plain one.)
    fn range(&mut self, min: i32, max: i32) -> i32 {
        min + (self.next_mixed() as i32) % (max - min + 1)
    }
}

// --- The generator, on Dual Strike's cell codes --------------------------------

/// Dual Strike's map cell codes (`Ov006_SetMapCell`).
const SHOAL: u16 = 0;
const PLAIN: u16 = 1;
const RIVER_BRIDGE: u16 = 19;
const BRIDGE_DOWN: u16 = 21;
const BRIDGE_ACROSS: u16 = 22;
const MOUNTAIN: u16 = 32;
const SEA: u16 = 42;
const ROAD: u16 = 97;
const WOOD: u16 = 135;
const REEF: u16 = 360;
const COM_TOWER: u16 = 441;
/// Properties: 448 + 5 * owner + kind (HQ, base, city, airport, port).
const PROPERTY: u16 = 448;
const CITY: u16 = PROPERTY + 2;
const fn hq(owner: u16) -> u16 {
    PROPERTY + 5 * owner
}
const fn base(owner: u16) -> u16 {
    PROPERTY + 5 * owner + 1
}
const fn city(owner: u16) -> u16 {
    PROPERTY + 5 * owner + 2
}
const fn airport(owner: u16) -> u16 {
    PROPERTY + 5 * owner + 3
}

/// `Ov006_gGenMarks`.
const CLEAR: i8 = 0;
const DONE: i8 = 1;
const SEED: i8 = 2;
/// A tile on a planned road (`Ov006_MarkLinkPath`).
const PLAN_ROAD: i8 = 2;

/// Bounds for the searches Dual Strike leaves open (they end long before
/// these on any map it makes).
const SEARCH: u32 = 100_000;

type Point = (i32, i32);

fn distance(a: Point, b: Point) -> i32 {
    (a.0 - b.0).abs() + (a.1 - b.1).abs()
}

struct Gen {
    cells: [[u16; W]; H],
    marks: [[i8; W]; H],
    rng: Rng,
}

impl Gen {
    fn on_map(x: i32, y: i32) -> bool {
        x >= 0 && y >= 0 && x < W as i32 && y < H as i32
    }

    fn cell(&self, x: i32, y: i32) -> u16 {
        self.cells[y as usize][x as usize]
    }

    fn set(&mut self, x: i32, y: i32, c: u16) {
        self.cells[y as usize][x as usize] = c;
    }

    fn mark(&self, x: i32, y: i32) -> i8 {
        if Self::on_map(x, y) {
            self.marks[y as usize][x as usize]
        } else {
            CLEAR
        }
    }

    fn set_mark(&mut self, x: i32, y: i32, m: i8) {
        self.marks[y as usize][x as usize] = m;
    }

    /// `Ov006_MarkMapBorder`.
    fn mark_border(&mut self) {
        for y in 0..H {
            for x in 0..W {
                self.marks[y][x] = (x == 0 || y == 0 || x == W - 1 || y == H - 1) as i8;
            }
        }
    }

    /// `Ov006_FindRandomCell`: 101 tries.
    fn find_random_cell(&mut self, cell: u16) -> Option<Point> {
        self.find(|g, x, y| g.cell(x, y) == cell)
    }

    /// `Ov006_FindRandomClearCell`: the 3x3 around it all water too.
    fn find_random_clear_cell(&mut self, cell: u16) -> Option<Point> {
        self.find(|g, x, y| g.cell(x, y) == cell && (-1..=1).all(|dy| (-1..=1).all(|dx| g.water(x + dx, y + dy))))
    }

    /// Random cells until one passes, 101 tries (the shape of
    /// `Ov006_FindRandomCell`, `Ov006_PickRandomCellNear`, ...).
    fn find(&mut self, ok: impl Fn(&Gen, i32, i32) -> bool) -> Option<Point> {
        for _ in 0..=100 {
            let x = self.rng.range(0, W as i32 - 1);
            let y = self.rng.range(0, H as i32 - 1);
            if ok(self, x, y) {
                return Some((x, y));
            }
        }
        None
    }

    /// `func_ov006_0235b784`: off the map, sea, shoal, reef or a river's
    /// bridge.
    fn water(&self, x: i32, y: i32) -> bool {
        !Self::on_map(x, y) || matches!(self.cell(x, y), SEA | SHOAL | REEF | RIVER_BRIDGE)
    }

    /// `Ov006_SettleSeedTiles`.
    fn settle(&mut self) -> bool {
        let mut found = false;
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                if self.mark(x, y) == SEED {
                    for (nx, ny) in [(x - 1, y), (x, y - 1), (x + 1, y), (x, y + 1)] {
                        if Self::on_map(nx, ny) {
                            self.set_mark(nx, ny, CLEAR);
                        }
                    }
                    self.set_mark(x, y, DONE);
                    found = true;
                }
            }
        }
        found
    }

    /// `Ov006_CountCellNeighbors`: off the map counts.
    fn count_neighbours(&self, x: i32, y: i32, cell: u16) -> i32 {
        if self.mark(x, y) != CLEAR {
            return 0;
        }
        [(x - 1, y), (x, y - 1), (x + 1, y), (x, y + 1)]
            .iter()
            .filter(|&&(nx, ny)| !Self::on_map(nx, ny) || self.cell(nx, ny) == cell)
            .count() as i32
    }

    /// `Ov006_RollCellChance`.
    fn roll(&mut self, count: i32, cell: u16) -> bool {
        match cell {
            MOUNTAIN if count != 0 => {
                let roll = self.rng.range(1, 8);
                roll <= [2, 3, 3, 5].get(count as usize - 1).copied().unwrap_or(count)
            }
            SEA if count != 0 => {
                let roll = self.rng.range(1, 6);
                roll <= [2, 4, 5, 6].get(count as usize - 1).copied().unwrap_or(count)
            }
            SHOAL => {
                let roll = self.rng.range(1, 4);
                roll <= [1, 3, 4].get(count as usize).copied().unwrap_or(count)
            }
            _ => false,
        }
    }

    /// `Ov006_GrowCells`.
    fn grow(&mut self, cell: u16, from: u16) {
        loop {
            for y in 0..H as i32 {
                for x in 0..W as i32 {
                    if self.mark(x, y) == CLEAR && self.cell(x, y) == from {
                        let n = self.count_neighbours(x, y, cell);
                        if self.roll(n, cell) {
                            self.set(x, y, cell);
                            self.set_mark(x, y, SEED);
                        } else {
                            self.set_mark(x, y, DONE);
                        }
                    }
                }
            }
            if !self.settle() {
                break;
            }
        }
    }

    /// `Ov006_ScatterSea`: 2..8 plus-shaped patches, grown over the plain.
    fn scatter_sea(&mut self) {
        self.mark_border();
        let count = self.rng.range(2, 8);
        for _ in 0..count {
            let Some((x, y)) = self.find_random_cell(PLAIN) else {
                break;
            };
            for (nx, ny) in [(x, y), (x - 1, y), (x, y - 1), (x + 1, y), (x, y + 1)] {
                if Self::on_map(nx, ny) {
                    self.set(nx, ny, SEA);
                    self.set_mark(nx, ny, SEED);
                }
            }
        }
        self.settle();
        self.grow(SEA, PLAIN);
    }

    /// `Ov006_ScatterMountains`: 8..12 seeds, grown over the plain.
    fn scatter_mountains(&mut self) {
        self.mark_border();
        let count = self.rng.range(8, 12);
        for _ in 0..count {
            let Some((x, y)) = self.find_random_cell(PLAIN) else {
                break;
            };
            self.set(x, y, MOUNTAIN);
            self.set_mark(x, y, SEED);
        }
        self.settle();
        self.grow(MOUNTAIN, PLAIN);
    }

    /// `Ov006_PickRandomCellBlock`: a cell off the map's edge whose 3x3 is
    /// all `cell`, at least 15 from `avoid`.
    fn pick_block(&mut self, cell: u16, avoid: Option<Point>) -> Option<Point> {
        let mut tries = 0;
        for _ in 0..SEARCH {
            let x = self.rng.range(0, W as i32 - 1);
            let y = self.rng.range(0, H as i32 - 1);
            if x == 0 || x == W as i32 - 1 || y == 0 || y == H as i32 - 1 {
                continue;
            }
            if avoid.is_some_and(|a| distance(a, (x, y)) < 15) {
                continue;
            }
            if (-1..=1).all(|dy| (-1..=1).all(|dx| self.cell(x + dx, y + dy) == cell)) {
                return Some((x, y));
            }
            if tries >= 100 {
                return None;
            }
            tries += 1;
        }
        None
    }

    /// `Ov006_PlaceHq`: the HQ, then bases and airports on plain within 2
    /// (a miss draws again; the edge is checked before the cell).
    fn place_hq(&mut self, (x, y): Point, owner: u16, bases: i32, airports: i32) -> Point {
        self.set(x, y, hq(owner));
        for (n, cell) in [(bases, base(owner)), (airports, airport(owner))] {
            let mut placed = 0;
            for _ in 0..SEARCH {
                if placed >= n {
                    break;
                }
                let bx = self.rng.range(x - 2, x + 2);
                let by = self.rng.range(y - 2, y + 2);
                if Self::on_map(bx, by) && self.cell(bx, by) == PLAIN {
                    self.set(bx, by, cell);
                    placed += 1;
                }
            }
        }
        (x, y)
    }

    /// `Ov006_PlaceRandomHq`: a 5x5 on the map with nothing owned, made
    /// plain. The second HQ also keeps 15 from the first here (Dual
    /// Strike's can land next to it, about one map in fifty).
    fn place_random_hq(&mut self, owner: u16, bases: i32, airports: i32, avoid: Option<Point>) -> Point {
        let owned = |c: u16| (hq(1)..=city(2) + 2).contains(&c);
        let corners = [
            (2, 2),
            (W as i32 - 3, H as i32 - 3),
            (W as i32 - 3, 2),
            (2, H as i32 - 3),
        ];
        let mut at = corners
            .into_iter()
            .max_by_key(|&c| avoid.map_or(0, |a| distance(a, c)))
            .unwrap();
        for _ in 0..SEARCH {
            let x = self.rng.range(0, W as i32 - 1);
            let y = self.rng.range(0, H as i32 - 1);
            let fits = (y - 2..=y + 2).all(|j| (x - 2..=x + 2).all(|i| Self::on_map(i, j) && !owned(self.cell(i, j))));
            if fits && avoid.is_none_or(|a| distance(a, (x, y)) >= 15) {
                at = (x, y);
                break;
            }
        }
        for j in at.1 - 2..=at.1 + 2 {
            for i in at.0 - 2..=at.0 + 2 {
                self.set(i, j, PLAIN);
            }
        }
        self.place_hq(at, owner, bases, airports)
    }

    /// `Ov006_PlaceHqs`.
    fn place_hqs(&mut self) -> (Point, Point) {
        let bases = self.rng.range(2, 4);
        let airports = self.rng.range(1, 3);
        let hq1 = match self.pick_block(PLAIN, None) {
            Some(p) => self.place_hq(p, 1, bases, airports),
            None => self.place_random_hq(1, bases, airports, None),
        };
        let hq2 = match self.pick_block(PLAIN, Some(hq1)) {
            Some(p) => self.place_hq(p, 2, bases, airports),
            None => self.place_random_hq(2, bases, airports, Some(hq1)),
        };
        (hq1, hq2)
    }

    /// `Ov006_AddCities`: returns the last neutral city near each HQ and
    /// the last city or tower between them.
    fn add_cities(&mut self, hq1: Point, hq2: Point) -> (Option<Point>, Option<Point>, Option<Point>) {
        let (mut city1, mut city2, mut middle) = (None, None, None);
        for step in 0..4 {
            let count = match step {
                0 => self.rng.range(0, 5),
                1 => self.rng.range(3, 5),
                2 => self.rng.range(3, 7),
                _ => self.rng.range(0, 5),
            };
            for _ in 0..count {
                let near =
                    |p: Point, r: i32| move |g: &Gen, x: i32, y: i32| g.cell(x, y) == PLAIN && distance(p, (x, y)) <= r;
                let between = |r: i32| {
                    move |g: &Gen, x: i32, y: i32| {
                        g.cell(x, y) == PLAIN && (distance(hq1, (x, y)) - distance(hq2, (x, y))).abs() <= r
                    }
                };
                match step {
                    0 | 1 => {
                        let (cells, range) = if step == 0 {
                            ([city(1), city(2)], 10)
                        } else {
                            ([CITY, CITY], 8)
                        };
                        let Some(p) = self.find(near(hq1, range)) else { break };
                        self.set(p.0, p.1, cells[0]);
                        if step == 1 {
                            city1 = Some(p);
                        }
                        let Some(p) = self.find(near(hq2, range)) else { break };
                        self.set(p.0, p.1, cells[1]);
                        if step == 1 {
                            city2 = Some(p);
                        }
                    }
                    _ => {
                        let (cell, range) = if step == 2 { (CITY, 10) } else { (COM_TOWER, 5) };
                        let Some(p) = self.find(between(range)) else { break };
                        self.set(p.0, p.1, cell);
                        middle = Some(p);
                    }
                }
            }
        }
        (city1, city2, middle)
    }

    /// `Ov006_RandomMapCoord`: low..=high, on the map.
    fn map_coord(&mut self, low: i32, high: i32, vertical: bool) -> i32 {
        let limit = if vertical { H } else { W } as i32;
        for _ in 0..SEARCH {
            let v = self.rng.range(low, high);
            if (0..limit).contains(&v) {
                return v;
            }
        }
        low.clamp(0, limit - 1)
    }

    /// `Ov006_PickLinkTiles`: a cell near each point, on the side facing
    /// the other, not sea, and whether the path's middle leg runs across
    /// (rows) or down. Dual Strike searches without end; here a search that
    /// finds nothing leaves the link out.
    fn pick_link(&mut self, (x1, y1): Point, (x2, y2): Point, range: i32) -> Option<(Point, Point, bool)> {
        let (dx, dy) = ((x1 - x2).abs(), (y1 - y2).abs());
        // Each cell's x and y ranges, in Dual Strike's drawing order (x first,
        // or y first when the points are close on x).
        let toward = |a: i32, b: i32, own: bool| -> (i32, i32) {
            // `own`: the range of the first point (toward the second), else
            // of the second (toward the first).
            let p = if own { a } else { b };
            if (a > b) == own {
                (p - range, p)
            } else {
                (p, p + range)
            }
        };
        let (vertical, free_x, free_y) = if (dx >= range || dy >= range) && dx < range {
            (true, true, false)
        } else if (dx >= range || dy >= range) && dy < range {
            (false, false, true)
        } else {
            (self.rng.range(0, 1) == 1, false, false)
        };
        let pick = |g: &mut Gen, own: bool| -> Option<Point> {
            let (cx, cy) = if own { (x1, y1) } else { (x2, y2) };
            for _ in 0..1000 {
                let (x, y) = if free_y {
                    let y = g.map_coord(cy - range, cy + range, true);
                    let (lo, hi) = toward(x1, x2, own);
                    (g.map_coord(lo, hi, false), y)
                } else {
                    let x = if free_x {
                        g.map_coord(cx - range, cx + range, false)
                    } else {
                        let (lo, hi) = toward(x1, x2, own);
                        g.map_coord(lo, hi, false)
                    };
                    let (lo, hi) = toward(y1, y2, own);
                    (x, g.map_coord(lo, hi, true))
                };
                if g.cell(x, y) != SEA && distance((x, y), (cx, cy)) <= range {
                    return Some((x, y));
                }
            }
            None
        };
        let from = pick(self, true)?;
        let to = pick(self, false)?;
        Some((from, to, vertical))
    }

    /// `Ov006_MarkLinkPath`: three legs, the middle one at a random column
    /// (or row, `vertical`) between the two.
    fn mark_link(&mut self, (x1, y1): Point, (x2, y2): Point, vertical: bool) {
        let span = |a: i32, b: i32| a.min(b)..=a.max(b);
        if !vertical {
            let mid = self.rng.range(x1.min(x2), x1.max(x2));
            for i in span(mid, x1) {
                self.set_mark(i, y1, PLAN_ROAD);
            }
            for i in span(mid, x2) {
                self.set_mark(i, y2, PLAN_ROAD);
            }
            for i in span(y1, y2) {
                self.set_mark(mid, i, PLAN_ROAD);
            }
        } else {
            let mid = self.rng.range(y1.min(y2), y1.max(y2));
            for i in span(mid, y1) {
                self.set_mark(x1, i, PLAN_ROAD);
            }
            for i in span(mid, y2) {
                self.set_mark(x2, i, PLAN_ROAD);
            }
            for i in span(x1, x2) {
                self.set_mark(i, mid, PLAN_ROAD);
            }
        }
    }

    /// `Ov006_TryPlaceBridge`: a planned road cell with water (not planned
    /// road) on both sides becomes a bridge.
    fn try_bridge(&mut self, x: i32, y: i32) -> bool {
        let open = |g: &Gen, x: i32, y: i32| g.water(x, y) && g.mark(x, y) != PLAN_ROAD;
        if open(self, x - 1, y) && open(self, x + 1, y) {
            self.set(x, y, BRIDGE_ACROSS);
            return true;
        }
        if open(self, x, y - 1) && open(self, x, y + 1) {
            self.set(x, y, BRIDGE_DOWN);
            return true;
        }
        false
    }

    /// `Ov006_AddRoads` and `Ov006_PlaceRoadsAtMarks`: properties stay.
    fn add_roads(&mut self, hq1: Point, hq2: Point, city1: Option<Point>, city2: Option<Point>, middle: Option<Point>) {
        self.mark_border();
        if let Some((a, b, v)) = self.pick_link(hq1, hq2, 4) {
            self.mark_link(a, b, v);
        }
        if let (Some(c1), Some(c2), Some(m)) = (city1, city2, middle) {
            for c in [c1, c2] {
                if let Some((a, b, v)) = self.pick_link(c, m, 2) {
                    self.mark_link(a, b, v);
                }
            }
        }
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                let property = matches!(self.cell(x, y), c if c == CITY || (hq(1)..=hq(2) + 4).contains(&c));
                if self.mark(x, y) == PLAN_ROAD && !property && !self.try_bridge(x, y) {
                    self.set(x, y, ROAD);
                }
            }
        }
    }

    /// `Ov006_ScatterWoods`.
    fn scatter_woods(&mut self) {
        let count = self.rng.range(20, 40);
        for _ in 0..count {
            let Some((x, y)) = self.find_random_cell(PLAIN) else {
                return;
            };
            self.set(x, y, WOOD);
        }
    }

    /// `func_ov006_0235b46c`: -1 unless a sea cell has water both beside and
    /// above or below it; with two such sides the shoals around it, with
    /// three the shoals across from water.
    fn shoal_count(&self, x: i32, y: i32) -> i32 {
        let horiz = self.water(x - 1, y) as i32 + self.water(x + 1, y) as i32;
        let vert = self.water(x, y - 1) as i32 + self.water(x, y + 1) as i32;
        if horiz == 0 || vert == 0 {
            return -1;
        }
        let shoal = |x: i32, y: i32| Self::on_map(x, y) && self.cell(x, y) == SHOAL;
        let sides = [
            (x - 1, y, x + 1, y),
            (x + 1, y, x - 1, y),
            (x, y - 1, x, y + 1),
            (x, y + 1, x, y - 1),
        ];
        match horiz + vert {
            2 => sides.iter().filter(|s| shoal(s.0, s.1)).count() as i32,
            3 => sides.iter().filter(|s| shoal(s.0, s.1) && self.water(s.2, s.3)).count() as i32,
            _ => -1,
        }
    }

    /// `Ov006_AddShoals`: by chance, then each sea cell with a count of 2.
    fn add_shoals(&mut self) {
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                if self.cell(x, y) == SEA {
                    let n = self.shoal_count(x, y);
                    if n != -1 && self.roll(n, SHOAL) {
                        self.set(x, y, SHOAL);
                    }
                }
            }
        }
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                if self.cell(x, y) == SEA && self.shoal_count(x, y) == 2 {
                    self.set(x, y, SHOAL);
                }
            }
        }
    }

    /// `Ov006_ScatterReefs`.
    fn scatter_reefs(&mut self) {
        let count = self.rng.range(8, 15);
        for _ in 0..count {
            let Some((x, y)) = self.find_random_clear_cell(SEA) else {
                return;
            };
            self.set(x, y, REEF);
        }
    }
}

/// `Ov006_GenerateRandomMap`, from a seed (Dual Strike's is its random
/// number advanced once plus the frame count).
pub fn generate(seed: u32) -> Vec<Terrain> {
    let mut g = Gen {
        cells: [[PLAIN; W]; H],
        marks: [[CLEAR; W]; H],
        rng: Rng(seed),
    };
    g.scatter_sea();
    g.scatter_mountains();
    let (hq1, hq2) = g.place_hqs();
    let (city1, city2, middle) = g.add_cities(hq1, hq2);
    g.add_roads(hq1, hq2, city1, city2, middle);
    g.scatter_woods();
    g.add_shoals();
    g.scatter_reefs();
    g.cells.iter().flatten().map(|&c| Terrain::from_cell(c)).collect()
}

// --- Terrain, and Dual Strike's preset ----------------------------------------

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Hq,
    Base,
    City,
    Airport,
    Port,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Terrain {
    Sea,
    Reef,
    Shoal,
    Plain,
    Wood,
    Mountain,
    Road,
    Bridge,
    Pipe,
    Tower,
    /// A property and its owner (0 neutral, 1 Orange Star, 2 Blue Moon).
    Property(Kind, u8),
}

const KINDS: [Kind; 5] = [Kind::Hq, Kind::Base, Kind::City, Kind::Airport, Kind::Port];

impl Terrain {
    fn from_cell(c: u16) -> Terrain {
        match c {
            SHOAL => Terrain::Shoal,
            PLAIN => Terrain::Plain,
            RIVER_BRIDGE | BRIDGE_DOWN | BRIDGE_ACROSS => Terrain::Bridge,
            MOUNTAIN => Terrain::Mountain,
            SEA => Terrain::Sea,
            ROAD => Terrain::Road,
            WOOD => Terrain::Wood,
            REEF => Terrain::Reef,
            COM_TOWER => Terrain::Tower,
            c if (PROPERTY..PROPERTY + 15).contains(&c) => {
                Terrain::Property(KINDS[((c - PROPERTY) % 5) as usize], ((c - PROPERTY) / 5) as u8)
            }
            _ => Terrain::Plain,
        }
    }

    /// A Dual Strike tile byte (terrain | owner << 5) as
    /// `Ov006_LoadPresetMap` lays it: the terrain it has no case for stays
    /// sea.
    fn from_ds_byte(b: u8) -> Terrain {
        let owner = b >> 5;
        match (b & 0x1F, owner) {
            (1, 0) => Terrain::Plain,
            (3, 0) => Terrain::Mountain,
            (4, 0) => Terrain::Wood,
            (5, 0) => Terrain::Road,
            (13, _) => Terrain::Shoal,
            (15 | 16, 0) => Terrain::Pipe,
            (19, 0) => Terrain::Reef,
            (6, 0..=2) => Terrain::Property(Kind::City, owner),
            (8 | 14, 1..=2) => Terrain::Property(if b & 0x1F == 8 { Kind::Hq } else { Kind::Base }, owner),
            _ => Terrain::Sea,
        }
    }

    fn tall(self) -> bool {
        matches!(
            self,
            Terrain::Wood | Terrain::Mountain | Terrain::Tower | Terrain::Property(..)
        )
    }
}

/// `Ov006_gPresetMapTiles`: overlay 6 (loaded at 0x02350560), 600 tile
/// bytes, by row.
const OVERLAY: usize = 6;
const OVERLAY_BASE: u32 = 0x0235_0560;
const PRESET_TILES: u32 = 0x0236_D2DC;

/// Dual Strike's preset map, from the pack.
pub fn preset() -> Option<Vec<Terrain>> {
    let bytes = crate::ds_pack::pack()?.overlay_at(OVERLAY, OVERLAY_BASE, PRESET_TILES, W * H)?;
    Some(bytes.iter().map(|&b| Terrain::from_ds_byte(b)).collect())
}

// --- AW2's tiles ----------------------------------------------------------------

/// AW2's tiles, as `five/map.py` lays them (learned from AW2's own maps;
/// see that file for each table's story).
const PLAIN_TILE: u16 = 0x001;
const PLAIN_SHADE: u16 = 0x021;
const SEA_TILE: u16 = 0x02A;
const REEF_TILE: u16 = 0x168;
const WOOD_SHADE: u16 = 0x086;
const WOOD_TILE: u16 = 0x087;
const PEAK: u16 = 0x043;
const PEAK_SHADE: u16 = 0x003;
const BRIDGE_ACROSS_TILE: u16 = 0x14;
const BRIDGE_DOWN_TILE: u16 = 0x36;
/// Mountains by (peak in the cell above, mountain below).
fn mountain_tile(peak_above: bool, below: bool) -> u16 {
    match (peak_above, below) {
        (true, true) => 0x022,
        (true, false) => 0x023,
        (false, true) => 0x002,
        (false, false) => 0x020,
    }
}
/// Roads by link (N E S W, bit 3 N).
const ROAD_TILES: [u16; 16] = [
    0x61, 0x61, 0x40, 0x42, 0x61, 0x61, 0x41, 0xE0, 0x40, 0x62, 0x40, 0xC1, 0x60, 0xC0, 0xE1, 0x100,
];
fn road_shaded(t: u16) -> u16 {
    match t {
        0x61 => 0xA1,
        0x40 => 0x80,
        0x41 => 0x81,
        0x60 => 0xA0,
        t => t,
    }
}
fn pipe_tile(link: u8) -> u16 {
    match link {
        0b0101 => 0x142,
        0b1010 => 0x143,
        0b0110 => 0x140,
        0b0011 => 0x141,
        0b1100 => 0x160,
        0b1001 => 0x161,
        0b0001 => 0x121,
        0b0100 => 0x120,
        0b0010 => 0x102,
        0b1000 => 0x103,
        _ => 0x142,
    }
}
/// Shoals by what lies N E S W: s sea or reef, h shoal, l else.
#[rustfmt::skip]
const SHOALS: &[(&str, u16)] = &[
    ("shlh", 0x10), ("lhsh", 0x50), ("hlhs", 0x2E), ("hshl", 0x32),
    ("shll", 0xF2), ("sllh", 0xF3), ("lhsl", 0x112), ("llsh", 0x113),
    ("llhs", 0xB2), ("hlls", 0xD2), ("lshl", 0xB3), ("hsll", 0xD3),
    ("shls", 0x6D), ("sslh", 0x6E), ("lhss", 0xCD), ("lssh", 0xCE),
    ("slhs", 0xAF), ("sshl", 0xB0), ("hlss", 0xCF), ("hssl", 0xD0),
    ("slls", 0xB6), ("ssll", 0xB7), ("llss", 0xD6), ("lssl", 0xD7),
    ("ssls", 0x8F), ("slss", 0x92), ("sssl", 0x93), ("lsss", 0xEF),
    ("hhll", 0x31), ("hllh", 0x2F), ("llhh", 0x4F), ("lhhl", 0x51),
    ("slll", 0x55), ("lsll", 0x53), ("llsl", 0x75), ("llls", 0x54),
    ("lhhh", 0x50), ("hlhh", 0x2E), ("hhlh", 0x10), ("lhhs", 0xCD),
    ("lshh", 0xCE), ("slhh", 0xAF), ("shhl", 0xB0), ("hlsh", 0xCF),
    ("hhsl", 0xD0), ("hhls", 0x6D), ("hslh", 0x6E), ("lshs", 0xEF),
];
/// Property tiles by kind and owner (0 neutral, 1..4 the armies, 5 Black
/// Hole).
const PROPERTY_TILES: [[u16; 6]; 5] = [
    [0x1C0, 0x1C5, 0x1CA, 0x1CF, 0x1D4, 0x1B4],
    [0x1C1, 0x1C6, 0x1CB, 0x1D0, 0x1D5, 0x1B5],
    [0x1C2, 0x1C7, 0x1CC, 0x1D1, 0x1D6, 0x1B6],
    [0x1C3, 0x1C8, 0x1CD, 0x1D2, 0x1D7, 0x1B7],
    [0x1C4, 0x1C9, 0x1CE, 0x1D3, 0x1D8, 0x1B8],
];

fn shoal_tile(key: [u8; 4]) -> Option<u16> {
    let find = |k: &[u8; 4]| SHOALS.iter().find(|(s, _)| s.as_bytes() == k).map(|&(_, t)| t);
    if let Some(t) = find(&key) {
        return Some(t);
    }
    // A strip of shoal wider than one cell: drawn as the beach it would be
    // with a neighbouring shoal as land, the one opposite the sea first
    // (five/map.py).
    let mut sides: Vec<usize> = (0..4).filter(|&j| key[j] == b'h').collect();
    sides.sort_by_key(|&j| key[(j + 2) % 4] != b's');
    sides.iter().find_map(|&j| {
        let mut alt = key;
        alt[j] = b'l';
        find(&alt)
    })
}

/// The map's AW2 tile ids, row by row. `edge(mask)` is the editor's sea-edge
/// table (land around a sea cell, bit 8 top-left .. bit 0 bottom-right;
/// zero or less: open sea), `tower` the Com Tower's tile.
pub fn paint(t: &[Terrain], edge: &dyn Fn(u16) -> i16, tower: u16) -> Vec<u16> {
    let at = |x: i32, y: i32| {
        if x >= 0 && y >= 0 && x < W as i32 && y < H as i32 {
            t[y as usize * W + x as usize]
        } else {
            Terrain::Sea
        }
    };
    // N E S W; off the map, the cell itself.
    let around = |x: i32, y: i32| {
        [(x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)].map(|(nx, ny)| {
            if nx >= 0 && ny >= 0 && nx < W as i32 && ny < H as i32 {
                at(nx, ny)
            } else {
                at(x, y)
            }
        })
    };
    let water = |c: Terrain| matches!(c, Terrain::Sea | Terrain::Reef | Terrain::Shoal | Terrain::Bridge);
    let sea_tile = |x: i32, y: i32| {
        let mut mask = 0u16;
        for (i, (dx, dy)) in [
            (-1, -1),
            (0, -1),
            (1, -1),
            (-1, 0),
            (0, 0),
            (1, 0),
            (-1, 1),
            (0, 1),
            (1, 1),
        ]
        .iter()
        .enumerate()
        {
            if !water(at(x + dx, y + dy)) {
                mask |= 0x100 >> i;
            }
        }
        match edge(mask) {
            e if e > 0 => e as u16,
            _ => SEA_TILE,
        }
    };
    let mut out = Vec::with_capacity(W * H);
    for y in 0..H as i32 {
        for x in 0..W as i32 {
            let left = at(x - 1, y);
            let tile = match at(x, y) {
                Terrain::Sea => sea_tile(x, y),
                Terrain::Reef => REEF_TILE,
                Terrain::Wood => {
                    if left.tall() || left == Terrain::Pipe {
                        WOOD_SHADE
                    } else {
                        WOOD_TILE
                    }
                }
                Terrain::Mountain => {
                    let peak_above = y > 0 && matches!(at(x, y - 1), Terrain::Mountain | Terrain::Plain);
                    mountain_tile(peak_above, at(x, y + 1) == Terrain::Mountain && y + 1 < H as i32)
                }
                Terrain::Road => {
                    let road = |c: Terrain| matches!(c, Terrain::Road | Terrain::Bridge);
                    let link = (road(at(x, y - 1)) as usize) << 3
                        | (road(at(x + 1, y)) as usize) << 2
                        | (road(at(x, y + 1)) as usize) << 1
                        | road(at(x - 1, y)) as usize;
                    let t = ROAD_TILES[link];
                    if left.tall() {
                        road_shaded(t)
                    } else {
                        t
                    }
                }
                Terrain::Bridge => {
                    let n = around(x, y);
                    let wet = |c: Terrain| matches!(c, Terrain::Sea | Terrain::Reef);
                    if wet(n[0]) || wet(n[2]) {
                        BRIDGE_ACROSS_TILE
                    } else {
                        BRIDGE_DOWN_TILE
                    }
                }
                Terrain::Shoal => {
                    let key = around(x, y).map(|c| match c {
                        Terrain::Sea | Terrain::Reef => b's',
                        Terrain::Shoal => b'h',
                        _ => b'l',
                    });
                    // A shape AW2's maps have no beach for: open water.
                    shoal_tile(key).unwrap_or_else(|| sea_tile(x, y))
                }
                Terrain::Pipe => {
                    let pipe = |x: i32, y: i32| at(x, y) == Terrain::Pipe;
                    let mut link = (pipe(x, y - 1) as u8) << 3
                        | (pipe(x + 1, y) as u8) << 2
                        | (pipe(x, y + 1) as u8) << 1
                        | pipe(x - 1, y) as u8;
                    // A pipe ending at the map's edge runs on off the map.
                    for (bit, out, back) in [
                        (0b1000, y == 0, 0b0010),
                        (0b0100, x == W as i32 - 1, 0b0001),
                        (0b0010, y == H as i32 - 1, 0b1000),
                        (0b0001, x == 0, 0b0100),
                    ] {
                        if out && link == back {
                            link |= bit;
                        }
                    }
                    pipe_tile(link)
                }
                Terrain::Tower => tower,
                Terrain::Property(kind, owner) => PROPERTY_TILES[kind as usize][owner.min(5) as usize],
                Terrain::Plain => {
                    let shaded = left.tall();
                    match (at(x, y + 1) == Terrain::Mountain && y + 1 < H as i32, shaded) {
                        (true, true) => PEAK_SHADE,
                        (true, false) => PEAK,
                        (false, true) => PLAIN_SHADE,
                        (false, false) => PLAIN_TILE,
                    }
                }
            };
            out.push(tile);
        }
    }
    out
}

// --- In the editor ------------------------------------------------------------------

const MAP: u32 = 0x0201_E450;
const TILES: u32 = MAP + 0xA22;
const CLASSES: u32 = MAP + 0x1432;
const ROWS: u32 = MAP + 0x417A;
/// Tile -> class byte (class | owner << 5).
const CLASS_TABLE: u32 = 0x080C_1BC4;
/// The editor's sea-edge table (`five/map.py`'s), s16 per mask.
const SEA_EDGES: u32 = 0x0848_5DC4;
/// AW2's random number and frame counter (`gGameClock`).
const AW2_RNG: u32 = 0x0300_1FD4;
const GAME_CLOCK: u32 = 0x0300_4008;

/// In `GenerateRandomMap`: the branch to AW2's built-in map (L and R held),
/// the branch to its random pick of generators (neither held), and the
/// recount both go on to.
pub const PRESET_BRANCH: u32 = 0x0800_3BDA;
pub const RANDOM_BRANCH: u32 = 0x0800_3C0E;
const RECOUNT: u32 = 0x0800_3C2E;

/// Write `t` into the editor's map (30x20, its row offsets set by
/// `GenerateRandomMap`): tiles and their classes.
fn write_map(core: &mut Core, t: &[Terrain]) {
    let edge = |mask: u16| core.raw_read_16(SEA_EDGES + 2 * mask as u32, -1) as i16;
    let tiles = paint(t, &edge, crate::com_tower::tile_for(0));
    for y in 0..H as u32 {
        let row = core.raw_read_16(ROWS + 2 * y, -1) as u32;
        for x in 0..W as u32 {
            let tile = tiles[(y * W as u32 + x) as usize];
            let class = core.raw_read_8(CLASS_TABLE + tile as u32, -1);
            core.raw_write_16(TILES + 2 * (row + x), -1, tile);
            core.raw_write_8(CLASSES + row + x, -1, class);
        }
    }
}

fn continue_at_recount(core: &mut Core) {
    core.gba_mut().cpu_mut().set_thumb_pc(RECOUNT);
}

/// The buttons as the console has them now (`REG_KEYINPUT`, a bit clear
/// while its button is down). The game's key state reads nothing while
/// the confirmation's dialogue runs, so `GenerateRandomMap` never sees L
/// and R held there; the console's register does.
const KEYINPUT: u32 = 0x0400_0130;
const KEY_L_R: u16 = 0x300;

fn shoulders_held(core: &Core) -> bool {
    core.raw_read_16(KEYINPUT, -1) & KEY_L_R == 0
}

/// `GenerateRandomMap`'s return address as it pushed it (`push {r4, r5, r6,
/// lr}`: the fourth word up the stack) when Fill > Random called it, through
/// `DesignRoomNewMap(-1)` (`bl` at `0x08003C58`). The editor also calls it
/// as it opens (`sub_08000DF8(0)`); that map stays AW2's, so a design
/// started on it is as before.
const FROM_FILL_MENU: u32 = 0x0800_3C5D;

fn from_fill_menu(core: &Core) -> bool {
    let sp = core.gba().cpu().gpr(13) as u32;
    core.raw_read_32(sp + 12, -1) == FROM_FILL_MENU
}

/// Trap at [`RANDOM_BRANCH`]: Dual Strike's generator, seeded as Dual
/// Strike seeds it, from AW2's random number and frame counter; with L
/// and R held, Dual Strike's preset.
fn random_map(core: &mut Core) {
    if !crate::ds_weather::is_on(core) || !crate::design::in_map_editor(core) || !from_fill_menu(core) {
        return;
    }
    let t = match shoulders_held(core).then(preset).flatten() {
        Some(t) => t,
        None => {
            let mut rng = Rng(core.raw_read_32(AW2_RNG, -1));
            generate(rng.next().wrapping_add(core.raw_read_32(GAME_CLOCK, -1)))
        }
    };
    write_map(core, &t);
    continue_at_recount(core);
}

/// Trap at [`PRESET_BRANCH`]: Dual Strike's preset map in place of AW2's.
fn preset_map(core: &mut Core) {
    if !crate::ds_weather::is_on(core) || !crate::design::in_map_editor(core) || !from_fill_menu(core) {
        return;
    }
    let Some(t) = preset() else {
        return;
    };
    write_map(core, &t);
    continue_at_recount(core);
}

pub fn traps() -> Vec<(u32, Box<dyn Fn(&mut Core)>)> {
    vec![
        (RANDOM_BRANCH, Box::new(random_map)),
        (PRESET_BRANCH, Box::new(preset_map)),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hqs(t: &[Terrain]) -> Vec<(u8, Point)> {
        let mut v: Vec<_> = (0..W * H)
            .filter_map(|i| match t[i] {
                Terrain::Property(Kind::Hq, o) => Some((o, ((i % W) as i32, (i / W) as i32))),
                _ => None,
            })
            .collect();
        v.sort();
        v
    }

    #[test]
    fn rng_is_dual_strikes() {
        // s = (4s + 2)(4s + 3) / 4 from 0: 2*3/4 = 1, then 6*7/4 = 10.
        let mut r = Rng(0);
        assert_eq!(r.next(), 1);
        assert_eq!(r.next(), 10);
        let mut r = Rng(12345);
        for _ in 0..1000 {
            let v = r.range(3, 7);
            assert!((3..=7).contains(&v));
        }
    }

    #[test]
    fn a_seed_makes_one_map() {
        for seed in [0, 1, 0xDEAD_BEEF, 77] {
            assert_eq!(generate(seed), generate(seed));
        }
        assert_ne!(generate(1), generate(2));
    }

    #[test]
    fn maps_are_playable() {
        for seed in 0..400u32 {
            let t = generate(seed.wrapping_mul(0x9E37_79B9));
            assert_eq!(t.len(), W * H);
            let h = hqs(&t);
            assert_eq!(
                h.iter().map(|&(o, _)| o).collect::<Vec<_>>(),
                vec![1, 2],
                "seed {seed}: HQs {h:?}"
            );
            assert!(distance(h[0].1, h[1].1) >= 15, "seed {seed}: HQs {h:?}");
            for owner in [1, 2] {
                let bases = t.iter().filter(|&&c| c == Terrain::Property(Kind::Base, owner)).count();
                assert!((2..=4).contains(&bases), "seed {seed}: army {owner} has {bases} bases");
            }
            // Painting never fails, and gives every cell a tile.
            let tiles = paint(&t, &|_| 0, 0x1D9);
            assert!(tiles.iter().all(|&x| x != 0 && x < 0x200));
        }
    }

    #[test]
    fn preset_bytes() {
        assert_eq!(Terrain::from_ds_byte(0x28), Terrain::Property(Kind::Hq, 1));
        assert_eq!(Terrain::from_ds_byte(0x4E), Terrain::Property(Kind::Base, 2));
        assert_eq!(Terrain::from_ds_byte(0x46), Terrain::Property(Kind::City, 2));
        assert_eq!(Terrain::from_ds_byte(0x0F), Terrain::Pipe);
        assert_eq!(Terrain::from_ds_byte(0x0C), Terrain::Sea);
    }
}
