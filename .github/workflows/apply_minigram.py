#!/usr/bin/env python3
"""
Minigram patcher - dijalankan di ROOT repo fork DrKLO/Telegram.

Dipakai oleh workflow GitHub Actions (build-minigram.yml), jadi fork Anda
tidak perlu diedit manual. Skrip ini berhenti dengan error jika ada bagian
source yang tidak ditemukan (artinya upstream berubah dan patch perlu diperbarui).

Pengaturan ada di bagian CONFIG di bawah.
"""
import json
import re
import shutil
import sys
from pathlib import Path

# ============================== CONFIG ==============================
APP_NAME = "Minigram"
APP_PACKAGE = "org.minigram.messenger"

# Hapus sponsored message (iklan channel/bot/pencarian/video).
# Default False = iklan tampil seperti aplikasi resmi.
# PERHATIAN: Ketentuan API Telegram (core.telegram.org/api/terms, poin 3.3)
# mewajibkan klien pihak ketiga menampilkan sponsored message. Jika False,
# iklan tetap tampil seperti aplikasi resmi.
REMOVE_SPONSORED = False

# Menu pengaturan yang disembunyikan (nomor id SettingCell di SettingsActivity)
#   11 Telegram Premium | 12 Telegram Stars | 13 Pendapatan Grams
#   15 Telegram Business | 16 Kirim Hadiah
#   17 Ajukan Pertanyaan | 18 Pertanyaan Umum | 23 Fitur Telegram | 19 Kebijakan Privasi
HIDE_SETTINGS = True

# Ganti ikon launcher, ikon notifikasi, dan ikon kontak dengan ikon Minigram
# (pesawat putih di latar dark grey). Butuh file minigram/make_icons.py dan Pillow.
REPLACE_ICONS = True

# Bahasa: hanya English (bawaan) + Indonesia (diunduh dari server Telegram)
ONLY_EN_ID = True

# Tema monokrom: semua warna UI yang lewat sistem tema dijadikan abu-abu
# (warna beraksen seperti biru tautan/tombol dibuat hitam-arang di tema terang
# dan abu terang di tema gelap, supaya tetap terbaca).
MONOCHROME = True

# Bentuk rounded square: avatar (foto dan inisial) dan tombol bulat (FAB, dll.)
SQUARE_SHAPES = True

# Hanya bangun arsitektur arm64-v8a (HP modern, build jauh lebih cepat)
ARM64_ONLY = True
# ====================================================================

ROOT = Path.cwd()
JAVA = ROOT / "TMessagesProj/src/main/java/org/telegram"


def fail(msg):
    print(f"[GAGAL] {msg}", file=sys.stderr)
    sys.exit(1)


def read(p):
    return Path(p).read_text(encoding="utf-8")


def write(p, s):
    Path(p).write_text(s, encoding="utf-8")


def replace_once(path, old, new, label):
    s = read(path)
    if old not in s:
        fail(f"{label}: teks tidak ditemukan di {path}")
    write(path, s.replace(old, new, 1))
    print(f"[ok] {label}")


def sub_once(path, pattern, repl, label, flags=re.S):
    s = read(path)
    new, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        fail(f"{label}: pola tidak cocok di {path}")
    write(path, new)
    print(f"[ok] {label}")


if not (ROOT / "TMessagesProj").is_dir():
    fail("Jalankan dari root repo Telegram (folder yang berisi TMessagesProj).")

# ---------------------------------------------------------------- 1. Nama & package
sub_once(ROOT / "gradle.properties", r"APP_PACKAGE=\S+",
         f"APP_PACKAGE={APP_PACKAGE}", "APP_PACKAGE")

for strings in (ROOT / "TMessagesProj/src/main/res/values/strings.xml",):
    sub_once(strings, r'<string name="AppName">[^<]*</string>',
             f'<string name="AppName">{APP_NAME}</string>', "AppName")
    sub_once(strings, r'<string name="AppNameBeta">[^<]*</string>',
             f'<string name="AppNameBeta">{APP_NAME} Beta</string>', "AppNameBeta")

# google-services.json bawaan (dummy) harus cocok dengan package baru agar plugin tidak error.
# Jika Anda menyediakan google-services.json sendiri (secret), workflow akan menimpanya.
for gs in ROOT.glob("TMessagesProj_App*/google-services.json"):
    data = json.loads(read(gs))
    for client in data.get("client", []):
        info = client.get("client_info", {}).get("android_client_info", {})
        if info.get("package_name", "").startswith("org.telegram.messenger"):
            suffix = info["package_name"][len("org.telegram.messenger"):]
            info["package_name"] = APP_PACKAGE + suffix
    # hapus oauth client milik Telegram (tidak berlaku untuk package baru)
    write(gs, json.dumps(data, indent=2))
    print(f"[ok] {gs.relative_to(ROOT)} -> package {APP_PACKAGE}")

