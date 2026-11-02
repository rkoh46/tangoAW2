"""A custom map's volcano hazard (crate::hazard, crate::campaign_model::VolcanoDef) seen from the battle: units of every army are parked on the cells
the next eruption takes, the day is ended, and each must have lost the configured HP (never below 1). The cells are the Rust's own
(`VolcanoDef::cells_on`), kept here in Python: a function of the day alone."""

DAY = 0x03004080
CELLS = 0x0203F708


def ring(x0, y0, x1, y1):
    v = [(x, y0) for x in range(x0, x1 + 1)]
    v += [(x1, y) for y in range(y0 + 1, y1 + 1)]
    v += [(x, y1) for x in range(x1 - 1, x0 - 1, -1)]
    v += [(x0, y) for y in range(y1 - 1, y0, -1)]
    return v


def cells_on(cells, per, day):
    n = len(cells)
    if per == 0 or per >= n:
        return list(cells)
    start = (day * 5) % n
    return [cells[(start + k * n // per) % n] for k in range(per)]


def ram_cells(e):
    out = []
    for k in range(12):
        x = e.u16(CELLS + 4 * k)
        if x == 0xFFFF:
            break
        out.append((x, e.u16(CELLS + 4 * k + 2)))
    return out


TRACE = {}
SEEN = set()          # the cursor's cells while the eruption's show plays (the show's camera visits each cell it drops a boulder on)


def _next_day(e, g, d, day, watch=()):
    d.end_turn()
    for _ in range(900):
        if e.u16(DAY) == day and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
        if watch:
            g._units_base = None
            h = {u["id"]: u["hp"] for u in g.units()}
            row = tuple(h.get(i) for i in watch)
            if not TRACE.get("last") == row:
                TRACE.setdefault("rows", []).append((e.u16(DAY), g.current_army(), row))
                TRACE["last"] = row
    for _ in range(60):
        if not d.scripts_running():
            break
        e.press("A", 4)
        e.wait(10)
    for _ in range(70):               # (the eruption's show, then the damage lands)
        e.wait(10)
        if watch:
            g._units_base = None
            h = {u["id"]: u["hp"] for u in g.units()}
            row = tuple(h.get(i) for i in watch)
            if not TRACE.get("last") == row:
                TRACE.setdefault("rows", []).append((e.u16(DAY), g.current_army(), row))
                TRACE["last"] = row
    d.wait_control()
    # (the eruption's impacts land one after the other, some seconds after the day starts: wait until the hit points hold still for ten seconds)
    still, last = 0, None
    for _ in range(400):
        e.wait(10)
        g._units_base = None
        if watch and last is not None and still < 60:
            SEEN.add(tuple(g.cursor()))
        h = {u["id"]: u["hp"] for u in g.units()}
        row = tuple(h.get(i) for i in watch) if watch else tuple(sorted(h.items()))
        if row != last:
            if watch:
                TRACE.setdefault("rows", []).append(("after control", e.u16(DAY), g.current_army(), row))
            last, still = row, 0
        else:
            still += 1
        if still >= 60:
            break
    g._units_base = g._players_base = None


def check(ctx, e, g, d, cells, first, interval, damage_hp, per, label, max_days=12):
    """Every army present has a unit hit on an erupting cell; each loses `damage_hp` HP (internal 10 a point), never below 1."""
    g._units_base = g._players_base = None
    want_hp = max(1, 100 - 10 * damage_hp)
    armies = sorted({u["army"] for u in g.units()})
    pending = list(armies)
    verified = set()
    for _ in range(max_days):
        if not pending:
            break
        day = e.u16(DAY)
        nxt = day + 1
        erupts = nxt >= first and interval > 0 and (nxt - first) % interval == 0
        if not erupts:
            _next_day(e, g, d, nxt)
            continue
        spots = cells_on(cells, per, nxt)
        placed = []
        mine = set()
        for c in spots:
            if not pending:
                break
            a = pending[0]
            cand = [u for u in g.units(army=a) if u["id"] not in mine and not (u["flags"] & 0x08)]
            if not cand:
                ctx.log(f"{label}: army {a} has no unit to park")
                pending.pop(0)
                continue
            u = cand[0]
            occ = g.unit_at(*c)
            if occ is not None and occ["id"] != u["id"]:
                d.remove_unit(occ)
            addr = g.unit_addr(u["id"])
            e.w8(addr, 4)                                         # a Tank: it stays put without fuel and is hit like any ground unit
            e.w16(addr + 4, (e.u16(addr + 4) & 0xFF80) | 100)
            e.w8(addr + 6, 0)
            d.place_unit(u, *c)
            mine.add(u["id"])
            placed.append((u["id"], a, c))
            pending.pop(0)
        g._units_base = g._players_base = None
        TRACE.clear()
        SEEN.clear()
        _next_day(e, g, d, nxt, [i for i, _, _ in placed])
        ctx.log(f"{label}: hp trace (day, army to move, hp of {[i for i, _, _ in placed]}): {TRACE.get('rows')}")
        landed = ram_cells(e)
        ctx.log(f"{label}: the show's cursor visited {sorted(SEEN)}")
        now = {u["id"]: u["hp"] for u in g.units()}
        ctx.log(f"{label}: day {nxt}: cells {spots}, the game's list {landed}, parked {placed} -> {[(i, now.get(i)) for i, _, _ in placed]}")
        for uid, a, c in placed:
            got = now.get(uid)
            # (at most the eruption's HP: a computer army's guns beside the cell can take more; never below 1)
            ctx.check(got is not None and 1 <= got <= want_hp, f"{label}: day {nxt}: army {a}'s unit on the erupting cell {c} lost at least {damage_hp} HP (100 -> {got}, want <= {want_hp})")
            verified.add(a)
    ctx.check(set(armies) == verified, f"{label}: units of every army ({armies}) were hit on erupting cells (verified {sorted(verified)})")
