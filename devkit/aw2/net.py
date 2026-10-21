"""aw2dev net: tools for developing and debugging the ONLINE side (netplay, rooms, rejoin, desyncs).

  net sim      N local peers with simulated network conditions and scripted kills / freezes / rejoins (local signalling by default)
  net matrix   a scenario across a grid (players x fog x route x impairment) -> pass/fail table
  net desync   a diverged run: first differing frame, differing 4 KB blocks, RAM diff, names from docs/dev/ram-map.md, inputs around it
  net trace    one merged timeline of every peer (inputs, acts, hashes, link events, log lines)
  net relays   polite health report of the public endpoints (signalling, STUN, TURN info, Nostr)
  net soak     hours of random play across peers; logs every desync, stall or crash

Politeness: sim / matrix / soak use a LOCAL signalling mock (aw2.signal_mock) and block every public endpoint through
TANGOAW2_BLOCK_ENDPOINTS, so they never touch the real matchmaking server, STUN or Nostr relays. `--public` opts back in (one run,
a handful of connections) and is required for relay-only (TURN) tests, whose credentials only the real server hands out.
Not possible without root (dnctl/pfctl) and therefore not offered: bandwidth caps, NAT-type emulation. Latency, jitter, loss and
reordering come from TANGOAW2_NET_IMPAIR (tango-net/src/impair.rs): jitter makes the in-match channel reorder.
"""
import json, os, random, re, shutil, socket, struct, sys, time
from pathlib import Path
from . import cfg, check, endpoints, live, scenarios, util, wsmini
from .runlib import Run

LEVELS = {"none": "0,0,0", "mild": "30,10,1", "bad": "80,40,5", "awful": "160,80,10"}
RESULT_SCENARIOS = ("yield", "hq3", "hq3k", "hq3p", "g2k", "g4k")


def parse_event(s):
    """'30:stop:1:10' (seconds) or 't900:kill:2' (tick): AT:ACTION:SEAT[:ARG]; actions kill stop cont relaunch."""
    p = s.split(":")
    at, act, seat = p[0], p[1], int(p[2])
    e = {"action": act, "seat": seat}
    if at.startswith("t"):
        e["at_tick"] = int(at[1:])
    else:
        e["at_s"] = float(at)
    if len(p) > 3:
        e["arg"] = float(p[3])
    return e


def impair_for(n, level=None, latency=None, jitter=None, loss=None, per_seat=None):
    base = None
    if level:
        base = LEVELS[level]
    if latency is not None or jitter is not None or loss is not None:
        base = f"{latency or 0},{jitter or 0},{loss or 0}"
    out = {}
    if base and base != "0,0,0":
        out = {k: base for k in range(n)}
    for x in per_seat or []:
        k, v = x.split("=")
        out[int(k)] = v
    return out


def sim_spec(a):
    n = a.players
    spec = live.make_spec(a.scenario, a.fog, n, a.rounds, a.tag or f"net_{a.scenario}", a.hz, a.max_s, None, None, None, {})
    spec.events = [parse_event(e) for e in (a.event or [])]
    spec.impair = impair_for(spec.n, getattr(a, "level", None), a.latency, a.jitter, a.loss, a.impair)
    if a.reorder and spec.impair:
        spec.impair = {k: (lambda p: f"{p[0]},{max(int(p[1]), int(p[0]))},{p[2]}")(v.split(",")) for k, v in spec.impair.items()}
    spec.local_signal = not a.public
    if a.relay:
        if not a.public:
            util.die("--relay needs the real server's TURN credentials: add --public (one polite run), or test relays with `net relays --turn`")
        spec.extra_env["TANGOAW2_FORCE_RELAY"] = "1"
    if a.dump_frame:
        spec.extra_env["TANGOAW2_DUMP_FRAME"] = str(a.dump_frame)
        os.environ["DUMPF"] = str(a.dump_frame)
    spec.extra_env["TANGOAW2_HASH_PARTS"] = "1"
    return spec


def result_check(run):
    """results correct: a yield/HQ scenario must end with `over` on every seat that is still there."""
    meta = run.meta
    if meta.get("scenario") not in RESULT_SCENARIOS:
        return {"pass": None, "detail": "no result expected by this scenario"}
    killed = set()
    try:
        killed = set(json.loads((run.dir / "summary.json").read_text()).get("killed", []))
    except Exception:
        pass
    seen = {}
    for s in run.seats:
        if s in killed:
            continue
        st = run.states(s)
        seen[s] = bool(st) and any(r.get("over") for r in st[-30:])
    ok = bool(seen) and all(seen.values())
    return {"pass": ok, "over_seen": seen, "detail": "result screen reached on every live seat" if ok else "a seat never saw the result"}


