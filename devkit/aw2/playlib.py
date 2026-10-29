"""`aw2dev campaign playthrough` reports (docs/dev/playthrough.md): the JSON a `tests/test_playthrough.py` run writes, as Markdown and a contact sheet of its key moments."""
import os


def markdown(rep):
    L = [f"# M{rep['mission']} {rep['title']}: a playthrough ({rep.get('player', 'cpu')} as the player)", ""]
    L.append(f"- outcome: **{rep['result']}** after {rep['days']} days ({rep['frames']} frames), stages reached {rep['stages_reached']}" + (f", {rep['reason']}" if rep.get("reason") else ""))
    for e in rep["events"]:
        if e["event"] == "stage switch":
            L.append(f"- day {e['day']}: stage {e['from']} -> {e['to']}")
        else:
            L.append(f"- day {e['day']} (stage {e['stage']}): {e['hq']}'s HQ taken (owner army {e['owner']})")
    for s in rep["stalls"]:
        L.append(f"- stop: day {s['day']} (stage {s['stage']}): {s['why']}")
    L += ["", "## Units and funds at the start of each day", "", "| day | stage | " + " | ".join(f"army {a}" for a in range(1, 6)) + " |", "|---|---|" + "---|" * 5]
    for d in rep["daily"]:
        cells = []
        for a in range(1, 6):
            u, f = d["units"].get(str(a), d["units"].get(a)), d["funds"].get(str(a), d["funds"].get(a))
            cells.append("-" if u is None and f is None else f"{u or 0} u / {f if f is not None else '-'}")
        L.append(f"| {d['day']} | {d['stage']} | " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def contact_sheet(rep, out, cols=3, cw=360):
    """The key pictures (start, each takeover, the switch, a stall, the end) on one sheet, each labelled."""
    from PIL import Image, ImageDraw
    items = []
    for s in rep["shots"]:
        p = os.path.join(rep["dir"], s["file"] + ".bmp")
        if os.path.exists(p):
            items.append((p, f"day {s['day']} stage {s['stage'] + 1}: {s['why']}"))
    if not items:
        return None
    ch = int(cw * 160 / 240)
    rows = (len(items) + cols - 1) // cols
    im = Image.new("RGB", (cols * cw, rows * (ch + 18)), (20, 20, 28))
    dr = ImageDraw.Draw(im)
    for i, (p, label) in enumerate(items):
        x, y = (i % cols) * cw, (i // cols) * (ch + 18)
        im.paste(Image.open(p).convert("RGB").resize((cw, ch), Image.NEAREST), (x, y + 18))
        dr.text((x + 4, y + 3), label, fill=(240, 220, 120))
    im.save(out)
    return out
