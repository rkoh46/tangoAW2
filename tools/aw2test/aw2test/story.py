"""Tracing a story flow (a campaign's prologue, briefings, between-mission scenes, mission cards, the battle's start): every few frames
the song the game started last, the music player's state and fade, the dialogue box's text, the screen's brightness and (optionally)
the sound that came out, so a flow can be read as a table: scene -> track, where music is missing, whether it fades.

Used by `aw2dev campaign trace` (devkit/aw2/commands/campaign.py) and tests/test_bh_story.py. Nothing from the games is kept: the trace
files go to the run's output folder (git-ignored)."""

import json
import os
import struct

SONG = 0x030005CA        # the song id the game last started (sub_0803B524)
BGM = 0x03005AE0         # the CO themes' music player (header, status, ... fade fields)
FADE = BGM + 0x24        # fadeOI, fadeOC, fadeOV (u16 each): a fade in progress when OC is not 0
SONG_TABLE_POOL = 0x080704A0


def clean(t):
    return t.replace("\x0f", " ").replace("\r", " ").replace("  ", " ").strip() if t else t


def brightness(bmp):
    """Mean brightness (0..255) of a BMP file (24 or 32 bit), sampled."""
    with open(bmp, "rb") as f:
        b = f.read()
    off = struct.unpack_from("<I", b, 10)[0]
    bpp = struct.unpack_from("<H", b, 28)[0]
    data = b[off:]
    px = bpp // 8
    if px not in (3, 4):
        return 0.0
    n = len(data) // px
    step = max(1, n // 2000)
    idx = range(0, n, step)
    return sum(data[i * px] + data[i * px + 1] + data[i * px + 2] for i in idx) / (3 * len(idx))


class Tracer:
    """Samples a running console every `step` frames while the caller drives it (`through`)."""

    def __init__(self, e, d, out, label, shots=True, audio=True):
        self.e, self.d, self.out, self.label, self.shots = e, d, out, label, shots
        self.rows = []
        self.audio = audio
        self.t0 = e.frame
        self.last_key = None
        self.same = 0
        os.makedirs(out, exist_ok=True)
        if audio:
            e.audio_start()

    def sample(self, note=""):
        e, d = self.e, self.d
        status = e.u32(BGM + 4)
        oi, oc, ov = struct.unpack("<3H", e.read(FADE, 6))
        text = None
        try:
            text = clean(d.text_shown())
        except Exception:
            pass
        row = {
            "frame": e.frame - self.t0, "song": e.u16(SONG), "playing": bool(status & 0xFFFF) and not status & 0x80000000,
            "fade": [oi, oc, ov], "text": text, "battle": d.in_battle(), "map": d.world_map_up(), "script": d.scripts_running(),
        }
        if self.shots:
            bmp = e.shot(os.path.join(self.out, f"{self.label}_cur"))
            row["bright"] = round(brightness(bmp), 1)
            key = (row["song"], text, row["battle"], row["map"])
            # (a box that has stayed on the screen for ten samples is typed out: its picture is the "settled" one, kept as <label>_<n>s.bmp)
            self.same = self.same + 1 if key == self.last_key else 0
            if text and self.same == 10:
                name = f"{self.label}_{len(self.rows):04d}s.bmp"
                os.replace(bmp, os.path.join(self.out, name))
                row["settled"] = name
            elif key != self.last_key:
                name = f"{self.label}_{len(self.rows):04d}.bmp"
                os.replace(bmp, os.path.join(self.out, name))
                row["shot"] = name
                self.last_key = key
        if note:
            row["note"] = note
        self.rows.append(row)
        return row

    def attach(self, step=20):
        """Sample whenever the console is driven by anyone: `e.wait` runs in slices of `step` frames and `e.press` is followed by a sample, so a flow another
        helper steps through (a mission's CO screen, card and intro) is traced as it is played."""
        e = self.e
        orig_wait, orig_press = e.wait, e.press

        def wait(n):
            while n > 0:
                k = min(step, n)
                orig_wait(k)
                n -= k
                self.sample()

        def press(keys, n=2):
            orig_press(keys, n)
            self.sample()
        e.wait, e.press = wait, press
        return self

    def detach(self):
        for name in ("wait", "press"):
            self.e.__dict__.pop(name, None)

    def through(self, until, max_frames=20000, step=20, press_every=3):
        """Press A every `press_every` samples, sampling every `step` frames, until `until(row)` (or the frame budget)."""
        e = self.e
        n = 0
        while n < max_frames:
            row = self.sample()
            if until(row):
                return row
            if len(self.rows) % press_every == 0:
                e.press("A", 4)
                e.wait(max(1, step - 10))
            else:
                e.wait(step)
            n += step
        return None

    def finish(self):
        """Stop the recording; write <label>.json (rows, with the sound's loudness) into the output folder."""
        e = self.e
        if self.audio:
            wav = os.path.join(self.out, f"{self.label}.wav")
            frames, rate = e.audio_end(wav)
            sound = loudness(wav, rate, [r["frame"] for r in self.rows])
            if sound:
                for r, v in zip(self.rows, sound):
                    r["rms"] = v
        with open(os.path.join(self.out, f"{self.label}.json"), "w") as f:
            json.dump(self.rows, f)
        return self.rows


def loudness(path, rate, at):
    """RMS (0..32767) of the 1/30 s of audio ending at each sample's frame, from a 16-bit stereo WAV."""
    try:
        with open(path, "rb") as f:
            b = f.read()
    except OSError:
        return None
    i = b.find(b"data")
    if i < 0:
        return None
    pcm = b[i + 8:]
    out = []
    per_frame = rate / 59.7275
    for fr in at:
        end = int(fr * per_frame) * 4
        start = max(0, end - int(per_frame * 2) * 4)
        seg = pcm[start:end]
        n = len(seg) // 2
        if n < 4:
            out.append(0)
            continue
        vals = struct.unpack(f"<{n}h", seg[:n * 2])
        out.append(int((sum(v * v for v in vals) / n) ** 0.5))
    return out


def kind_of(r):
    return "dialogue" if r["text"] else "battle" if r["battle"] else "map" if r["map"] else "other"


def scenes(rows, quiet_rms=60):
    """Collapse a trace into scenes: runs of samples with the same song id and the same kind of screen (dialogue / map / battle / other)
    with their frames, the quietest and loudest sound, how many samples were silent, and the first text line."""
    out = []
    for r in rows:
        kind = kind_of(r)
        silent = 1 if (not r["playing"] or r.get("rms", 999) < quiet_rms) else 0
        if out and out[-1]["song"] == r["song"] and out[-1]["kind"] == kind:
            s = out[-1]
            s["end"] = r["frame"]
            s["rms_min"] = min(s["rms_min"], r.get("rms", 0))
            s["rms_max"] = max(s["rms_max"], r.get("rms", 0))
            s["samples"] += 1
            s["silent"] += silent
            s["text"] = s["text"] or r["text"]
            continue
        out.append({"start": r["frame"], "end": r["frame"], "song": r["song"], "kind": kind, "text": r["text"], "rms_min": r.get("rms", 0),
                    "rms_max": r.get("rms", 0), "samples": 1, "silent": silent})
    return out
