"""M4A (MP2K, "Sappy") readers for AW2's ROM: songs, voice groups, samples, and a track disassembler.

Everything is read from the player's ROM at run time; nothing from it is stored. Song header: [tracks, unused, priority, reverb],
voice group pointer, track pointers. A voice entry is 12 bytes: type, key, length/pan, pan, then two words (sample or sub-voice table
pointer; ADSR). Types: 0 DirectSound, 8 DirectSound at fixed pitch, 1/9 square 1, 2/0xA square 2, 3/0xB programmable wave, 4/0xC noise,
0x40 key split, 0x80 rhythm (one sub-voice a key).
"""
import struct

ROM_BASE = 0x08000000
SONG_TABLE = 0x0824238C
SONGS = 505
LENGTHS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
           28, 30, 32, 36, 40, 42, 44, 48, 52, 54, 56, 60, 64, 66, 68, 72, 76, 78, 80, 84, 88, 90, 92, 96]
GROUP_A = 0x08240FB0
GROUP_B = 0x082415C8
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def key_name(k):
    """Scientific names: key 60 is C4."""
    return f"{KEYS[k % 12]}{k // 12 - 1}"


class Rom:
    def __init__(self, data):
        self.d = data

    def u8(self, a):
        return self.d[a - ROM_BASE]

    def u16(self, a):
        return struct.unpack_from("<H", self.d, a - ROM_BASE)[0]

    def u32(self, a):
        return struct.unpack_from("<I", self.d, a - ROM_BASE)[0]

    def song_header(self, sid):
        o = SONG_TABLE - ROM_BASE + 8 * sid
        h, p1, p2 = struct.unpack_from("<IHH", self.d, o)
        return h, p1

    def song(self, sid):
        h, player = self.song_header(sid)
        n = self.u8(h)
        return dict(id=sid, header=h, player=player, tracks=n, priority=self.u8(h + 2), reverb=self.u8(h + 3),
                    group=self.u32(h + 4), track_ptrs=[self.u32(h + 8 + 4 * i) for i in range(n)])

    def voice(self, group, i):
        a = group + 12 * i
        t, k, u, p = self.d[a - ROM_BASE: a - ROM_BASE + 4]
        w, adsr = struct.unpack_from("<II", self.d, a - ROM_BASE + 4)
        return dict(type=t, key=k, u=u, pan=p, word=w, adsr=tuple(adsr.to_bytes(4, "little")))

    def sample(self, ptr):
        """A DirectSound wave: (frequency Hz, loop start or None, signed 8-bit PCM bytes)."""
        o = ptr - ROM_BASE
        flags, freq, loop, size = struct.unpack_from("<IIII", self.d, o)
        pcm = self.d[o + 16: o + 16 + size + 1]
        return freq / 1024.0, (loop if (flags >> 16) & 0xC000 else None), pcm


def disasm(rom, ptr, limit=20000):
    """One track as a list of (address, text). Follows nothing: PATT/GOTO are shown as written."""
    out = []
    a = ptr
    last_cmd = None
    n = 0
    while n < limit:
        n += 1
        c = rom.u8(a)
        at = a
        a += 1
        if c < 0x80:                          # running status: arguments of the previous command again
            out.append((at, f"  ({c})"))
            continue
        if c <= 0xB0:
            out.append((at, f"W{LENGTHS[c - 0x80]:02d}"))
        elif c == 0xB1:
            out.append((at, "FINE"))
            break
        elif c in (0xB2, 0xB3):
            out.append((at, ("GOTO" if c == 0xB2 else "PATT") + f" {rom.u32(a):08x}"))
            a += 4
            if c == 0xB2:
                break
        elif c == 0xB4:
            out.append((at, "PEND"))
        elif c == 0xB5:
            out.append((at, f"REPT {rom.u8(a)} {rom.u32(a + 1):08x}"))
            a += 5
        elif c in (0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC8):
            name = {0xBA: "PRIO", 0xBB: "TEMPO", 0xBC: "KEYSH", 0xBD: "VOICE", 0xBE: "VOL", 0xBF: "PAN", 0xC0: "BEND", 0xC1: "BENDR", 0xC2: "LFOS",
                    0xC3: "LFODL", 0xC4: "MOD", 0xC5: "MODT", 0xC8: "TUNE"}[c]
            out.append((at, f"{name} {rom.u8(a)}"))
            a += 1
        elif c == 0xCE or c >= 0xCF:
            ln = "TIE" if c == 0xCF else ("EOT" if c == 0xCE else f"N{LENGTHS[c - 0xCF]:02d}")
            args = []
            while rom.u8(a) < 0x80 and len(args) < 3:
                args.append(rom.u8(a))
                a += 1
            txt = ln
            if args:
                txt += " " + key_name(args[0])
            if len(args) > 1:
                txt += f" v{args[1]}"
            if len(args) > 2:
                txt += f" +{args[2]}"
            out.append((at, txt))
        else:
            out.append((at, f"?{c:02x}"))
    return out


