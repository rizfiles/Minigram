#!/usr/bin/env python3
"""
Generator ikon Minigram: pesawat putih (pesawat terbang, bukan pesawat kertas)
di atas latar dark grey. Semua ikon dibuat dari satu bentuk vektor.

Pemakaian:
  python3 minigram/make_icons.py --preview out_icons      # hanya buat SVG/PNG pratinjau
  python3 minigram/make_icons.py --apply .                # timpa ikon di source (root repo)

Butuh: pip install pillow
"""
import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

BG = "#2B2B2E"     # dark grey
FG = "#FFFFFF"     # putih

# Setengah sisi kanan siluet pesawat, hidung menghadap atas, satuan bebas
# (panjang ~61, rentang sayap 60). Sisi kiri adalah cerminannya.
def _build_half():
    pts = []
    # hidung membulat (seperempat elips)
    for i in range(0, 11):
        t = math.radians(i * 9)
        pts.append((3.5 * math.sin(t), -19 - 11 * math.cos(t)))
    pts += [
        (3.5, -6),                                   # badan -> pangkal sayap
        (30, 10), (30, 14.5), (3.5, 8.5),            # sayap utama
        (3.5, 20),                                   # badan -> ekor
        (14, 28), (14, 31.5), (2.6, 28.2),           # sayap ekor
    ]
    # ujung ekor membulat
    for i in range(1, 11):
        t = math.radians(i * 9)
        pts.append((2.6 * math.cos(t), 28.2 + 2.6 * math.sin(t)))
    return pts


HALF = _build_half()
ROTATE_DEG = 45  # hidung ke kanan-atas, supaya terlihat "terbang" dan beda dari logo kertas Telegram
MAX_R = 31.7     # jarak terjauh dari pusat (setelah rotasi tidak berubah)


def outline():
    right = HALF
    left = [(-x, y) for x, y in reversed(HALF[1:-1])]
    pts = right + left
    a = math.radians(ROTATE_DEG)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def place(pts, cx, cy, f):
    return [(cx + x * f, cy + y * f) for x, y in pts]


def render(size, kind, ss=4):
    """kind: 'square' | 'round' | 'plane' (putih, latar transparan)."""
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if kind == "square":
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=BG)
        f = S * 0.36 / MAX_R
    elif kind == "round":
        d.ellipse([0, 0, S - 1, S - 1], fill=BG)
        f = S * 0.34 / MAX_R
    else:
        f = S * 0.47 / MAX_R
    d.polygon(place(outline(), S / 2, S / 2, f), fill=FG)
    return img.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------------ vektor Android
def vector_xml():
    pts = place(outline(), 54, 54, 1.0)
    path = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
    <path
        android:fillColor="{FG}"
        android:pathData="{path}" />
</vector>
"""


def bg_xml():
    return f"""<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="{BG}" />
</shape>
"""


def adaptive_xml():
    return """<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@drawable/minigram_bg" />
    <foreground android:drawable="@drawable/minigram_plane" />
    <monochrome android:drawable="@drawable/minigram_plane" />
</adaptive-icon>
"""


def svg_master():
    pts = place(outline(), 256, 256, 512 * 0.36 / MAX_R)
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <rect width="512" height="512" rx="113" fill="{BG}"/>
  <path d="{path}" fill="{FG}"/>
</svg>
"""


# ------------------------------------------------------------------ output
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
NOTIF = {"mdpi": 24, "hdpi": 36, "xhdpi": 48, "xxhdpi": 72}


def do_preview(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "minigram_icon.svg").write_text(svg_master(), encoding="utf-8")
    render(512, "square").save(out / "minigram_icon_512.png")
    render(512, "round").save(out / "minigram_icon_round_512.png")
    render(1024, "square").save(out / "minigram_icon_1024.png")
    print(f"Pratinjau ditulis ke {out}/")


def do_apply(root):
    res = Path(root) / "TMessagesProj/src/main/res"
    if not res.is_dir():
        raise SystemExit(f"Folder resource tidak ditemukan: {res}")

    # Android 8+ (adaptive icon) untuk ikon utama dan ikon alternatif
    (res / "drawable/minigram_bg.xml").write_text(bg_xml(), encoding="utf-8")
    (res / "drawable/minigram_plane.xml").write_text(vector_xml(), encoding="utf-8")
    names = ["ic_launcher"] + [f"icon_{i}_launcher" for i in range(2, 7)]
    for n in names:
        for suffix in ("", "_round"):
            (res / f"mipmap-anydpi-v26/{n}{suffix}.xml").write_text(adaptive_xml(), encoding="utf-8")

    # Android 6-7 (PNG biasa)
    for dens, px in DENSITIES.items():
        sq, rd = render(px, "square"), render(px, "round")
        for n in names:
            sq.save(res / f"mipmap-{dens}/{n}.png")
            rd.save(res / f"mipmap-{dens}/{n}_round.png")
        # ikon akun/kontak/panggilan
        rd.save(res / f"drawable-{dens}/ic_launcher_dr.webp", lossless=True)

    # ikon kecil notifikasi di status bar (putih, transparan)
    for dens, px in NOTIF.items():
        render(px, "plane").save(res / f"drawable-{dens}/notification.webp", lossless=True)

    print("[ok] Ikon Minigram diterapkan (launcher, adaptive, kontak, notifikasi)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", metavar="DIR")
    ap.add_argument("--apply", metavar="REPO_ROOT")
    a = ap.parse_args()
    if not a.preview and not a.apply:
        ap.error("pilih --preview DIR atau --apply REPO_ROOT")
    if a.preview:
        do_preview(a.preview)
    if a.apply:
        do_apply(a.apply)
