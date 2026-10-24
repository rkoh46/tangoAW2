"""Analysis of recorded game audio (16-bit stereo WAVs of the harness's `audio` capture): levels, spectra, loop seams, pictures. numpy and Pillow only."""
import wave

import numpy as np
from PIL import Image, ImageDraw

from .pitch import f0  # noqa: F401  (re-exported)


def load(path):
    """(rate, mono float array in -1..1, stereo array [n, 2])."""
    with wave.open(str(path), "rb") as w:
        rate, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    st = x.reshape(-1, ch) if ch > 1 else np.stack([x, x], 1)
    return rate, st.mean(1), st


def write(path, rate, st):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())


def db(v):
    return 20 * np.log10(max(float(v), 1e-9))


def levels(x, rate, skip=0.0):
    """Loudness numbers of a mono signal after `skip` seconds: RMS and peak in dBFS, the one-second RMS spread, and the share of energy in three bands."""
    x = x[int(skip * rate):]
    rms = float(np.sqrt(np.mean(x ** 2)))
    w = rate
    secs = np.array([np.sqrt(np.mean(x[i:i + w] ** 2)) for i in range(0, len(x) - w + 1, w)]) if len(x) >= w else np.array([rms])
    sp = np.abs(np.fft.rfft(x[: (len(x) // 4096) * 4096].reshape(-1, 4096) * np.hanning(4096), axis=1)) ** 2
    sp = sp.mean(0)
    fr = np.fft.rfftfreq(4096, 1 / rate)
    tot = sp.sum() + 1e-12
    bands = [sp[fr < 250].sum() / tot, sp[(fr >= 250) & (fr < 2000)].sum() / tot, sp[(fr >= 2000)].sum() / tot]
    cen = float((sp * fr).sum() / tot)
    return dict(rms_db=db(rms), peak_db=db(np.abs(x).max()), sec_p10_db=db(np.percentile(secs, 10)), sec_p50_db=db(np.percentile(secs, 50)),
                sec_p90_db=db(np.percentile(secs, 90)), low=float(bands[0]), mid=float(bands[1]), high=float(bands[2]), centroid=cen, seconds=len(x) / rate)


def envelope(x, rate, hop=0.01):
    h = int(rate * hop)
    n = len(x) // h
    return np.sqrt(np.mean(x[: n * h].reshape(n, h) ** 2, axis=1))


def loop_seams(x, rate, intro_s, loop_s, passes=2):
    """The loop's seams in a recording that starts with the song: for each seam (the end of an intro or a pass), what the sound does there.

    - `period_err_ms`: how far the music's period is from the file's (best match of the second pass against the first by the 10 ms envelope);
    - `click`: the largest step of the signal within 30 ms of the seam over the 99.9th percentile of such steps elsewhere (a click is far above 1);
    - `gap`: the quietest 20 ms next to the seam over the 10th percentile of such dips elsewhere in the recording (a silence gap is far below 1);
    - `repeat_corr`: how alike the second second of one pass and the same second of the next are (envelope correlation, near 1 for a clean loop)."""
    env = envelope(x, rate, 0.01)
    out = dict(seams=[])
    P = int(round(loop_s * 100))
    I = int(round(intro_s * 100))
    if len(env) >= I + 2 * P - 50:
        a = env[I + 100: I + P - 100]
        best = None
        for d in range(-40, 41):
            b = env[I + 100 + P + d: I + P - 100 + P + d]
            if len(b) != len(a):
                continue
            c = float(np.corrcoef(a, b)[0, 1])
            if best is None or c > best[0]:
                best = (c, d)
        out["repeat_corr"] = best[0]
        out["period_err_ms"] = best[1] * 10.0
    d1 = np.abs(np.diff(x))
    elsewhere = np.percentile(d1, 99.9)
    e20 = envelope(x, rate, 0.02)
    # the quietest 20 ms in every 120 ms window of the whole recording: what a gap in the music's own rhythm looks like
    dips = np.array([e20[i:i + 6].min() for i in range(10, len(e20) - 6, 3)])
    typical = float(np.percentile(dips, 10)) or 1e-9
    for k in range(passes + 1):
        t = intro_s + k * loop_s
        if t * rate + rate * 0.1 > len(x) or t <= 0.05:
            continue
        a, b = int((t - 0.03) * rate), int((t + 0.03) * rate)
        seg = d1[a:b]
        click = float(seg.max() / max(elsewhere, 1e-9))
        e = envelope(x[int((t - 0.06) * rate): int((t + 0.06) * rate)], rate, 0.02)
        gap = float(e.min() / typical)
        out["seams"].append(dict(t=t, click=click, gap=gap))
    return out


def picture(x, rate, path, marks=(), width=1400, height=360):
    """Envelope (top) and spectrogram (bottom) of a whole recording, with the loop seams marked."""
    seg = max(1, len(x) // width)
    env = np.array([np.abs(x[i:i + seg]).max() for i in range(0, seg * width, seg)])
    top = Image.new("RGB", (width, 100), (16, 20, 28))
    d = ImageDraw.Draw(top)
    for c, v in enumerate(env[:width]):
        d.line([(c, 50 - v / max(env.max(), 1e-6) * 48), (c, 50 + v / max(env.max(), 1e-6) * 48)], fill=(90, 200, 120))
    nfft = 1024
    hop = max(nfft // 2, (len(x) - nfft) // width)
    cols = [np.abs(np.fft.rfft(x[i:i + nfft] * np.hanning(nfft))) for i in range(0, len(x) - nfft, hop)]
    m = np.array(cols).T
    fr = np.fft.rfftfreq(nfft, 1 / rate)
    m = m[fr < 8000]
    m = 20 * np.log10(m + 1e-6)
    m = np.clip((m - (m.max() - 70)) / 70, 0, 1)
    sp = Image.fromarray((m[::-1] * 255).astype(np.uint8)).resize((width, height - 100), Image.BILINEAR)
    sp = Image.merge("RGB", [sp.point(lambda v: min(255, v * 2)), sp.point(lambda v: max(0, min(255, v * 2 - 128))), sp.point(lambda v: 255 - v // 2 if v < 128 else 60)])
    im = Image.new("RGB", (width, height))
    im.paste(top, (0, 0))
    im.paste(sp, (0, 100))
    dd = ImageDraw.Draw(im)
    total = len(x) / rate
    for t in marks:
        cx = int(t / total * width)
        dd.line([(cx, 0), (cx, height)], fill=(255, 220, 60))
    im.save(path)



def seam_picture(x, rate, seams, path, span=0.8, width=520, height=130):
    """A strip of panels, one per seam: the 5 ms envelope (top) and the waveform (bottom) from `span` seconds before to `span` after it, the seam in the middle."""
    im = Image.new("RGB", (width * len(seams), height + 14), (10, 12, 16))
    d = ImageDraw.Draw(im)
    for k, t in enumerate(seams):
        a, b = int((t - span) * rate), int((t + span) * rate)
        seg = x[max(0, a):b]
        if len(seg) < 100:
            continue
        ox = k * width
        hop = max(1, len(seg) // width)
        env = np.array([np.sqrt(np.mean(seg[i:i + hop] ** 2)) for i in range(0, hop * width, hop)])
        peak = max(float(np.abs(x).max()), 1e-6)
        for c, v in enumerate(env[:width]):
            h = min(1.0, v / peak * 1.4) * (height * 0.45)
            d.line([(ox + c, 14 + height * 0.5 - h), (ox + c, 14 + height * 0.5 + h)], fill=(90, 200, 120))
        d.line([(ox + width // 2, 14), (ox + width // 2, 14 + height)], fill=(255, 220, 60))
        d.text((ox + 4, 1), f"seam at {t:.1f} s (+-{span} s)", fill=(255, 230, 120))
    im.save(path)


def resample(st, rate_in, rate_out):
    """A stereo array resampled by the FFT (band-limited: nothing above the lower Nyquist survives)."""
    n_in = st.shape[0]
    n_out = int(round(n_in * rate_out / rate_in))
    out = np.zeros((n_out, st.shape[1]), dtype=np.float32)
    for c in range(st.shape[1]):
        X = np.fft.rfft(st[:, c].astype(np.float64))
        Y = np.zeros(n_out // 2 + 1, dtype=complex)
        k = min(len(X), len(Y))
        Y[:k] = X[:k]
        out[:, c] = np.fft.irfft(Y, n=n_out) * (n_out / n_in)
    return out
