"""Utility helper functions for PDF Partner."""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from pdf_partner_app.utils.config import (
    SETTINGS_FILE, RESERVED_NAMES, FONT_PATTERNS,
    BUILTIN_FONT_CODES, BUILTIN_FONT_DISPLAY, BOLD_MAP, logger
)

try:
    from fontTools.ttLib import TTFont, TTCollection
    FONTTOOLS_AVAILABLE = True
except Exception:
    TTFont = None
    TTCollection = None
    FONTTOOLS_AVAILABLE = False

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except Exception:
    TkinterDnD = None
    DND_FILES = None
    DND_AVAILABLE = False


def app_base_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent


def app_fonts_dir():
    p = app_base_dir() / "Fonts"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("Unable to create app fonts directory: %s", exc)
    return p


def windows_fonts_dir():
    return Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"


def user_fonts_dir():
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "Microsoft" / "Windows" / "Fonts" if local else None


def documents_dir():
    docs = Path.home() / "Documents"
    return docs if docs.exists() else Path.home()


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
    except Exception as exc:
        logger.warning("Failed to load settings from %s: %s", SETTINGS_FILE, exc)
        return {}


def save_settings(settings):
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to save settings to %s: %s", SETTINGS_FILE, exc)


def open_folder(path):
    try:
        os.startfile(str(path))
    except Exception:
        try:
            subprocess.Popen(["explorer", str(path)])
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Unable to open folder:\n{exc}")


def safe_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except Exception:
        return default


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]+', '_', str(name)).strip().rstrip('. ')
    if not name:
        return "Untitled"
    if name.split('.')[0].upper() in RESERVED_NAMES:
        name = "_" + name
    return name[:170]


def clean_title(path):
    return re.sub(r"\s+", " ", Path(path).stem.replace("_", " ")).strip()


def hex_to_rgb01(hex_colour):
    if not re.match(r"^#[0-9a-fA-F]{6}$", str(hex_colour)):
        hex_colour = "#000000"
    return tuple(int(hex_colour[1 + i:3 + i], 16) / 255 for i in (0, 2, 4))


def formal_font_name_from_font(font_obj):
    try:
        table = font_obj["name"]
        for name_id in [4, 6, 1]:
            values = []
            for rec in table.names:
                if rec.nameID == name_id:
                    try:
                        txt = rec.toUnicode().strip()
                        if txt and txt not in values:
                            values.append(txt)
                    except Exception:
                        pass
            if values:
                for value in values:
                    if re.search(r"[A-Za-z]", value):
                        return value
                return values[0]
    except Exception:
        pass
    return ""


def get_formal_font_name(font_path):
    p = Path(font_path)
    if not FONTTOOLS_AVAILABLE:
        return p.stem.replace("_", " ").replace("-", " ").strip()
    try:
        if p.suffix.lower() in [".ttc", ".otc"]:
            col = TTCollection(str(p), lazy=True)
            if col.fonts:
                name = formal_font_name_from_font(col.fonts[0])
                if name:
                    return name
        else:
            font = TTFont(str(p), lazy=True)
            name = formal_font_name_from_font(font)
            try:
                font.close()
            except Exception:
                pass
            if name:
                return name
    except Exception:
        pass
    return p.stem.replace("_", " ").replace("-", " ").strip()


def scan_fonts_folder(folder, label):
    results = {}
    folder = Path(folder) if folder else None
    if not folder or not folder.exists():
        return results
    for pattern in FONT_PATTERNS:
        for fp in folder.glob(pattern):
            display = f"{label}: {get_formal_font_name(fp)}"
            original, n = display, 2
            while display in results:
                display = f"{original} ({n})"
                n += 1
            results[display] = str(fp)
    return results


@lru_cache(maxsize=None)
def scan_external_fonts(include_app=True, include_windows=True, include_user=True):
    fonts = {}
    if include_app:
        fonts.update(scan_fonts_folder(app_fonts_dir(), "App Font"))
    if include_windows:
        fonts.update(scan_fonts_folder(windows_fonts_dir(), "Windows Font"))
    if include_user and user_fonts_dir():
        fonts.update(scan_fonts_folder(user_fonts_dir(), "User Font"))
    return dict(sorted(fonts.items(), key=lambda kv: kv[0].lower()))


def all_font_options(include_app=True, include_windows=True, include_user=True):
    return BUILTIN_FONT_DISPLAY + list(scan_external_fonts(include_app, include_windows, include_user).keys())


def font_for_selection(selection, include_app=True, include_windows=True, include_user=True):
    if selection in BUILTIN_FONT_CODES:
        return BUILTIN_FONT_CODES[selection], None
    return "customfont", scan_external_fonts(include_app, include_windows, include_user).get(selection)


def apply_bold(fontname, fontfile, bold):
    if not bold:
        return fontname, fontfile, False
    if fontfile:
        return fontname, fontfile, True
    return BOLD_MAP.get(fontname, fontname), None, False


def parse_pages(text, total):
    text = str(text).strip().lower()
    if not text or text == "all":
        return list(range(total))
    pages = set()
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if part == "all":
            pages.update(range(total))
        elif part == "odd":
            pages.update(i for i in range(total) if (i + 1) % 2 == 1)
        elif part == "even":
            pages.update(i for i in range(total) if (i + 1) % 2 == 0)
        elif part == "first":
            if total:
                pages.add(0)
        elif part == "last":
            if total:
                pages.add(total - 1)
        elif '-' in part:
            a, b = part.split('-', 1)
            a, b = safe_int(a, 1), safe_int(b, total)
            for n in range(max(1, a), min(total, b) + 1):
                pages.add(n - 1)
        else:
            n = safe_int(part, 0)
            if 1 <= n <= total:
                pages.add(n - 1)
    return sorted(pages)


def resolve_output_path(input_path, suffix, output_mode="Same folder", chosen_folder="", if_exists="Auto-increment"):
    p = Path(input_path)
    if output_mode == "Choose output folder" and chosen_folder:
        folder = Path(chosen_folder)
    elif output_mode == "Create Output subfolder":
        folder = p.parent / "Output"
    elif output_mode == "Create dated output folder":
        folder = p.parent / "Output" / datetime.now().strftime("%Y-%m-%d")
    else:
        folder = p.parent

    folder.mkdir(parents=True, exist_ok=True)
    clean_stem = sanitize_filename(p.stem)
    suffix = str(suffix or "")
    safe_suffix = re.sub(r'[<>:"/\\|?*]+', '_', suffix).strip()

    if not safe_suffix:
        safe_suffix = "_Edited"

    target = folder / f"{clean_stem}{safe_suffix}{p.suffix}"

    try:
        if target.resolve() == p.resolve():
            target = folder / f"{clean_stem}_Edited{p.suffix}"
    except Exception as exc:
        logger.warning("Could not compare input/output paths: %s", exc)

    if target.exists():
        if if_exists == "Overwrite":
            return target
        if if_exists == "Ask":
            from tkinter import messagebox
            if messagebox.askyesno("File Exists", f"Overwrite existing file?\n{target}"):
                return target
        base, ext, idx = folder / f"{clean_stem}{safe_suffix}", p.suffix, 1
        while True:
            candidate = Path(str(base) + f"_{idx:02d}" + ext)
            if not candidate.exists():
                return candidate
            idx += 1
    return target


def parse_drop_paths(data):
    tokens = re.findall(r"\{[^}]*\}|\S+", str(data))
    paths = [t[1:-1] if t.startswith("{") and t.endswith("}") else t for t in tokens]
    return paths