# ---------------------------------------------------------------- 2. BuildVars
bv = JAVA / "messenger/BuildVars.java"
replace_once(bv, "    public static boolean CHECK_UPDATES = true;",
             "    public static boolean CHECK_UPDATES = false;\n"
             f"    public static final boolean MINIGRAM_NO_ADS = {'true' if REMOVE_SPONSORED else 'false'};\n"
             f"    public static final boolean MINIGRAM_MONO = {'true' if MONOCHROME else 'false'};\n"
             f"    public static final boolean MINIGRAM_SQUARE = {'true' if SQUARE_SHAPES else 'false'};",
             "BuildVars: flag iklan, matikan cek update resmi")
replace_once(bv, "public static boolean SUPPORTS_PASSKEYS = true;",
             "public static boolean SUPPORTS_PASSKEYS = false;", "BuildVars: passkeys off")
replace_once(bv, "public static boolean SUPPORTS_FPNV = true;",
             "public static boolean SUPPORTS_FPNV = false;", "BuildVars: FPNV off")
sub_once(bv, r'SAFETYNET_KEY = "[^"]*";', 'SAFETYNET_KEY = "";', "BuildVars: SafetyNet key kosong")
# APP_ID / APP_HASH diisi oleh workflow dari secret (TG_API_ID, TG_API_HASH)

# ---------------------------------------------------------------- 3. Sponsored message
if REMOVE_SPONSORED:
    replace_once(
        JAVA / "messenger/MessagesController.java",
        "    public SponsoredMessagesInfo getSponsoredMessages(long dialogId) {\n",
        "    public SponsoredMessagesInfo getSponsoredMessages(long dialogId) {\n"
        "        if (BuildVars.MINIGRAM_NO_ADS) {\n            return null;\n        }\n",
        "Sponsored: chat channel & bot")
    replace_once(
        JAVA / "messenger/video/VideoAds.java",
        "        if (loading || loaded) return;\n",
        "        if (loading || loaded || BuildVars.MINIGRAM_NO_ADS) return;\n",
        "Sponsored: iklan video")
    replace_once(
        JAVA / "ui/Adapters/DialogsSearchAdapter.java",
        "if (query == null || query.length() < 4 || UserConfig.getInstance(currentAccount).isPremium()",
        "if (BuildVars.MINIGRAM_NO_ADS || query == null || query.length() < 4 || UserConfig.getInstance(currentAccount).isPremium()",
        "Sponsored: hasil pencarian")
    # pastikan import BuildVars ada (kelas ada di package org.telegram.messenger)
    for f in (JAVA / "messenger/video/VideoAds.java", JAVA / "ui/Adapters/DialogsSearchAdapter.java"):
        s = read(f)
        if "import org.telegram.messenger.BuildVars;" not in s and "import org.telegram.messenger.*;" not in s:
            s = re.sub(r"(\nimport org\.telegram\.messenger\.)", r"\nimport org.telegram.messenger.BuildVars;\1", s, count=1)
            write(f, s)
            print(f"[ok] import BuildVars -> {f.name}")

# ---------------------------------------------------------------- 4. Menu pengaturan
if HIDE_SETTINGS:
    sa = JAVA / "ui/SettingsActivity.java"
    # Premium, Stars, Pendapatan Grams, Business, Kirim Hadiah (id 11,12,13,15,16)
    sub_once(
        sa,
        r"        if \(!getMessagesController\(\)\.premiumFeaturesBlocked\(\)\) \{\n"
        r"            items\.add\(SettingCell\.Factory\.of\(11,.*?"
        r"(?=        if \(items\.get\(items\.size\(\) - 1\)\.viewType != UniversalAdapter\.VIEW_TYPE_SHADOW\))",
        "", "Menu: Premium, Stars, Grams, Business, Hadiah", )
    # Bantuan: header + id 17, 18, 23, 19
    sub_once(
        sa,
        r"        items\.add\(UItem\.asHeader\(getString\(R\.string\.SettingsHelp\)\)\);\n"
        r"(?:        items\.add\(SettingCell\.Factory\.of\((?:17|18|23|19),[^\n]*\n){4}",
        "", "Menu: Bantuan (Tanya, FAQ, Fitur, Kebijakan Privasi)")