def judge(run, res, with_leak=True):
    """The matrix/soak verdict: no stall, hashes equal, no leak, result."""
    out = {}
    out["stall"] = {"pass": bool(res.get("ok")), "detail": "scripts ran to the end" if res.get("ok") else f"gave up {res.get('gave_up')} / ended {res.get('ended')}"}
    killed = res.get("killed") or []
    live_seats = [s for s in run.seats if s not in killed] or run.seats
    out["hash"] = check.c_hash(run, seats=live_seats)
    if with_leak and run.n >= 2 and run.meta.get("flow") == "scen":
        out["leak"] = check.c_leak(run)
    out["result"] = result_check(run)
    ok = all(v["pass"] is not False for v in out.values())
    return ok, out


def cmd_sim(a):
    spec = sim_spec(a)
    res = live.run(spec)
    run = Run(res["run"])
    ok, out = judge(run, res)
    for k, v in out.items():
        print(f"  [{ {True: 'PASS', False: 'FAIL', None: 'n/a '}[v['pass']] }] {k}: {v['detail']}")
    (run.dir / "net_verdict.json").write_text(json.dumps(out, indent=1, default=str))
    util.say(("PASS " if ok else "FAIL ") + run.dir.name + ("  -> aw2dev net desync " + run.dir.name if not out["hash"]["pass"] else ""))
    return 0 if ok else 1


# ---- matrix ----
def cmd_matrix(a):
    players = [int(x) for x in a.players.split(",")]
    fogs = a.fog.split(",")
    routes = a.route.split(",")
    levels = a.levels.split(",")
    if "relay" in routes and not a.public:
        util.die("route 'relay' needs --public (the real server's TURN); polite default is direct only")
    rows = []
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = cfg.work("matrix")
    out.mkdir(parents=True, exist_ok=True)
    cells = [(n, f, r, lv) for n in players for f in fogs for r in routes for lv in levels]
    util.say(f"{len(cells)} cells x ~3 min each; local signalling{'' if not a.public else ' (PUBLIC)'}; one live run at a time")
    for n, f, r, lv in cells:
        name = a.scenario if n == 2 else "lobby"
        if a.scenario != "moveview" and n != scenarios.seats_of(a.scenario) and a.scenario in scenarios.SCEN:
            name = "lobby"
        spec = live.make_spec(name, f, n, a.rounds, f"mx_{n}p_{lv}_{r}", a.hz, a.max_s)
        spec.impair = impair_for(n, lv)
        spec.local_signal = not a.public
        spec.extra_env["TANGOAW2_HASH_PARTS"] = "1"
        if r == "relay":
            spec.extra_env["TANGOAW2_FORCE_RELAY"] = "1"
        try:
            res = live.run(spec, quiet=True)
            run = Run(res["run"])
            ok, v = judge(run, res)
        except SystemExit:
            raise
        except Exception as e:
            ok, v, res = False, {"stall": {"pass": False, "detail": repr(e)}}, {}
        rows.append((n, f, r, lv, name, v, ok, res.get("run")))
        cell = " ".join(f"{k}={'ok' if x['pass'] else ('--' if x['pass'] is None else 'FAIL')}" for k, x in v.items())
        util.say(f"{n}P fog={f} {r} {lv}: {'PASS' if ok else 'FAIL'}  {cell}")
        if ok and not a.keep and res.get("run"):
            for p in Path(res["run"]).glob("*.png"):
                p.unlink()
    cols = ["stall", "hash", "leak", "result"]
    lines = ["| players | fog | route | impair | flow | " + " | ".join(cols) + " | verdict | run |", "|" + "---|" * (6 + len(cols) + 1)]
    for n, f, r, lv, name, v, ok, rd in rows:
        c = [("ok" if v.get(k, {}).get("pass") else ("FAIL" if v.get(k, {}).get("pass") is False else "-")) for k in cols]
        lines.append(f"| {n} | {f} | {r} | {lv} ({LEVELS[lv]}) | {name} | " + " | ".join(c) + f" | {'PASS' if ok else 'FAIL'} | {Path(rd).name if rd else ''} |")
    table = "\n".join(lines)
    (out / f"matrix_{stamp}.md").write_text(table + "\n")
    print(table)
    bad = sum(1 for r in rows if not r[6])
    print(f"matrix done bad={bad} of {len(rows)} (table: {out / f'matrix_{stamp}.md'})")
    return 1 if bad else 0