def summary(rom, sid):
    """Per track: programs used, the notes' key range, the wait total of one pass, and its loop target."""
    s = rom.song(sid)
    tr = []
    for p in s["track_ptrs"]:
        prog, keys, ticks, loop, tempo = [], [], 0, None, None
        a = p
        for at, txt in disasm(rom, p):
            w = txt.split()
            if w[0].startswith("W") and w[0][1:].isdigit():
                ticks += int(w[0][1:])
            elif w[0] == "VOICE":
                prog.append(int(w[1]))
            elif w[0] == "TEMPO":
                tempo = int(w[1]) * 2
            elif w[0] == "GOTO":
                loop = int(w[1], 16)
            elif w[0][0] in "NT" and len(w) > 1 and w[0] != "TEMPO":
                keys.append(w[1])
        tr.append(dict(ptr=p, programs=sorted(set(prog)), notes=len(keys), ticks=ticks, loop=loop, tempo=tempo))
    return s, tr


_CTL = {0xBA: "PRIO", 0xBB: "TEMPO", 0xBC: "KEYSH", 0xBD: "VOICE", 0xBE: "VOL", 0xBF: "PAN", 0xC0: "BEND", 0xC1: "BENDR", 0xC2: "LFOS",
        0xC3: "LFODL", 0xC4: "MOD", 0xC5: "MODT", 0xC8: "TUNE"}


def run(rom, ptr, limit=400000):
    """Play a track's commands as the engine does, PATT/PEND/REPT expanded, up to its GOTO or FINE.
    Returns (events, end_tick, loop_tick, loop_target). Events: (tick, "NOTE", key, vel, ticks or None for TIE), (tick, "EOT", key),
    (tick, "VOICE"/"VOL"/"PAN"/"TEMPO"/..., value). loop_tick: the tick at which the first pass was at the GOTO's target address."""
    ev = []
    a = ptr
    tick = 0
    stack = []
    key, vel = 60, 127
    loop_target = loop_tick = None
    seen = {}
    for _ in range(limit):
        seen.setdefault(a, tick)
        c = rom.u8(a)
        a += 1
        if c < 0x80:
            continue
        if c <= 0xB0:
            tick += LENGTHS[c - 0x80]
        elif c == 0xB1:
            break
        elif c == 0xB2:
            loop_target = rom.u32(a)
            loop_tick = seen.get(loop_target)
            break
        elif c in (0xB3, 0xB5):
            if c == 0xB3:
                cnt, tgt, ret = 1, rom.u32(a), a + 4
            else:
                cnt, tgt, ret = max(rom.u8(a), 1), rom.u32(a + 1), a + 5
            stack.append([ret, cnt, tgt])
            a = tgt
        elif c == 0xB4:
            if not stack:
                break
            f = stack[-1]
            f[1] -= 1
            if f[1] > 0:
                a = f[2]
            else:
                stack.pop()
                a = f[0]
        elif c in _CTL:
            ev.append((tick, _CTL[c], rom.u8(a)))
            a += 1
        elif c >= 0xCE:
            args = []
            while rom.u8(a) < 0x80 and len(args) < 3:
                args.append(rom.u8(a))
                a += 1
            if args:
                key = args[0]
            if len(args) > 1:
                vel = args[1]
            if c == 0xCE:
                ev.append((tick, "EOT", key))
            else:
                ln = None if c == 0xCF else LENGTHS[c - 0xCF] + (args[2] if len(args) > 2 else 0)
                ev.append((tick, "NOTE", key, vel, ln))
        else:
            ev.append((tick, "?", c))
    return ev, tick, loop_tick, loop_target


def sounding_midi(x, rate, loop):
    """Two guesses at the pitch (MIDI number, 60 = middle C) a DirectSound voice sounds at when played at key 60, from its loop (or the steady part of a one-shot): the
    harmonic product spectrum (right when the fundamental is strong) and the autocorrelation (right for bass, where the second harmonic is the strong one; it can
    read an octave low on a bright loop). `shift` for a song = 60 - round(the right one); `aw2dev sound pitchcheck` plays the instruments and says which was right."""
    import numpy as np
    from .pitch import f0
    y = x[loop:] if loop is not None and len(x) - loop >= 64 else x[int(rate * 0.04): int(rate * 0.04) + 4096]
    if len(y) < 64:
        y = x[:4096]
    n = 8192
    y = np.tile(y, int(np.ceil(n / len(y))))[:n]
    y = y - y.mean()
    sp = np.abs(np.fft.rfft(y * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1 / rate)
    h = sp.copy()
    for k in (2, 3, 4):
        d = sp[::k]
        h[: len(d)] *= d
        h[len(d):] = 0
    h[fr < 40] = 0
    h[fr > 2500] = 0
    hps = 69 + 12 * np.log2(fr[h.argmax()] / 440.0)
    fz, _ = f0(y, rate, lo=30.0, hi=1500.0)
    ac = 69 + 12 * np.log2(fz / 440.0) if fz else 0.0
    return hps, ac