# ---------------------------------------------------------------- 5. Bahasa
if ONLY_EN_ID:
    lc = JAVA / "messenger/LocaleController.java"
    s = read(lc)
    end = s.index("        loadOtherLanguages();")
    head, tail = s[:end], s[end:]
    head, n = re.subn(
        r"\n        localeInfo = new LocaleInfo\(\);\n.*?languagesDict\.put\(localeInfo\.shortName, localeInfo\);\n",
        "\n", head, flags=re.S)
    if n < 5:
        fail(f"Bahasa bawaan: hanya {n} blok ditemukan, diharapkan sekitar 9")
    write(lc, head + tail)
    print(f"[ok] Bahasa bawaan: {n} bahasa dihapus (sisa English)")
    # Daftar bahasa dari server: hanya Indonesia
    replace_once(
        lc,
        "TLRPC.TL_langPackLanguage language = (TLRPC.TL_langPackLanguage) res.objects.get(a);\n",
        "TLRPC.TL_langPackLanguage language = (TLRPC.TL_langPackLanguage) res.objects.get(a);\n"
        "                        if (!\"id\".equals(language.lang_code)) {\n                            continue;\n                        }\n",
        "Bahasa server: hanya Indonesia")
    res_dir = ROOT / "TMessagesProj/src/main/res"
    removed = []
    for lang in ("ar", "de", "es", "it", "ko", "nl", "pt-rBR", "ru", "uk"):
        d = res_dir / f"values-{lang}"
        if d.is_dir():
            shutil.rmtree(d)
            removed.append(lang)
    print(f"[ok] Folder resource dihapus: {', '.join(removed)}")

# ---------------------------------------------------------------- 5b. Tema monokrom
THEME = JAVA / "ui/ActionBar/Theme.java"
if MONOCHROME:
    replace_once(
        THEME,
        "    private static int getColorFromTable(SparseIntArray currentColors, int key, boolean[] isDefault) {\n",
        """    private static int getColorFromTable(SparseIntArray currentColors, int key, boolean[] isDefault) {
        final int c = getColorFromTableRaw(currentColors, key, isDefault);
        return BuildVars.MINIGRAM_MONO ? minigramMono(c) : c;
    }

    /** Minigram: ubah warna ke abu-abu, warna beraksen digelapkan/diterangkan agar kontras tetap baik. */
    public static int minigramMono(int c) {
        final int a = c >>> 24, r = (c >> 16) & 0xff, g = (c >> 8) & 0xff, b = c & 0xff;
        final int max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b));
        int gray = (r * 299 + g * 587 + b * 114) / 1000;
        if (max - min > 40) {
            final boolean dark = currentTheme != null && currentTheme.isDark();
            gray = dark ? Math.max(gray, 135) : Math.min(gray, 80);
        }
        return (a << 24) | (gray << 16) | (gray << 8) | gray;
    }

    private static int getColorFromTableRaw(SparseIntArray currentColors, int key, boolean[] isDefault) {
""",
        "Monokrom: tabel warna tema")
    replace_once(
        THEME,
        "            return provider.getColor(key);\n        }\n        return getColor(key);",
        "            final int pc = provider.getColor(key);\n            return BuildVars.MINIGRAM_MONO ? minigramMono(pc) : pc;\n        }\n        return getColor(key);",
        "Monokrom: resources provider")
    replace_once(
        THEME,
        "    public static int getCurrentColor(int key) {\n        return currentColors.get(key);",
        "    public static int getCurrentColor(int key) {\n        final int cc = currentColors.get(key);\n        return BuildVars.MINIGRAM_MONO ? minigramMono(cc) : cc;",
        "Monokrom: getCurrentColor")