# ---- desync ----
def ram_names():
    names = []
    p = cfg.REPO / "docs" / "dev" / "ram-map.md"
    if p.exists():
        for l in p.read_text().splitlines():
            if not l.startswith("|"):
                continue
            cells = [c.strip().strip("`") for c in l.strip("|").split("|")]
            m = re.match(r"0x0*([0-9A-Fa-f]{7,8})(?:\s*[-.]+\s*0x0*([0-9A-Fa-f]{7,8}))?", cells[0])
            if not m:
                continue
            start = int(m.group(1), 16)
            if m.group(2):
                end = int(m.group(2), 16)
            else:
                sz = re.match(r"\d+", cells[1]) if len(cells) > 1 else None
                end = start + (int(sz.group()) if sz else 1) - 1
            names.append((start, end, " | ".join(cells[1:3])[:80]))
    return names


def name_for(addr, names):
    hits = [n for n in names if n[0] <= addr <= n[1]]
    return min(hits, key=lambda n: n[1] - n[0])[2] if hits else "(unnamed: add it to docs/dev/ram-map.md)"


def block_addr(i):
    return (0x03000000 + 0x1000 * i) if i < 8 else (0x02000000 + 0x1000 * (i - 8))


def cmd_desync(a):
    run = Run(a.run if a.run != "latest" else Run.latest())
    seats = [int(x) for x in a.seats.split(",")] if a.seats else run.seats
    H = {s: {} for s in seats}
    for s in seats:
        for d in run.hashes(s):
            H[s][d["frame"]] = d
    common = sorted(set.intersection(*[set(h) for h in H.values()]))
    if not common:
        util.die("no common hash frames (run with TANGOAW2_HASH_PARTS=1; `net sim` sets it)")
    equal_seen = False
    first = None
    for f in common:
        same = len({H[s][f]["h"] for s in seats}) == 1
        equal_seen = equal_seen or same
        if equal_seen and not same:
            first = f
            break
    if first is None:
        diffs = [f for f in common if len({H[s][f]["h"] for s in seats}) > 1]
        if diffs and not equal_seen:
            print(f"hashes never agreed in {len(common)} common frames (menu-phase hashes differ by design; did the battle start?)")
        else:
            print(f"NO DESYNC: {len(common)} common frames, all equal after the first agreement")
        return 0 if equal_seen else 1
    idx = common.index(first)
    print(f"first diverged frame: {first} (previous equal frame {common[idx - 1] if idx else None}; seats {seats})")
    names = ram_names()
    base = seats[0]
    pb = H[base][first].get("parts", "")
    for s in seats[1:]:
        ps = H[s][first].get("parts", "")
        if not pb or not ps:
            print("  no per-block parts (TANGOAW2_HASH_PARTS=1 needed)")
            continue
        diff = [i for i in range(len(pb) // 4) if pb[4 * i:4 * i + 4] != ps[4 * i:4 * i + 4]]
        print(f"  seat {s} vs {base}: {len(diff)} differing 4 KB block(s):")
        for i in diff:
            ba = block_addr(i)
            inside = sorted({n[2] for n in names if n[0] <= ba + 0xfff and n[1] >= ba})[:6]
            print(f"    block {i:2} {ba:#010x}-{ba + 0xfff:#010x}  known here: " + ("; ".join(inside) if inside else "(nothing in docs/dev/ram-map.md)"))
    # RAM diff when dumps exist for that frame
    for s in seats[1:]:
        for part, region in (("i", 0x03000000), ("e", 0x02000000)):
            fa, fb = run.dir / f"ram_s{base}_{first}_{part}.bin", run.dir / f"ram_s{s}_{first}_{part}.bin"
            if fa.exists() and fb.exists():
                A, B = fa.read_bytes(), fb.read_bytes()
                bad = [i for i in range(min(len(A), len(B))) if A[i] != B[i]]
                rs = []
                for i in bad:
                    if rs and i - rs[-1][1] <= 16:
                        rs[-1][1] = i
                    else:
                        rs.append([i, i])
                print(f"  RAM {part} seat {s} vs {base}: {len(bad)} bytes in {len(rs)} range(s)")
                for x, y in rs[:40]:
                    print(f"    {region + x:#010x}-{region + y:#010x}  {name_for(region + x, names)}")
    if not any(run.dir.glob(f"ram_s*_{first}_*.bin")):
        print(f"  no RAM dump for frame {first}: re-run the same story with `aw2dev net sim ... --dump-frame {first}` (the dump needs the frame known in advance)")
    # inputs around the first differing frame (tick of that hash line)
    tick = H[base][first]["tick"]
    print(f"inputs (non-zero joypad words) within {a.window} ticks of tick {tick}:")
    for s in seats:
        ks = [r for r in run.state_lines(s) if r.get("k") == "keys" and abs(r["tick"] - H[s][first]["tick"]) <= a.window]
        print(f"  seat {s}: " + (", ".join(f"t{r['tick']}={r['word']:#x}" for r in ks[-40:]) or "(none)"))
    for s in seats:
        lg = run.dir / f"tango_s{s}.log"
        if lg.exists():
            hits = [l.strip()[:200] for l in lg.read_text(errors="ignore").splitlines() if re.search(r"rollback|desync|input-drop|mismatch", l, re.I)]
            if hits:
                print(f"  seat {s} log ({len(hits)} lines, last 5):")
                for l in hits[-5:]:
                    print("    " + l)
    return 1


# ---- trace ----
LOG_RE = re.compile(r"^\[(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)Z (\w+)\s+([\w:]+)\] (.*)")
LOG_KEYS = re.compile(r"rollback|desync|input-drop|link|pvp|reconnect|dropp|disconnect|migrat|silen|host|rejoin|unranked|peer connection|resume|yield|eliminat|room", re.I)


def cmd_trace(a):
    import calendar
    run = Run(a.run if a.run != "latest" else Run.latest())
    ev = []
    for s in run.seats:
        for r in run.state_lines(s):
            k = r.get("k")
            if k == "keys" and a.keys:
                ev.append((r["ms"], s, r["tick"], "input", f"word={r['word']:#x}"))
            elif k == "act":
                ev.append((r["ms"], s, r["tick"], "act", f"{r.get('what')} actor={r.get('actor')} {r.get('from', '')}->{r.get('to', '')}"))
            elif k == "hash":
                ev.append((r["ms"], s, r["tick"], "hash", f"frame={r['frame']} h={r['h'][:8]}"))
            elif k == "state" and a.state:
                ev.append((r["ms"], s, r["tick"], "state", f"army={r.get('army')} mover={r.get('mover')} over={r.get('over')} ended={r.get('ended')}"))
        lg = run.dir / f"tango_s{s}.log"
        if lg.exists():
            for l in lg.read_text(errors="ignore").splitlines():
                m = LOG_RE.match(l)
                if m and (LOG_KEYS.search(m.group(9)) or LOG_KEYS.search(m.group(8))) and "libdatachannel" not in m.group(8) and not re.search(r"consoleprocs|rom scan|loading selection", m.group(9)):
                    y, mo, d, h, mi, se = map(int, m.groups()[:6])
                    ev.append((calendar.timegm((y, mo, d, h, mi, se)) * 1000, s, None, "log", f"{m.group(7)} {m.group(8).split('::')[-1]}: {m.group(9)[:160]}"))
    ev.sort(key=lambda e: (e[0], e[1]))
    if not ev:
        util.die("nothing to trace in " + str(run.dir))
    t0 = ev[0][0]
    # a hash line anchors each seat's tick; log lines (1 s resolution) borrow the tick of the nearest state event before them
    last_tick = {}
    lines = []
    for ms, s, tick, kind, text in ev:
        if tick is not None:
            last_tick[s] = tick
        t = tick if tick is not None else last_tick.get(s)
        if a.from_tick is not None and (t is None or t < a.from_tick):
            continue
        if a.to_tick is not None and (t is not None and t > a.to_tick):
            continue
        if a.kinds and kind not in a.kinds.split(","):
            continue
        lines.append(f"{(ms - t0) / 1000:9.3f}s s{s} t{'' if t is None else t:<6} {kind:5} {text}")
    out = run.dir / "trace.txt"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:a.head]))
    util.say(f"{len(lines)} events (printed {min(len(lines), a.head)}); full timeline: {out}")
    return 0


