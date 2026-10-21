"""Contact sheets and strips of a live run (port of qa/ts.py, actwin.py, acts.py, zstrip.py, hzstrip.py, drive/pairstrip.py, evsheet.py)."""
from PIL import Image, ImageDraw
from . import cfg, util
from .runlib import Run, game


def _label(im, text):
    ImageDraw.Draw(im).text((3, 3), text, fill=(255, 224, 64))


def _thumb(run, rec, cw, ch, text):
    try:
        im = game(run.image(rec["file"])).resize((cw, ch))
    except Exception:
        im = Image.new("RGB", (cw, ch), (40, 0, 0))
    _label(im, text)
    return im


def _out(run, name):
    d = run.dir / "sheets"
    d.mkdir(exist_ok=True)
    return d / name


def contact(run, t0=0.0, t1=None, frames=10, seats=None, cw=384, ch=256):
    """frames rows x seats columns, evenly spread between t0 and t1 seconds after the first battle action."""
    seats = seats or run.seats
    T0 = run.t0()
    last = max(run.shots(s)[-1]["ms"] for s in seats if run.shots(s))
    if t1 is None:
        t1 = (last - T0) / 1000
    ts = [T0 + int((t0 + (t1 - t0) * i / max(frames - 1, 1)) * 1000) for i in range(frames)]
    o = Image.new("RGB", (cw * len(seats), ch * frames))
    for r, t in enumerate(ts):
        for c, s in enumerate(seats):
            sh = run.shots(s)
            if sh:
                b = min(sh, key=lambda x: abs(x["ms"] - t))
                o.paste(_thumb(run, b, cw, ch, f"s{s} {b['file'][3:7]} t={(b['ms'] - T0) / 1000:+.2f}"), (c * cw, r * ch))
    out = _out(run, f"contact_{int(t0)}_{int(t1)}.jpg")
    o.save(out, quality=70)
    return out


def around(run, kind, idx, pre=3500, post=2500, seats=None, cw=420, ch=280):
    """All frames of every window within [-pre, +post] ms of the idx-th act (of `kind`, or any act)."""
    seats = seats or run.seats
    acts = run.acts(kind)
    if not (0 <= idx < len(acts)):
        util.die(f"act {idx} out of range ({len(acts)} {kind or 'acts'})")
    a = acts[idx]
    fr = {s: [x for x in run.shots(s) if a["ms"] - pre <= x["ms"] <= a["ms"] + post] for s in seats}
    rows = max(len(v) for v in fr.values())
    o = Image.new("RGB", (cw * len(seats), ch * max(rows, 1)))
    for c, s in enumerate(seats):
        for r, x in enumerate(fr[s]):
            o.paste(_thumb(run, x, cw, ch, f"s{s} {x['file'][3:7]} dt={x['ms'] - a['ms']:+d}ms"), (c * cw, r * ch))
    out = _out(run, f"around_{kind or 'act'}_{idx}.jpg")
    o.save(out, quality=65)
    return out, a


def strip(run, kind, idx, pre=300, post=1500, every=1, seats=None, cols=6, cw=320, ch=213):
    """The mover's window over every waiting window, frame by frame around the idx-th act of `kind` (default move): reads like a film strip."""
    seats = seats or run.seats
    acts = run.acts(kind or "move")
    if not (0 <= idx < len(acts)):
        util.die(f"{kind or 'move'} {idx} out of range ({len(acts)})")
    a = acts[idx]
    base = [x for x in run.shots(seats[0]) if a["ms"] - pre <= x["ms"] <= a["ms"] + post][::every]
    rows = (len(base) + cols - 1) // cols
    rh = ch + 14
    o = Image.new("RGB", (cols * cw, rows * rh * len(seats)), (20, 20, 28))
    for i, x in enumerate(base):
        for si, s in enumerate(seats):
            rec = x if si == 0 else min(run.shots(s), key=lambda r: abs(r["ms"] - x["ms"]))
            X, Y = (i % cols) * cw, ((i // cols) * len(seats) + si) * rh
            ImageDraw.Draw(o).text((X + 2, Y), f"s{s} {rec['ms'] - a['ms']:+d}ms tick {rec.get('tick')}", fill=(255, 224, 64))
            try:
                o.paste(game(run.image(rec["file"])).resize((cw, ch)), (X, Y + 14))
            except Exception:
                pass
    out = _out(run, f"strip_{kind or 'move'}_{idx}.png")
    o.save(out)
    return out, a


def events(run, seat=None, cw=480, ch=320):
    """A sheet of every non-build act: the frame before, at and after it on one window."""
    seat = run.seats[-1] if seat is None else seat
    shots = run.shots(seat)
    cells = []
    for a in [a for a in run.acts() if a["what"] != "build"]:
        i = shots.index(min(shots, key=lambda s: abs(s["ms"] - a["ms"])))
        for j in range(max(0, i - 1), min(len(shots), i + 3)):
            cells.append((f"{a['what']} a{a.get('actor')} {a.get('from', '')}->{a.get('to', '')} @{shots[j]['ms'] - a['ms']:+d}ms", shots[j]))
    cols = 4
    rows = (len(cells) + cols - 1) // cols
    o = Image.new("RGB", (cols * cw, max(rows, 1) * (ch + 14)), (20, 20, 28))
    for k, (lab, rec) in enumerate(cells):
        x, y = (k % cols) * cw, (k // cols) * (ch + 14)
        ImageDraw.Draw(o).text((x + 2, y), lab, fill=(255, 224, 64))
        try:
            im = game(run.image(rec["file"]))
            im.thumbnail((cw, ch))
            o.paste(im, (x, y + 14))
        except Exception:
            pass
    out = _out(run, f"events_s{seat}.png")
    o.save(out)
    return out, len(cells)


def cmd(args):
    run = Run(args.run if args.run != "latest" else Run.latest())
    seats = [int(x) for x in args.seats.split(",")] if args.seats else None
    if args.around is not None:
        kind = args.kind if args.kind != "any" else None
        out, a = _dispatch(run, args, kind, seats)
        print(out)
        util.say(f"{a['what']} act {args.around} at tick {a.get('tick')}: {a.get('from', '')} -> {a.get('to', '')}")
    elif args.events:
        out, n = events(run, args.seat)
        print(out)
    else:
        print(contact(run, args.t0, args.t1, args.frames, seats))
    return 0


def _dispatch(run, args, kind, seats):
    if args.strip:
        kw = {}
        if args.pre is not None:
            kw["pre"] = args.pre
        if args.post is not None:
            kw["post"] = args.post
        return strip(run, kind or "move", args.around, every=args.every, seats=seats, **kw)
    kw = {}
    if args.pre is not None:
        kw["pre"] = args.pre
    if args.post is not None:
        kw["post"] = args.post
    return around(run, kind, args.around, seats=seats, **kw)
