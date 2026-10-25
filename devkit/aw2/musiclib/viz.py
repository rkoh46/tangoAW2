"""Pictures of sound with Pillow and numpy only: spectrograms, waveform envelopes, a sheet of the samples in a voice group."""
import numpy as np
from PIL import Image, ImageDraw


def spectrogram(x, rate, w=400, h=120, fmax=6000.0, nfft=512):
    """A log-magnitude spectrogram (time left to right, low frequencies at the bottom) as an RGB image."""
    x = np.asarray(x, dtype=float)
    if len(x) < nfft:
        x = np.pad(x, (0, nfft - len(x)))
    hop = max(1, (len(x) - nfft) // max(1, w - 1))
    win = np.hanning(nfft)
    cols = []
    for i in range(0, len(x) - nfft + 1, hop):
        s = np.abs(np.fft.rfft(x[i:i + nfft] * win))
        cols.append(s)
    m = np.array(cols).T
    fr = np.fft.rfftfreq(nfft, 1 / rate)
    m = m[fr <= fmax]
    m = 20 * np.log10(m + 1e-6)
    top = m.max()
    m = np.clip((m - (top - 60)) / 60, 0, 1)
    img = Image.fromarray((m[::-1] * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    return Image.merge("RGB", [img.point(lambda v: min(255, v * 2)), img.point(lambda v: max(0, min(255, v * 2 - 128))), img.point(lambda v: 255 - v // 2 if v < 128 else 60)])


def waveform(x, w=400, h=40, colour=(90, 200, 120)):
    x = np.asarray(x, dtype=float)
    img = Image.new("RGB", (w, h), (16, 20, 28))
    if len(x) == 0:
        return img
    d = ImageDraw.Draw(img)
    peak = max(1e-9, np.abs(x).max())
    n = len(x)
    for c in range(w):
        seg = x[c * n // w:max(c * n // w + 1, (c + 1) * n // w)]
        d.line([(c, h / 2 - seg.max() / peak * h / 2 + 0.5), (c, h / 2 - seg.min() / peak * h / 2 - 0.5)], fill=colour)
    return img


def sheet(items, cols=4, w=300, hs=90, hw=30, fmax=6000.0):
    """items: [(label, samples, rate)] -> one image of waveform + spectrogram tiles with labels."""
    rows = (len(items) + cols - 1) // cols
    th = hs + hw + 14
    im = Image.new("RGB", (cols * (w + 6), rows * (th + 4)), (8, 10, 14))
    d = ImageDraw.Draw(im)
    for i, (label, x, rate) in enumerate(items):
        cx, cy = (i % cols) * (w + 6), (i // cols) * (th + 4)
        d.text((cx + 2, cy), label, fill=(255, 230, 120))
        im.paste(waveform(x, w, hw), (cx, cy + 12))
        im.paste(spectrogram(x, rate, w, hs, fmax), (cx, cy + 12 + hw))
    return im