# ---- relays ----
def _udp_stun(host, port, timeout=2.0):
    msg = struct.pack(">HHI", 0x0001, 0, 0x2112A442) + os.urandom(12)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t = time.time()
    try:
        s.sendto(msg, (host, port))
        d, _ = s.recvfrom(2048)
        return int((time.time() - t) * 1000) if d[:2] == b"\x01\x01" else None
    except Exception:
        return None
    finally:
        s.close()


def cmd_relays(a):
    e = endpoints.load()
    state_p = cfg.path("paths", "lock_dir") / "relay_probe.json"
    try:
        state = json.loads(state_p.read_text())
    except Exception:
        state = {}
    now = time.time()
    fresh = e["CHECK_FRESH_SECS"] or 300

    def polite(key):
        s = state.get(key, {})
        if not a.force and now - s.get("t", 0) < fresh:
            return f"skipped (probed {int(now - s['t'])} s ago; fresh for {fresh} s)"
        if not a.force and s.get("fails", 0) and now < s.get("until", 0):
            return f"skipped (backing off {int(s['until'] - now)} s after {s['fails']} failure(s))"
        return None

    def note(key, ok):
        s = state.setdefault(key, {})
        s["t"] = now
        if ok:
            s["fails"] = 0
        else:
            s["fails"] = s.get("fails", 0) + 1
            s["until"] = now + min(e["BACKOFF_CAP_SECS"] or 600, (e["BACKOFF_FIRST_SECS"] or 5) * 2 ** (s["fails"] - 1))

    print("== what the app itself has learned (relay_health.txt in each test profile)")
    for p in sorted(cfg.work("profiles").glob("*/config/relay_health.txt")) if cfg.work("profiles").is_dir() else []:
        print(f"-- {p.parent.parent.name}\n" + "\n".join("   " + l for l in p.read_text().splitlines()[:15]))
    rows = []
    # signalling: one websocket request WITHOUT a session id: a healthy server answers HTTP 400 + Abort(MISSING_SESSION_ID); nothing is paired
    for u in e["signaling"]:
        sk = polite(u)
        if sk:
            rows.append(("signalling", u, sk))
            continue
        t = time.time()
        try:
            sock, status, body = wsmini.connect(u + "/", timeout=e["SIGNALING_TIMEOUT_SECS"] or 5)
            if sock:
                sock.close()
            ok = ("400" in status and body[:2] == b"\x08\x03") or " 101 " in status + " "
            rows.append(("signalling", u, f"{'OK' if ok else 'ODD'} {status} in {int((time.time() - t) * 1000)} ms"))
            note(u, ok)
        except Exception as ex:
            rows.append(("signalling", u, f"FAIL {ex!r}"))
            note(u, False)
    # TURN: only the Hello of one signalling session lists the ICE servers; read it once, show hosts only (never the credentials)
    if a.turn:
        u = e["signaling"][0]
        try:
            sock, status, body = wsmini.connect(u + "/?session_id=aw2dev-turn-probe-" + os.urandom(4).hex(), timeout=5)
            if sock:
                op, hello = wsmini.read_frame(sock)
                sock.close()
                urls = sorted(set(re.findall(rb"(?:stun|turns?):[\w.\-]+(?::\d+)?", hello)))
                rows.append(("turn/ice", u, "Hello lists: " + ", ".join(x.decode() for x in urls) if urls else "Hello without ICE servers"))
            else:
                rows.append(("turn/ice", u, f"no Hello: {status}"))
        except Exception as ex:
            rows.append(("turn/ice", u, f"FAIL {ex!r}"))
    # STUN: at most STUN_PROBES_PER_CALL single binding requests per call, never an endpoint checked within the fresh window
    probes = e["STUN_PROBES_PER_CALL"] or 3
    pool = e["stun"][:]
    random.shuffle(pool)
    done = 0
    for h in pool:
        if done >= (len(pool) if a.all else probes):
            break
        sk = polite(h)
        if sk:
            rows.append(("stun", h, sk))
            continue
        host, _, port = h.partition(":")
        ms = _udp_stun(host, int(port or 3478))
        rows.append(("stun", h, f"OK {ms} ms" if ms is not None else "FAIL no answer"))
        note(h, ms is not None)
        done += 1
    # Nostr: a websocket handshake only (no subscription, no event), at most NOSTR_MAX_BROWSE relays per call
    maxn = e["NOSTR_MAX_BROWSE"] or 3
    pool = e["nostr"][:]
    random.shuffle(pool)
    done = 0
    for u in pool:
        if done >= (len(pool) if a.all else maxn):
            break
        sk = polite(u)
        if sk:
            rows.append(("nostr", u, sk))
            continue
        t = time.time()
        try:
            sock, status, body = wsmini.connect(u, timeout=5)
            if sock:
                sock.sendall(wsmini.encode(8, b"\x03\xe8", mask=True))
                sock.close()
            rows.append(("nostr", u, f"{'OK' if sock else 'FAIL'} {status[:40]} in {int((time.time() - t) * 1000)} ms"))
            note(u, bool(sock))
        except Exception as ex:
            rows.append(("nostr", u, f"FAIL {ex!r}"[:90]))
            note(u, False)
        done += 1
    state_p.parent.mkdir(parents=True, exist_ok=True)
    state_p.write_text(json.dumps(state))
    print("== probes (one polite request each; same caps as tango-net/src/endpoints.rs)")
    for kind, u, r in rows:
        print(f"  {kind:10} {u:42} {r}")
    util.say(f"probe memory: {state_p} (no endpoint is probed twice within {fresh} s, failures back off like the app)")
    return 0