# ---------------------------------------------------------------- 5c. Bentuk rounded square
if SQUARE_SHAPES:
    # Tombol/ikon bulat bawaan tema (FAB, dll.) -> rounded square
    s_theme = read(THEME)
    old = "OvalShape ovalShape = new OvalShape();"
    n = s_theme.count(old)
    if n < 3:
        fail(f"OvalShape: hanya {n} kemunculan di Theme.java, diharapkan 4")
    s_theme = s_theme.replace(old, "RectShape ovalShape = minigramCircleShape(size);")
    helper_anchor = "    public static ShapeDrawable createCircleDrawable(int size, int color) {\n"
    if helper_anchor not in s_theme:
        fail("Theme.java: jangkar createCircleDrawable tidak ditemukan")
    s_theme = s_theme.replace(
        helper_anchor,
        """    /** Minigram: bentuk "lingkaran" menjadi rounded square. */
    private static RectShape minigramCircleShape(int size) {
        if (!BuildVars.MINIGRAM_SQUARE) {
            return new OvalShape();
        }
        final float r = size * 0.28f;
        return new RoundRectShape(new float[]{r, r, r, r, r, r, r, r}, null, null);
    }

""" + helper_anchor, 1)
    write(THEME, s_theme)
    print(f"[ok] Bentuk: {n} pembuat lingkaran di Theme.java -> rounded square")

    # Avatar berisi foto: ImageReceiver (deteksi lingkaran sempurna saat digambar)
    ir = JAVA / "messenger/ImageReceiver.java"
    s_ir = read(ir)
    old = "        if (!useRoundRadius) roundRadius = emptyRoundRadius;\n"
    n = s_ir.count(old)
    if n != 2:
        fail(f"ImageReceiver: kemunculan useRoundRadius = {n}, diharapkan 2")
    s_ir = s_ir.replace(old, old + "        roundRadius = minigramSquare(roundRadius, imageW, imageH);\n")
    anchor = "    protected void drawDrawable(Canvas canvas, Drawable drawable, int alpha, BitmapShader shader,"
    if anchor not in s_ir:
        fail("ImageReceiver: jangkar drawDrawable tidak ditemukan")
    s_ir = s_ir.replace(anchor, """    private final int[] minigramRadius = new int[4];

    /** Minigram: radius yang membentuk lingkaran sempurna (avatar) diubah menjadi rounded square. */
    private int[] minigramSquare(int[] r, float w, float h) {
        if (!BuildVars.MINIGRAM_SQUARE || r == null || r.length < 4 || r[0] <= 0) {
            return r;
        }
        final float m = Math.min(w, h);
        if (m <= 0 || r[0] != r[1] || r[1] != r[2] || r[2] != r[3] || r[0] * 2f < m - 1.5f) {
            return r;
        }
        final int v = Math.max(1, Math.round(m * 0.28f));
        minigramRadius[0] = minigramRadius[1] = minigramRadius[2] = minigramRadius[3] = v;
        return minigramRadius;
    }

""" + anchor, 1)
    write(ir, s_ir)
    print(f"[ok] Bentuk: ImageReceiver ({n} titik)")

    # Avatar inisial (tanpa foto): AvatarDrawable
    ad = JAVA / "ui/Components/AvatarDrawable.java"
    replace_once(
        ad,
        "                canvas.drawCircle(size / 2.0f, size / 2.0f, size / 2.0f, backgroundPaint);\n            }\n            if (rotate45Background)",
        "                if (BuildVars.MINIGRAM_SQUARE) {\n"
        "                    AndroidUtilities.rectTmp.set(0, 0, size, size);\n"
        "                    canvas.drawRoundRect(AndroidUtilities.rectTmp, size * 0.28f, size * 0.28f, backgroundPaint);\n"
        "                } else {\n"
        "                    canvas.drawCircle(size / 2.0f, size / 2.0f, size / 2.0f, backgroundPaint);\n"
        "                }\n            }\n            if (rotate45Background)",
        "Bentuk: avatar inisial")
    s_ad = read(ad)
    if "import org.telegram.messenger.BuildVars;" not in s_ad and "import org.telegram.messenger.*;" not in s_ad:
        s_ad = re.sub(r"(\nimport org\.telegram\.messenger\.)", r"\nimport org.telegram.messenger.BuildVars;\1", s_ad, count=1)
        write(ad, s_ad)
        print("[ok] import BuildVars -> AvatarDrawable.java")

# ---------------------------------------------------------------- 6. Ikon
if REPLACE_ICONS:
    import subprocess
    gen = Path(__file__).resolve().parent / "make_icons.py"
    if not gen.is_file():
        fail("minigram/make_icons.py tidak ditemukan (atau set REPLACE_ICONS = False)")
    r = subprocess.run([sys.executable, str(gen), "--apply", str(ROOT)])
    if r.returncode != 0:
        fail("make_icons.py gagal (pastikan Pillow terpasang: pip install pillow)")

# ---------------------------------------------------------------- 7. arm64 saja
if ARM64_ONLY:
    app = ROOT / "TMessagesProj_App/build.gradle"
    sub_once(
        app,
        r'(        afat \{\n            ndk \{\n                abiFilters )"armeabi-v7a", "arm64-v8a", "x86", "x86_64"',
        r'\1"arm64-v8a"', "ABI afat: arm64-v8a saja")

print("\nSelesai. Patch Minigram diterapkan.")