# ---- soak ----
def cmd_soak(a):
    end = time.time() + a.hours * 3600
    out = cfg.work("soak", time.strftime("%Y%m%d_%H%M%S"))
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(a.seed)
    logf = out / "soak.jsonl"
    util.say(f"soaking for {a.hours} h; seed {a.seed}; log {logf}; local signalling (nothing leaves this Mac)")
    runs = bad = 0
    while time.time() < end:
        n = rnd.choice([2, 2, 3, 4])
        fog = rnd.choice(["on", "off"])
        lv = rnd.choice(list(LEVELS))
        name = "lobby"
        if n == 2 and rnd.random() < 0.5:
            name = rnd.choice(["moveview", "move", "attack", "power", "build", "capture", "yield", "load"])
        spec = live.make_spec(name, fog, n, rnd.choice([2, 3, 4]), f"soak_{n}p", a.hz, a.max_s)
        spec.impair = impair_for(spec.n, lv)
        spec.local_signal = True
        spec.extra_env["TANGOAW2_HASH_PARTS"] = "1"
        events = []
        if rnd.random() < a.chaos and spec.n >= 2:
            k = rnd.randrange(1, spec.n)
            kind = rnd.choice(["stop", "kill-relaunch", "stop"])
            at = rnd.randint(60, 150)
            if kind == "stop":
                events.append({"action": "stop", "seat": k, "at_s": at, "arg": rnd.choice([4, 8, 15])})
            else:
                events += [{"action": "kill", "seat": k, "at_s": at}, {"action": "relaunch", "seat": k, "at_s": at + 14}]
        spec.events = events
        rec = {"t": time.strftime("%F %T"), "scenario": name, "players": spec.n, "fog": fog, "impair": lv, "events": events}
        try:
            res = live.run(spec, quiet=True)
            run = Run(res["run"])
            ok, v = judge(run, res, with_leak=False)
            crash = []
            for lg in run.dir.glob("tango_s*.log"):
                crash += [l[:200] for l in lg.read_text(errors="ignore").splitlines() if "panicked at" in l or "fatal runtime error" in l]
            for lg in run.dir.glob("stdout_s*.log"):
                crash += [l[:200] for l in lg.read_text(errors="ignore").splitlines() if "panicked at" in l or "Segmentation" in l]
            rec.update(run=str(run.dir), ok=ok and not crash, verdict={k: x["pass"] for k, x in v.items()}, crash=crash[:3])
            if not rec["ok"]:
                bad += 1
                util.say("SOAK FAILURE", json.dumps(rec)[:300])
            else:
                shutil.rmtree(run.dir, ignore_errors=True)   # keep only what failed
        except SystemExit:
            raise
        except Exception as ex:
            rec.update(ok=False, error=repr(ex))
            bad += 1
        runs += 1
        with open(logf, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        time.sleep(a.pause)
    print(f"soak done: {runs} runs, {bad} failed; log {logf}")
    return 1 if bad else 0
