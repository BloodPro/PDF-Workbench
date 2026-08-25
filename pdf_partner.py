r"""
PDF Partner - Modular PDF Utility Application

Run:
    python pdf_partner.py

Optional (enables drag-and-drop of files from Explorer):
    pip install tkinterdnd2

Build EXE:
    python -m PyInstaller --onefile --windowed --name PDF_Partner pdf_partner.py
Build EXE with icon:
    python -m PyInstaller --onefile --windowed --name PDF_Partner --icon icon.ico pdf_partner.py
If you installed tkinterdnd2, add it to the build:
    python -m PyInstaller --onefile --windowed --name PDF_Partner --collect-all tkinterdnd2 pdf_partner.py

UI / workflow changes in this revision
---------------------------------------
* Progressive disclosure: every "Custom ..." field and the Output Folder picker
  appear only when their trigger is selected; placement fields follow the chosen
  position (and disappear entirely for "Center", which ignores margins).
* Grouped sections (Source / Placement / Style / Output) and a collapsible
  "Output options" panel keep each screen short.
* Colour swatch opens the OS colour picker; opacity is a slider.
* Live, debounced preview - the "Refresh Preview" button is gone.
* Drag-and-drop files onto the lists (auto-enabled if tkinterdnd2 is installed,
  silently disabled otherwise - no hard dependency).
* Rotate uses the same single "Pages" field as every other module.
* "Bold" replaces "Fake Bold": real bold for built-in fonts, synthetic for
  external ones. Font-source configuration moved to a Settings dialog.
* Quality: central rolling log file, reserved-Windows-name guard, Merge defaults
  to Documents, page lists accept combinations like "first,last,3-5,odd",
  bookmark hierarchy is validated before saving, metadata auto-loads on add.

Litigation-workflow additions in this revision
-----------------------------------------------
* INDEX BUILDER: builds an editable table (Sr | Particulars | From | To) from a
  single file's top-level bookmarks, or from several files' names; you can edit
  any row, then Preview, Save as a standalone Index PDF, or Prepend it to a PDF
  (bookmarks are re-pointed and the index page is left un-numbered, so body
  numbering still starts at 1).
* Diagonal watermark option in Text / Heading (centered, 45°) for DRAFT /
  CONFIDENTIAL style stamps.
* Drag-to-reorder in Merge and the Organiser (in addition to Move Up/Down).
"""

import os
import re
import sys
import json
import subprocess
import traceback
import tempfile
import logging
import webbrowser
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

from PIL import Image, ImageTk
import fitz  # PyMuPDF

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

APP_NAME = "PDF Partner"
APP_AUTHOR = "BloodPro"
APP_REPOSITORY = "https://github.com/BloodPro/PDF-Workbench.git"
APP_DESCRIPTION = "Professional PDF Workbench for Litigation & Documentation preparation"
APP_COPYRIGHT = "© BloodPro"
APP_VERSION = "1.0.2"
SETTINGS_FILE = Path.home() / ".pdf_partner_settings.json"
LOG_FILE = Path.home() / "PDF_Partner.log"

THEME = {
    "bg": "#F8FAFC", "surface": "#FFFFFF", "sidebar": "#0F172A", "sidebar_hover": "#1E293B",
    "primary": "#2563EB", "primary_dark": "#1D4ED8", "text": "#0F172A", "muted": "#64748B",
    "border": "#E2E8F0", "success": "#059669", "warning": "#D97706", "danger": "#DC2626",
}
MM = 72 / 25.4
A4_W_MM, A4_H_MM = 210, 297

POSITIONS = ["Top Left", "Top Center", "Top Right", "Center", "Bottom Left", "Bottom Center", "Bottom Right", "Custom X/Y"]
PAGE_FORMATS = ["Page {n} of {total}", "Page {n}", "- {n} -", "{n}", "Custom"]
ROTATION_OPTIONS = ["90° clockwise", "90° counter-clockwise", "180°"]
OUTPUT_MODES = ["Same folder", "Choose output folder", "Create Output subfolder", "Create dated output folder"]
IF_EXISTS_OPTIONS = ["Auto-increment", "Overwrite", "Ask"]

MODULE_OUTPUT_SUFFIXES = {
    "text_heading": "_Heading", "page_numbering": "_Numbered", "sign_stamp": "_Signed",
    "merge": "_Merged", "index": "_Indexed", "split": "_Split", "delete": "_PagesDeleted",
    "rotate": "_Rotated", "bookmark": "_BookmarksEdited", "metadata": "_Metadata",
}

BUILTIN_FONT_DISPLAY = [
    "Built-in: Helvetica", "Built-in: Helvetica Bold", "Built-in: Helvetica Italic", "Built-in: Helvetica Bold Italic",
    "Built-in: Times Roman", "Built-in: Times Bold", "Built-in: Times Italic", "Built-in: Times Bold Italic",
    "Built-in: Courier", "Built-in: Courier Bold", "Built-in: Courier Italic", "Built-in: Courier Bold Italic",
]
BUILTIN_FONT_CODES = {
    "Built-in: Helvetica": "helv", "Built-in: Helvetica Bold": "hebo", "Built-in: Helvetica Italic": "heit", "Built-in: Helvetica Bold Italic": "hebi",
    "Built-in: Times Roman": "tiro", "Built-in: Times Bold": "tibo", "Built-in: Times Italic": "tiit", "Built-in: Times Bold Italic": "tibi",
    "Built-in: Courier": "cour", "Built-in: Courier Bold": "cobo", "Built-in: Courier Italic": "coit", "Built-in: Courier Bold Italic": "cobi",
}
# Maps each built-in code to its bold counterpart (already-bold map to themselves).
BOLD_MAP = {
    "helv": "hebo", "heit": "hebi", "tiro": "tibo", "tiit": "tibi", "cour": "cobo", "coit": "cobi",
    "hebo": "hebo", "hebi": "hebi", "tibo": "tibo", "tibi": "tibi", "cobo": "cobo", "cobi": "cobi",
}
FONT_PATTERNS = ("*.ttf", "*.otf", "*.ttc", "*.otc", "*.TTF", "*.OTF", "*.TTC", "*.OTC")
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}

logger = logging.getLogger("pdf_partner")


def setup_logging():
    try:
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
            logger.addHandler(handler)
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        logger.warning("Failed to initialize file logger: %s", exc)


def app_base_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


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
    # Cached: scanning Windows\Fonts and parsing every face is expensive. The
    # Settings dialog calls scan_external_fonts.cache_clear() to force a rescan.
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
    """Return (fontname, fontfile, fake_bold). For built-ins, switch to the bold
    code; for external fonts there is no real bold, so request a synthetic one."""
    if not bold:
        return fontname, fontfile, False
    if fontfile:
        return fontname, fontfile, True
    return BOLD_MAP.get(fontname, fontname), None, False


def choose_pdfs(parent, multiple=True, title="Select PDF file(s)"):
    opts = dict(parent=parent, title=title, initialdir=str(documents_dir()), filetypes=[("PDF files", ("*.pdf", "*.PDF")), ("All files", "*.*")])
    if multiple:
        return [f for f in filedialog.askopenfilenames(**opts) if Path(f).suffix.lower() == ".pdf"]
    f = filedialog.askopenfilename(**opts)
    return f if f and Path(f).suffix.lower() == ".pdf" else ""


def choose_image(parent):
    f = filedialog.askopenfilename(parent=parent, title="Select image", initialdir=str(Path.home() / "Pictures"), filetypes=[("Images", ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG")), ("All files", "*.*")])
    return f if f and Path(f).suffix.lower() in [".png", ".jpg", ".jpeg"] else ""


def parse_pages(text, total):
    """Accepts 'all', keywords (odd/even/first/last) and ranges, freely combined,
    e.g. 'first,last,3-5,odd'. Returns 0-based page indices."""
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
    """Resolve a safe output path for a processed PDF.

    v1.0.2 safety improvements:
    - sanitises the source stem and suffix;
    - creates output folders safely;
    - prevents accidental overwrite of the original input file;
    - auto-increments when required.
    """
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

    # Avoid saving directly over the source file when suffix is blank or unsafe.
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
        if if_exists == "Ask" and messagebox.askyesno("File Exists", f"Overwrite existing file?\n{target}"):
            return target
        base, ext, idx = folder / f"{clean_stem}{safe_suffix}", p.suffix, 1
        while True:
            candidate = Path(str(base) + f"_{idx:02d}" + ext)
            if not candidate.exists():
                return candidate
            idx += 1
    return target


def text_width(text, size, fontname="helv"):
    try:
        if fontname != "customfont":
            return fitz.get_text_length(text, fontname=fontname, fontsize=size)
    except Exception:
        pass
    return len(text) * size * 0.52


def place_box(w, h, iw, ih, pos, m_side, m_tb, cx, cy):
    """Top-left (x, y) of an iw*ih item inside a w*h container. All arguments
    share one unit (points for output, pixels for preview)."""
    if pos == "Top Left":        return m_side, m_tb
    if pos == "Top Center":      return (w - iw) / 2, m_tb
    if pos == "Top Right":       return w - m_side - iw, m_tb
    if pos == "Center":          return (w - iw) / 2, (h - ih) / 2
    if pos == "Bottom Left":     return m_side, h - m_tb - ih
    if pos == "Bottom Center":   return (w - iw) / 2, h - m_tb - ih
    if pos == "Bottom Right":    return w - m_side - iw, h - m_tb - ih
    return cx, h - cy - ih  # Custom X/Y (cx from left, cy from bottom)


def text_point(w, h, tw, size, pos, mx, my, cx, cy):
    x, y = place_box(w, h, tw, size, pos, mx * MM, my * MM, cx * MM, cy * MM)
    return fitz.Point(max(0, x), max(size, min(h, y + size)))


def image_rect(w, h, iw, ih, pos, mx, my, cx, cy):
    x, y = place_box(w, h, iw, ih, pos, mx * MM, my * MM, cx * MM, cy * MM)
    x, y = max(0, min(x, w - iw)), max(0, min(y, h - ih))
    return fitz.Rect(x, y, x + iw, y + ih)


def insert_text(page, text, pt, size, fontname, fontfile, colour, opacity, underline=False, fake_bold=False):
    kwargs = dict(fontsize=size, color=colour, overlay=True)
    try: kwargs["fill_opacity"] = opacity
    except Exception: pass
    try:
        if fontfile: page.insert_text(pt, text, fontname="customfont", fontfile=fontfile, **kwargs)
        else: page.insert_text(pt, text, fontname=fontname, **kwargs)
    except TypeError:
        kwargs.pop("fill_opacity", None)
        if fontfile: page.insert_text(pt, text, fontname="customfont", fontfile=fontfile, **kwargs)
        else: page.insert_text(pt, text, fontname=fontname, **kwargs)
    if fake_bold and fontfile:
        try: page.insert_text(fitz.Point(pt.x + 0.25, pt.y), text, fontname="customfont", fontfile=fontfile, **kwargs)
        except Exception: pass
    if underline:
        tw = text_width(text, size, fontname if not fontfile else "helv")
        sh = page.new_shape(); y = pt.y + 1.5
        sh.draw_line(fitz.Point(pt.x, y), fitz.Point(pt.x + tw, y))
        try: sh.finish(color=colour, width=max(0.5, size / 18), stroke_opacity=opacity)
        except TypeError: sh.finish(color=colour, width=max(0.5, size / 18))
        sh.commit(overlay=True)


def insert_diagonal_text(page, text, fontname, fontfile, fontsize, colour, opacity, angle=45):
    """Centered watermark text rotated by `angle` degrees across the page.
    Used for DRAFT / CONFIDENTIAL style watermarks. Vector text via TextWriter;
    falls back to plain centered text if rotation is unavailable."""
    rect = page.rect
    try:
        font = fitz.Font(fontfile=fontfile) if fontfile else fitz.Font(fontname)
    except Exception:
        try: font = fitz.Font("helv")
        except Exception: font = None
    try:
        tlen = font.text_length(text, fontsize=fontsize) if font else len(text) * fontsize * 0.5
    except Exception:
        tlen = len(text) * fontsize * 0.5
    cx, cy = rect.width / 2, rect.height / 2
    start = fitz.Point(cx - tlen / 2, cy + fontsize * 0.35)
    try:
        writer = fitz.TextWriter(rect)
        if font:
            writer.append(start, text, font=font, fontsize=fontsize)
        else:
            writer.append(start, text, fontsize=fontsize)
        morph = (fitz.Point(cx, cy), fitz.Matrix(angle))
        try:
            writer.write_text(page, color=colour, opacity=opacity, morph=morph)
        except TypeError:
            writer.write_text(page, color=colour, morph=morph)
    except Exception:
        try:
            page.insert_text(fitz.Point(cx - tlen / 2, cy), text, fontname=(fontname if not fontfile else "helv"), fontsize=fontsize, color=colour, overlay=True)
        except Exception:
            pass


def wrap_text(measure_font, fontsize, text, max_w):
    words = str(text).split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        try:
            fits = measure_font.text_length(trial, fontsize=fontsize) <= max_w
        except Exception:
            fits = len(trial) * fontsize * 0.5 <= max_w
        if fits:
            cur = trial
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def index_rows_from_pdf(path):
    """Build index rows from a single PDF's top-level bookmarks.
    Returns (rows, warning). Each row = [sr, particulars, from_page, to_page]."""
    with fitz.open(path) as doc:
        total = len(doc)
        toc = doc.get_toc()
    top = [(t, p) for lvl, t, p, *_ in toc if lvl == 1]
    if not top:
        return [[1, clean_title(path), 1, total]], ("This PDF has no bookmarks, so the index could not be built from them. "
                                                     "A single row for the whole file was added - edit it as needed.")
    rows = []
    for i, (t, p) in enumerate(top):
        nxt = top[i + 1][1] - 1 if i + 1 < len(top) else total
        rows.append([i + 1, t, p, nxt])
    return rows, ""


def index_rows_from_files(paths):
    """Build index rows from several files: particulars = file name, page ranges
    from cumulative page counts (as if the files were merged in this order)."""
    rows, start = [], 1
    for i, fp in enumerate(paths, 1):
        try:
            with fitz.open(fp) as d: n = len(d)
        except Exception:
            n = 0
        end = start + n - 1 if n else start
        rows.append([i, clean_title(fp), start, end])
        start += max(0, n)
    return rows, ""


def render_index_pdf(rows, page_w=595, page_h=842, title="INDEX"):
    """Render index rows into an in-memory fitz.Document (A4 by default).
    Columns: Sr | Particulars | From | To. Wraps long particulars and paginates."""
    doc = fitz.open()
    L, R, T, B = 50, 50, 60, 55
    col_sr, col_num, pad = 45, 55, 6
    x0 = L
    x1 = L + col_sr
    x2 = page_w - R - 2 * col_num
    x3 = page_w - R - col_num
    x4 = page_w - R
    part_w = x2 - x1 - 2 * pad
    body_size, line_h, header_size, title_size = 10, 14, 11, 16
    try:
        measure = fitz.Font("helv")
    except Exception:
        measure = None

    def measure_len(txt, size):
        try:
            return measure.text_length(txt, fontsize=size) if measure else len(txt) * size * 0.5
        except Exception:
            return len(txt) * size * 0.5

    def draw_header(pg, y):
        hh = line_h + 6
        sh = pg.new_shape()
        sh.draw_rect(fitz.Rect(x0, y, x4, y + hh))
        for xx in (x1, x2, x3):
            sh.draw_line(fitz.Point(xx, y), fitz.Point(xx, y + hh))
        sh.finish(width=0.8, color=(0, 0, 0))
        sh.commit()
        ty = y + hh - 6
        pg.insert_text(fitz.Point(x0 + pad, ty), "Sr", fontname="hebo", fontsize=header_size)
        pg.insert_text(fitz.Point(x1 + pad, ty), "Particulars", fontname="hebo", fontsize=header_size)
        pg.insert_text(fitz.Point(x2 + pad, ty), "From", fontname="hebo", fontsize=header_size)
        pg.insert_text(fitz.Point(x3 + pad, ty), "To", fontname="hebo", fontsize=header_size)
        return y + hh

    pg = doc.new_page(width=page_w, height=page_h)
    tw = measure_len(title, title_size)
    pg.insert_text(fitz.Point((page_w - tw) / 2, T), title, fontname="hebo", fontsize=title_size)
    y = draw_header(pg, T + 26)

    for sr, particulars, frm, to in rows:
        lines = wrap_text(measure, body_size, particulars, part_w) if measure else [str(particulars)]
        lines = lines or [""]
        rh = max(line_h + 6, len(lines) * line_h + 8)
        if y + rh > page_h - B:
            pg = doc.new_page(width=page_w, height=page_h)
            y = draw_header(pg, T)
        sh = pg.new_shape()
        sh.draw_rect(fitz.Rect(x0, y, x4, y + rh))
        for xx in (x1, x2, x3):
            sh.draw_line(fitz.Point(xx, y), fitz.Point(xx, y + rh))
        sh.finish(width=0.6, color=(0, 0, 0))
        sh.commit()
        srtxt = str(sr); sw = measure_len(srtxt, body_size)
        pg.insert_text(fitz.Point(x0 + (col_sr - sw) / 2, y + line_h), srtxt, fontname="helv", fontsize=body_size)
        ty = y + line_h
        for ln in lines:
            pg.insert_text(fitz.Point(x1 + pad, ty), ln, fontname="helv", fontsize=body_size); ty += line_h
        for xx, cw, val in ((x2, col_num, str(frm)), (x3, col_num, str(to))):
            vw = measure_len(val, body_size)
            pg.insert_text(fitz.Point(xx + (cw - vw) / 2, y + line_h), val, fontname="helv", fontsize=body_size)
        y += rh
    return doc


def parse_drop_paths(data):
    """tkdnd <<Drop>> data is space separated, with {braces} around paths
    containing spaces. Returns only the PDF paths."""
    tokens = re.findall(r"\{[^}]*\}|\S+", str(data))
    paths = [t[1:-1] if t.startswith("{") and t.endswith("}") else t for t in tokens]
    return paths


def preview_font_spec(selection, bold, size):
    """Best-effort Tk font (family, size, style) so the preview reflects the
    chosen font, Bold, and italic. Built-ins map to close Windows families;
    external fonts use their family name (Tk substitutes if it isn't installed)."""
    fs = max(6, int(size * 0.85))
    name = selection or ""
    low = name.lower()
    italic = ("italic" in low) or ("oblique" in low)
    is_bold = bool(bold) or ("bold" in low)
    if "courier" in low:
        family = "Courier New"
    elif "times" in low:
        family = "Times New Roman"
    elif "helvetica" in low or selection in BUILTIN_FONT_CODES:
        family = "Arial"  # Helvetica's closest Windows match
    else:
        family = name.split(":", 1)[-1].strip()
        for word in ("Bold", "Italic", "Oblique", "Regular", "Light", "Medium", "SemiBold", "Semibold", "Black", "Thin"):
            family = re.sub(rf"\b{word}\b", "", family, flags=re.I)
        family = re.sub(r"\s+", " ", family).strip() or "Segoe UI"
    style = " ".join(s for s, on in (("bold", is_bold), ("italic", italic)) if on)
    return (family, fs, style) if style else (family, fs)


class Collapsible(ttk.Frame):
    def __init__(self, parent, title, expanded=False):
        super().__init__(parent)
        self.title = title
        self._open = expanded
        self.btn = ttk.Button(self, text=self._label(), command=self.toggle, style="Toolbutton")
        self.btn.pack(fill="x")
        self.body = ttk.Frame(self, padding=(0, 4, 0, 0))
        if expanded:
            self.body.pack(fill="x")

    def _label(self):
        return ("▾  " if self._open else "▸  ") + self.title

    def toggle(self):
        self._open = not self._open
        self.btn.configure(text=self._label())
        if self._open:
            self.body.pack(fill="x")
        else:
            self.body.pack_forget()


class PDFPreview(ttk.LabelFrame):
    CANVAS_W, CANVAS_H = 360, 500

    def __init__(self, parent):
        super().__init__(parent, text="Preview", padding=8)
        self.canvas = tk.Canvas(self, width=self.CANVAS_W, height=self.CANVAS_H, bg="#f0f0f0", highlightthickness=1, highlightbackground="#999")
        self.canvas.pack()
        self.img_ref = None
        self.img_ref_overlay = None
        self.pdf_path = ""
        self.page_index = 0
        self.page_w_mm, self.page_h_mm = A4_W_MM, A4_H_MM
        nav = ttk.Frame(self); nav.pack(fill="x", pady=(6, 0))
        ttk.Button(nav, text="Prev", command=self.prev_page).pack(side="left")
        ttk.Button(nav, text="Next", command=self.next_page).pack(side="left", padx=4)
        self.page_label = ttk.Label(nav, text="Blank A4"); self.page_label.pack(side="left", padx=8)
        self.overlay_callback = None

    def set_pdf(self, pdf_path, overlay_callback=None):
        self.pdf_path = pdf_path or ""; self.page_index = 0; self.overlay_callback = overlay_callback; self.render()

    def prev_page(self):
        if self.pdf_path and self.page_index > 0:
            self.page_index -= 1; self.render()

    def next_page(self):
        if self.pdf_path:
            try:
                with fitz.open(self.pdf_path) as doc: total = len(doc)
                if self.page_index < total - 1:
                    self.page_index += 1; self.render()
            except Exception as exc:
                logger.debug("Failed to navigate to next page: %s", exc)

    def blank_page(self):
        self.canvas.delete("all")
        self.page_w_mm, self.page_h_mm = A4_W_MM, A4_H_MM
        cw, ch, margin = self.CANVAS_W, self.CANVAS_H, 18
        pw = cw - 2 * margin; ph = pw * A4_H_MM / A4_W_MM
        if ph > ch - 2 * margin:
            ph = ch - 2 * margin; pw = ph * A4_W_MM / A4_H_MM
        px, py = (cw - pw) / 2, (ch - ph) / 2
        self.canvas.create_rectangle(px, py, px + pw, py + ph, fill="white", outline="#444")
        self.page_label.configure(text="Blank A4")
        return px, py, pw, ph

    def render(self):
        self.canvas.delete("all")
        if not self.pdf_path or not Path(self.pdf_path).exists():
            px, py, pw, ph = self.blank_page()
            if self.overlay_callback: self.overlay_callback(self, px, py, pw, ph)
            return px, py, pw, ph
        try:
            with fitz.open(self.pdf_path) as doc:
                page = doc[self.page_index]
                pix = page.get_pixmap(matrix=fitz.Matrix(0.8, 0.8), alpha=False)
                # Actual page size in mm (so the preview is correct for any size).
                self.page_w_mm = (pix.width / 0.8) / MM
                self.page_h_mm = (pix.height / 0.8) / MM
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                cw, ch = self.CANVAS_W, self.CANVAS_H
                scale = min((cw - 20) / img.width, (ch - 20) / img.height)
                new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
                img = img.resize(new_size); self.img_ref = ImageTk.PhotoImage(img)
                x, y = (cw - new_size[0]) / 2, (ch - new_size[1]) / 2
                self.canvas.create_image(x, y, anchor="nw", image=self.img_ref)
                self.page_label.configure(text=f"Page {self.page_index + 1} of {len(doc)}")
            if self.overlay_callback: self.overlay_callback(self, x, y, new_size[0], new_size[1])
            return x, y, new_size[0], new_size[1]
        except Exception:
            px, py, pw, ph = self.blank_page()
            if self.overlay_callback: self.overlay_callback(self, px, py, pw, ph)
            return px, py, pw, ph

    def _overlay_box(self, px, py, pw, ph, item_w, item_h, pos, mx, my, cx, cy):
        sx, sy = pw / self.page_w_mm, ph / self.page_h_mm
        x0, y0 = place_box(pw, ph, item_w, item_h, pos, mx * sx, my * sy, cx * sx, cy * sy)
        return px + x0, py + y0

    def overlay_text(self, text, pos, mx, my, cx, cy, size, colour, underline=False, font_spec=None):
        px, py, pw, ph = self.render() or self.blank_page()
        fs = max(6, int(size * 0.85))
        spec = font_spec or ("Segoe UI", fs)
        try:
            tw = tkfont.Font(font=spec).measure(text)
        except Exception:
            tw = len(text) * fs * 0.55
        x, y = self._overlay_box(px, py, pw, ph, tw, fs, pos, mx, my, cx, cy)
        self.canvas.create_text(x, y, text=text, anchor="nw", fill=colour, font=spec)
        if underline:
            self.canvas.create_line(x, y + fs + 1, x + tw, y + fs + 1, fill=colour)

    def overlay_image(self, image_path, pos, width_mm, mx, my, cx, cy):
        px, py, pw, ph = self.render() or self.blank_page()
        if not image_path or not Path(image_path).exists(): return
        try:
            img = Image.open(image_path).convert("RGBA")
        except Exception:
            return
        iw, ih = img.size
        sw = pw * width_mm / self.page_w_mm; sh = sw * ih / iw
        img = img.resize((max(1, int(sw)), max(1, int(sh))))
        self.img_ref_overlay = ImageTk.PhotoImage(img)
        x, y = self._overlay_box(px, py, pw, ph, sw, sh, pos, mx, my, cx, cy)
        self.canvas.create_image(x, y, anchor="nw", image=self.img_ref_overlay)

    def overlay_diagonal(self, text, size, colour, angle=45, font_spec=None):
        px, py, pw, ph = self.render() or self.blank_page()
        fs = max(8, int(size * 0.9))
        spec = font_spec or ("Segoe UI", fs, "bold")
        try:
            self.canvas.create_text(px + pw / 2, py + ph / 2, text=text, fill=colour, font=spec, angle=angle)
        except Exception:
            self.canvas.create_text(px + pw / 2, py + ph / 2, text=text, fill=colour, font=spec)


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window_id, width=event.width))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        # Activate wheel scrolling whenever the pointer is anywhere over this
        # panel (including over child fields), and release it on the way out.
        self.canvas.bind("<Enter>", self._activate)
        self.canvas.bind("<Leave>", self._maybe_deactivate)

    def _activate(self, _):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _maybe_deactivate(self, _):
        # Moving onto a child fires <Leave> on the canvas; keep scrolling active
        # while the pointer is still inside the canvas's screen rectangle.
        try:
            x, y = self.canvas.winfo_pointerxy()
            cx, cy = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if cx <= x < cx + cw and cy <= y < cy + ch:
                return
        except Exception:
            pass
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        # Let lists/trees/text boxes scroll themselves; otherwise scroll the panel.
        if isinstance(event.widget, (tk.Listbox, ttk.Treeview, tk.Text)):
            return
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass


class PDFPartner:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} - {APP_AUTHOR}")
        self.root.geometry("1280x800")
        self.root.minsize(1120, 720)
        self.settings = load_settings()
        app_fonts_dir()
        self.include_app_fonts = tk.BooleanVar(value=self.settings.get("include_app_fonts", True))
        self.include_windows_fonts = tk.BooleanVar(value=self.settings.get("include_windows_fonts", True))
        self.include_user_fonts = tk.BooleanVar(value=self.settings.get("include_user_fonts", True))
        self.font_values = all_font_options(self.include_app_fonts.get(), self.include_windows_fonts.get(), self.include_user_fonts.get())
        self._num_vcmd = (self.root.register(self._is_num_partial), "%P")
        self._preview_after = None
        self.frame = None
        self.sidebar = None
        self.main_area = None
        self.active_tool = "Dashboard"
        self.configure_styles()
        self.set_icon_if_available()
        self.home()

    # ---- small infrastructure -------------------------------------------------
    def configure_styles(self):
        style = ttk.Style(self.root)
        try:
            if "vista" in style.theme_names():
                style.theme_use("vista")
        except Exception:
            pass
        try:
            self.root.configure(bg=THEME["bg"])
        except Exception:
            pass
        style.configure("App.TFrame", background=THEME["bg"])
        style.configure("Header.TLabel", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 24, "bold"))
        style.configure("Subheader.TLabel", background=THEME["bg"], foreground=THEME["muted"], font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 15, "bold"))
        style.configure("Muted.TLabel", background=THEME["bg"], foreground=THEME["muted"], font=("Segoe UI", 9))

    def open_repository(self):
        try:
            webbrowser.open(APP_REPOSITORY)
        except Exception as exc:
            messagebox.showerror("Error", "Unable to open repository: " + str(exc))

    def sidebar_button(self, text, command):
        is_active = getattr(self, "active_tool", "Dashboard") == text
        bg = THEME["sidebar_hover"] if is_active else THEME["sidebar"]
        fg = "white" if is_active else "#CBD5E1"

        def wrapped_command():
            self.active_tool = text
            command()

        btn = tk.Button(
            self.sidebar,
            text=text,
            command=wrapped_command,
            anchor="w",
            bg=bg,
            fg=fg,
            activebackground=THEME["sidebar_hover"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold" if is_active else "normal"),
            cursor="hand2",
        )
        btn.pack(fill="x")
        return btn

    def build_sidebar(self):
        tk.Label(self.sidebar, text="PDF Partner", bg=THEME["sidebar"], fg="white", font=("Segoe UI", 17, "bold"), anchor="w", padx=18, pady=16).pack(fill="x")
        tk.Label(self.sidebar, text=f"by {APP_AUTHOR}", bg=THEME["sidebar"], fg="#94A3B8", font=("Segoe UI", 9), anchor="w", padx=18, pady=0).pack(fill="x")
        self.sidebar_button("Dashboard", self.home)
        groups = [
            ("CORE PDF TOOLS", [("Merge PDFs", self.merge_module), ("Split PDF", self.split_module), ("Delete Pages", self.delete_module), ("Rotate Pages", self.rotate_module)]),
            ("WATERMARKING", [("Text Watermark", self.text_module), ("Page Numbering", self.number_module), ("Sign / Stamp", self.sign_module)]),
            ("LITIGATION TOOLS", [("Index Builder", self.index_module), ("Bookmark Editor", self.bookmark_module), ("PDF Organiser", self.pdf_organiser)]),
            ("APPLICATION", [("Metadata Editor", self.metadata_module), ("Settings", self.open_settings), ("GitHub Repository", self.open_repository)]),
        ]
        for heading, items in groups:
            tk.Label(self.sidebar, text=heading, bg=THEME["sidebar"], fg="#64748B", font=("Segoe UI", 8, "bold"), anchor="w", padx=18, pady=0).pack(fill="x")
            for label, cmd in items:
                self.sidebar_button(label, cmd)
        footer = tk.Frame(self.sidebar, bg=THEME["sidebar"])
        footer.pack(side="bottom", fill="x", pady=12)
        tk.Label(footer, text=f"{APP_NAME} v{APP_VERSION}", bg=THEME["sidebar"], fg="#94A3B8", font=("Segoe UI", 8), anchor="w", padx=18).pack(fill="x")
        tk.Label(footer, text=APP_REPOSITORY, bg=THEME["sidebar"], fg="#64748B", font=("Segoe UI", 7), anchor="w", padx=18, wraplength=190, justify="left").pack(fill="x")

    @staticmethod
    def _is_num_partial(proposed):
        return bool(re.match(r"^-?\d*\.?\d*$", proposed))

    def set_icon_if_available(self):
        icon_path = app_base_dir() / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception as exc:
                logger.debug("Unable to set window icon: %s", exc)

    def refresh_font_values(self):
        self.font_values = all_font_options(self.include_app_fonts.get(), self.include_windows_fonts.get(), self.include_user_fonts.get())
        return self.font_values

    def clear(self):
        if self._preview_after:
            try:
                self.root.after_cancel(self._preview_after)
            except Exception:
                pass
            self._preview_after = None
        if self.frame:
            self.frame.destroy()
        self.frame = ttk.Frame(self.root, style="App.TFrame")
        self.frame.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.frame, bg=THEME["sidebar"], width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.main_area = ttk.Frame(self.frame, style="App.TFrame", padding=18)
        self.main_area.pack(side="left", fill="both", expand=True)
        self.build_sidebar()

    def debounced(self, preview, fn, delay=250):
        def schedule(*_):
            if self._preview_after:
                try: self.root.after_cancel(self._preview_after)
                except Exception: pass
            def run():
                self._preview_after = None
                try:
                    if preview.winfo_exists(): fn()
                except Exception: pass
            self._preview_after = self.root.after(delay, run)
        return schedule

    def enable_drop(self, widget, on_files):
        if not DND_AVAILABLE:
            return
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", lambda e: on_files(parse_drop_paths(e.data)))
        except Exception:
            pass

    def enable_listbox_drag(self, lb, length_fn, swap_fn, refresh_fn):
        """Make a Listbox reorder by dragging an item with the mouse."""
        state = {"i": None}
        def start(e):
            state["i"] = lb.nearest(e.y)
        def motion(e):
            i = state["i"]; j = lb.nearest(e.y)
            if i is None or j < 0 or j == i or i >= length_fn() or j >= length_fn():
                return
            swap_fn(i, j); state["i"] = j; refresh_fn()
            lb.selection_clear(0, tk.END); lb.selection_set(j)
        lb.bind("<Button-1>", start, add="+")
        lb.bind("<B1-Motion>", motion, add="+")

    # ---- generic rows / groups -----------------------------------------------
    def group(self, parent, title):
        g = ttk.LabelFrame(parent, text=title, padding=8)
        g.pack(fill="x", pady=6)
        return g

    def row_entry(self, parent, label, var, width=30):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=width).pack(side="left")
        ent = ttk.Entry(row, textvariable=var); ent.pack(side="left", fill="x", expand=True)
        ent._row = row
        return ent

    def row_num(self, parent, label, var, width=30):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=width).pack(side="left")
        ent = ttk.Entry(row, textvariable=var, validate="key", validatecommand=self._num_vcmd)
        ent.pack(side="left", fill="x", expand=True)
        ent._row = row
        return ent

    def row_combo(self, parent, label, var, values, width=30):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=width).pack(side="left")
        cb = ttk.Combobox(row, textvariable=var, values=values, state="readonly"); cb.pack(side="left", fill="x", expand=True)
        cb._row = row
        return cb

    def row_file(self, parent, label, var, cmd, width=30):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=width).pack(side="left")
        ent = ttk.Entry(row, textvariable=var); ent.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=cmd).pack(side="left", padx=6)
        row._entry = ent
        return row

    @staticmethod
    def _show_row(row, show):
        if show:
            if not row.winfo_ismapped(): row.pack(fill="x", pady=3)
        else:
            row.pack_forget()

    def colour_row(self, parent, label, hex_var):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=30).pack(side="left")
        swatch = tk.Button(row, width=4, relief="groove", bg=hex_var.get() or "#000000", cursor="hand2")
        swatch.pack(side="left")
        val = ttk.Label(row, text=hex_var.get() or "#000000"); val.pack(side="left", padx=8)
        def pick():
            chosen = colorchooser.askcolor(color=hex_var.get() or "#000000", parent=self.root)
            if chosen and chosen[1]:
                hex_var.set(chosen[1]); swatch.configure(bg=chosen[1]); val.configure(text=chosen[1])
        swatch.configure(command=pick)
        def on_var(*_):
            try: swatch.configure(bg=hex_var.get()); val.configure(text=hex_var.get())
            except Exception: pass
        hex_var.trace_add("write", on_var)
        return row

    def opacity_row(self, parent, opacity_var):
        row = ttk.Frame(parent); row.pack(fill="x", pady=3)
        ttk.Label(row, text="Opacity", width=30).pack(side="left")
        val = ttk.Label(row, text=f"{int(opacity_var.get())}%", width=5)
        scale = ttk.Scale(row, from_=0, to=100, variable=opacity_var, command=lambda v: val.configure(text=f"{int(float(v))}%"))
        scale.pack(side="left", fill="x", expand=True)
        val.pack(side="left", padx=6)
        return row

    def pdf_list_selector(self, parent, pdfs, on_change=None):
        lb = tk.Listbox(parent, height=6)
        row = ttk.Frame(parent); row.pack(fill="x", pady=5)
        def refresh():
            lb.delete(0, tk.END)
            if not pdfs: lb.insert(tk.END, "No PDFs selected" + ("  -  drag files here" if DND_AVAILABLE else ""))
            else:
                for p in pdfs: lb.insert(tk.END, p)
        def changed():
            refresh()
            if on_change: on_change()
        def add_dialog():
            pdfs.extend(choose_pdfs(self.root)); changed()
        def add_dropped(paths):
            pdfs.extend(p for p in paths if Path(p).suffix.lower() == ".pdf"); changed()
        ttk.Button(row, text="Add PDF(s)", command=add_dialog).pack(side="left")
        ttk.Button(row, text="Add Folder", command=lambda: self.add_folder_pdfs(pdfs, changed)).pack(side="left", padx=6)
        ttk.Button(row, text="Clear", command=lambda: (pdfs.clear(), changed())).pack(side="left")
        lb.pack(fill="x", pady=5)
        self.enable_drop(lb, add_dropped)
        refresh()
        return lb, changed

    def add_folder_pdfs(self, pdfs, refresh):
        folder = filedialog.askdirectory(parent=self.root, title="Select folder containing PDFs")
        if folder:
            pdfs.extend(str(p) for p in sorted(Path(folder).glob("*.pdf")))
            refresh()

    def style_group(self, parent, font_var, size_var, bold_var, underline_var, hex_var, opacity_var):
        self.refresh_font_values()
        g = self.group(parent, "Style")
        row = ttk.Frame(g); row.pack(fill="x", pady=3)
        ttk.Label(row, text="Font", width=30).pack(side="left")
        cb = ttk.Combobox(row, textvariable=font_var, values=self.font_values, state="readonly"); cb.pack(side="left", fill="x", expand=True)
        if font_var.get() not in self.font_values:
            font_var.set(self.font_values[0])
        ttk.Button(row, text="Fonts…", width=7, command=self.open_settings).pack(side="left", padx=4)
        self.row_num(g, "Font Size", size_var)
        st = ttk.Frame(g); st.pack(fill="x", pady=3)
        ttk.Label(st, text="Weight / Style", width=30).pack(side="left")
        ttk.Checkbutton(st, text="Bold", variable=bold_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(st, text="Underline", variable=underline_var).pack(side="left")
        self.colour_row(g, "Colour", hex_var)
        self.opacity_row(g, opacity_var)
        return g

    def output_group(self, parent, suffix_default):
        col = Collapsible(parent, "Output options", expanded=False)
        col.pack(fill="x", pady=6)
        body = col.body
        mode = tk.StringVar(value="Same folder"); folder = tk.StringVar(value=""); suffix = tk.StringVar(value=suffix_default); exists = tk.StringVar(value="Auto-increment")
        sub = ttk.Frame(body); sub.pack(fill="x")
        self.row_combo(sub, "Output Mode", mode, OUTPUT_MODES)
        folder_row = self.row_file(sub, "Output Folder", folder, lambda: folder.set(filedialog.askdirectory(parent=self.root, title="Select output folder") or folder.get()))
        self.row_entry(body, "Output Suffix", suffix)
        self.row_combo(body, "If File Exists", exists, IF_EXISTS_OPTIONS)
        def sync(*_):
            self._show_row(folder_row, mode.get() == "Choose output folder")
        mode.trace_add("write", sync); sync()
        return mode, folder, suffix, exists

    # ---- result / batch helpers ----------------------------------------------
    def finish(self, done, errors):
        if errors:
            for e in errors:
                logger.error(e)
            messagebox.showwarning(
                "Completed with Errors",
                f"Completed: {done}\nErrors: {len(errors)}\n\nDetails were written to the log:\n{LOG_FILE}",
            )
        else:
            logger.info("Completed %s file(s) with no errors.", done)
            messagebox.showinfo("Done", f"Successfully processed {done} PDF(s).")

    def run_files(self, pdfs, mutate, out_mode, out_folder, suffix, if_exists, title="Processing"):
        """Shared per-file batch loop with a progress dialog. `mutate(doc, pdf)`
        modifies an open document in place; this handles open/save/errors/UI."""
        if not pdfs:
            messagebox.showerror("Error", "Select PDF(s)."); return
        errors, done, total = [], 0, len(pdfs)
        win = tk.Toplevel(self.root); win.title(title); win.transient(self.root); win.resizable(False, False)
        try: win.iconbitmap(str(app_base_dir() / "icon.ico"))
        except Exception: pass
        frm = ttk.Frame(win, padding=16); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=title, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        status = ttk.Label(frm, text=f"0 / {total}", foreground="#555"); status.pack(anchor="w", pady=(4, 8))
        bar = ttk.Progressbar(frm, length=380, mode="determinate", maximum=total); bar.pack()
        win.update()
        try:
            win.geometry(f"+{self.root.winfo_rootx() + 90}+{self.root.winfo_rooty() + 110}")
        except Exception:
            pass
        try:
            for i, pdf in enumerate(pdfs, 1):
                status.configure(text=f"{i} / {total}   {Path(pdf).name}")
                bar["value"] = i - 1; win.update_idletasks()
                try:
                    with fitz.open(pdf) as doc:
                        mutate(doc, pdf)
                        out = resolve_output_path(pdf, suffix, out_mode, out_folder, if_exists)
                        doc.save(out, garbage=4, deflate=True)
                    done += 1
                except Exception as e:
                    errors.append(f"{pdf}\n{e}\n{traceback.format_exc()}")
                bar["value"] = i; win.update_idletasks()
        finally:
            win.destroy()
        self.finish(done, errors)

    # ---- home -----------------------------------------------------------------
    def home(self):
        self.active_tool = "Dashboard"
        self.clear()
        f = self.main_area
        header = ttk.Frame(f, style="App.TFrame")
        header.pack(fill="x", pady=0)
        left_head = ttk.Frame(header, style="App.TFrame")
        left_head.pack(side="left", fill="x", expand=True)
        ttk.Label(left_head, text="PDF Partner", style="Header.TLabel").pack(anchor="w")
        ttk.Label(left_head, text="Professional PDF Workbench for Litigation & Documentation preparation", style="Subheader.TLabel").pack(anchor="w", pady=(2, 0))
        right_head = ttk.Frame(header, style="App.TFrame")
        right_head.pack(side="right")
        ttk.Button(right_head, text="GitHub Repository", command=self.open_repository).pack(side="right", padx=8)
        ttk.Button(right_head, text="Settings", command=self.open_settings).pack(side="right")
        ttk.Label(f, text=f"Developer: {APP_AUTHOR}   |   Repository: {APP_REPOSITORY}", style="Muted.TLabel").pack(anchor="w", pady=0)
        ft = "Available" if FONTTOOLS_AVAILABLE else "Not installed"
        dnd = "Enabled" if DND_AVAILABLE else "Disabled"
        ttk.Label(f, text=f"FontTools: {ft}   |   Drag-and-drop: {dnd}", style="Muted.TLabel").pack(anchor="w", pady=(0, 16))
        dashboard = ScrollableFrame(f)
        dashboard.pack(fill="both", expand=True)
        grid = dashboard.inner
        self.dashboard_stats(grid)
        self.dashboard_section(grid, "Core PDF Tools", [("Merge", "Combine PDFs in order and create bookmarks from file names.", self.merge_module), ("Split", "Split PDFs by bookmarks, fixed page count, or custom ranges.", self.split_module), ("Delete", "Delete selected pages or page ranges safely.", self.delete_module), ("Rotate", "Rotate selected, odd, even, first, last, or all pages.", self.rotate_module)])
        self.dashboard_section(grid, "Watermarking & Stamping", [("Text Watermark", "Add file names, headings, DRAFT, CONFIDENTIAL, or custom text.", self.text_module), ("Page Numbering", "Apply professional page numbers with formatting and placement controls.", self.number_module), ("Sign / Stamp", "Apply signature, seal, or stamp images with live preview.", self.sign_module)])
        self.dashboard_section(grid, "Litigation Tools", [("Index Builder", "Build an editable index from bookmarks or selected files.", self.index_module), ("Bookmark Editor", "View, add, edit, delete, and validate PDF bookmarks.", self.bookmark_module), ("PDF Organiser", "Arrange PDFs, edit display names, and rename files on disk.", self.pdf_organiser)])
        self.dashboard_section(grid, "Document Properties", [("Metadata Editor", "Read, edit, clear, and batch-apply PDF metadata.", self.metadata_module)])

    def dashboard_stats(self, parent):
        wrap = ttk.Frame(parent, style="App.TFrame")
        wrap.pack(fill="x", pady=0)
        stats = [("Files Processed", "Ready", THEME["primary"]), ("Indexes Created", "Index Builder", THEME["success"]), ("Watermarks", "Text / Page / Stamp", THEME["warning"]), ("Batch Tools", "Available", THEME["danger"])]
        for i, (title, value, colour) in enumerate(stats):
            card = tk.Frame(wrap, bg=THEME["surface"], highlightbackground=THEME["border"], highlightthickness=1, bd=0, padx=16, pady=12)
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 8))
            tk.Label(card, text=title, bg=THEME["surface"], fg=THEME["muted"], font=("Segoe UI", 9), anchor="w").pack(anchor="w")
            tk.Label(card, text=value, bg=THEME["surface"], fg=colour, font=("Segoe UI", 15, "bold"), anchor="w").pack(anchor="w", pady=(4, 0))
            wrap.columnconfigure(i, weight=1)

    def dashboard_section(self, parent, title, items):
        section = ttk.Frame(parent, style="App.TFrame")
        section.pack(fill="x", pady=0)
        ttk.Label(section, text=title, style="Section.TLabel").pack(anchor="w", pady=0)
        cards = ttk.Frame(section, style="App.TFrame")
        cards.pack(fill="x")
        for i, (name, desc, cmd) in enumerate(items):
            card = self.dashboard_card(cards, name, desc, cmd)
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=(0 if i % 4 == 0 else 8, 8), pady=4)
            cards.columnconfigure(i % 4, weight=1)

    def dashboard_card(self, parent, title, desc, command):
        card = tk.Frame(parent, bg=THEME["surface"], highlightbackground=THEME["border"], highlightthickness=1, bd=0, padx=14, pady=12, cursor="hand2")
        tk.Label(card, text=title, bg=THEME["surface"], fg=THEME["text"], font=("Segoe UI", 13, "bold"), anchor="w").pack(anchor="w")
        tk.Label(card, text=desc, bg=THEME["surface"], fg=THEME["muted"], font=("Segoe UI", 9), wraplength=240, justify="left", anchor="w").pack(anchor="w", pady=0, fill="x")
        btn = tk.Button(card, text="Open", command=command, bg=THEME["primary"], fg="white", activebackground=THEME["primary_dark"], activeforeground="white", relief="flat", bd=0, padx=12, pady=7, font=("Segoe UI", 9, "bold"), cursor="hand2")
        btn.pack(anchor="e")
        def click(_event):
            command()
        card.bind("<Button-1>", click)
        for child in card.winfo_children():
            if child is not btn:
                child.bind("<Button-1>", click)
        return card

    def header(self, title, subtitle=""):
        active_map = {
            "PDF Organiser": "PDF Organiser",
            "Text Watermark / Heading": "Text Watermark",
            "Page Numbering": "Page Numbering",
            "Sign / Stamp": "Sign / Stamp",
            "Merge PDFs": "Merge PDFs",
            "Index Builder": "Index Builder",
            "Split PDF": "Split PDF",
            "Delete Pages": "Delete Pages",
            "Rotate Pages": "Rotate Pages",
            "Bookmark Editor": "Bookmark Editor",
            "Metadata Editor": "Metadata Editor",
        }
        self.active_tool = active_map.get(title, title)
        self.clear()
        top = ttk.Frame(self.main_area, style="App.TFrame")
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text=title, style="Header.TLabel").pack(side="left")
        ttk.Button(top, text="Dashboard", command=self.home).pack(side="right")
        if subtitle:
            ttk.Label(self.main_area, text=subtitle, style="Subheader.TLabel").pack(anchor="w", pady=(0, 12))
        return self.main_area

    def scroll_body(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        return scroll.inner

    # ---- settings -------------------------------------------------------------
    def open_settings(self):
        win = tk.Toplevel(self.root); win.title("Settings"); win.transient(self.root); win.resizable(False, False)
        try: win.iconbitmap(str(app_base_dir() / "icon.ico"))
        except Exception: pass
        frm = ttk.Frame(win, padding=18); frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Font sources", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=0)
        ttk.Checkbutton(frm, text="App Fonts folder", variable=self.include_app_fonts).pack(anchor="w")
        ttk.Checkbutton(frm, text="Windows fonts", variable=self.include_windows_fonts).pack(anchor="w")
        ttk.Checkbutton(frm, text="User fonts", variable=self.include_user_fonts).pack(anchor="w")
        ttk.Label(frm, text="Changes apply when you open (or re-open) a module.", foreground="#777").pack(anchor="w", pady=(6, 0))
        btns = ttk.Frame(frm); btns.pack(fill="x", pady=(14, 0))
        def refresh():
            scan_external_fonts.cache_clear()
            vals = self.refresh_font_values()
            messagebox.showinfo("Fonts", f"{len(vals)} fonts available.", parent=win)
        def persist():
            self.settings.update({
                "include_app_fonts": self.include_app_fonts.get(),
                "include_windows_fonts": self.include_windows_fonts.get(),
                "include_user_fonts": self.include_user_fonts.get(),
            })
            save_settings(self.settings)
        ttk.Button(btns, text="Refresh fonts", command=refresh).pack(side="left")
        ttk.Button(btns, text="Open App Fonts folder", command=lambda: open_folder(app_fonts_dir())).pack(side="left", padx=6)
        ttk.Button(btns, text="Save & Close", command=lambda: (persist(), scan_external_fonts.cache_clear(), self.refresh_font_values(), win.destroy())).pack(side="right")

    # ---- PDF Organiser --------------------------------------------------------
    def pdf_organiser(self):
        f = self.header("PDF Organiser", "Arrange PDFs, edit display names, and optionally rename files on disk.")
        body = self.scroll_body(f)
        pdfs, display_names = [], []
        lb = tk.Listbox(body, height=14); lb.pack(fill="both", expand=True, pady=6)
        def refresh():
            lb.delete(0, tk.END)
            if not pdfs: lb.insert(tk.END, "No PDFs selected" + ("  -  drag files here" if DND_AVAILABLE else ""))
            for p, d in zip(pdfs, display_names): lb.insert(tk.END, f"{d}    |    {p}")
        def add_paths(paths):
            for x in paths:
                if Path(x).suffix.lower() == ".pdf":
                    pdfs.append(x); display_names.append(Path(x).stem)
            refresh()
        def add_files():
            add_paths(choose_pdfs(self.root))
        def add_folder():
            folder = filedialog.askdirectory(parent=self.root)
            if folder:
                add_paths([str(p) for p in sorted(Path(folder).glob("*.pdf"))])
        def move(delta):
            sel = lb.curselection()
            if sel and sel[0] < len(pdfs):
                i, j = sel[0], sel[0] + delta
                if 0 <= j < len(pdfs):
                    pdfs[i], pdfs[j] = pdfs[j], pdfs[i]; display_names[i], display_names[j] = display_names[j], display_names[i]; refresh(); lb.selection_set(j)
        def edit_name():
            sel = lb.curselection()
            if sel and sel[0] < len(pdfs):
                i = sel[0]
                new = simpledialog.askstring("Edit Display Name", "Enter display name:", initialvalue=display_names[i], parent=self.root)
                if new: display_names[i] = sanitize_filename(new); refresh()
        def title_case():
            for i, name in enumerate(display_names): display_names[i] = name.replace("_", " ").replace("-", " ").title()
            refresh()
        def add_prefixes():
            for i, name in enumerate(display_names, 1): display_names[i - 1] = f"{i:02d} - {name}"
            refresh()
        def remove_prefixes():
            for i, name in enumerate(display_names): display_names[i] = re.sub(r"^\d+\s*-\s*", "", name).strip()
            refresh()
        def rename_on_disk():
            if not pdfs: return
            if not messagebox.askyesno("Confirm Rename", "This will rename actual PDF files on disk. Continue?"): return
            errors, done = [], 0
            for i, old in enumerate(list(pdfs)):
                try:
                    p = Path(old); newp = p.with_name(sanitize_filename(display_names[i]) + p.suffix)
                    if newp.exists() and newp != p: raise FileExistsError(f"Target exists: {newp}")
                    p.rename(newp); pdfs[i] = str(newp); done += 1
                except Exception as e:
                    errors.append(f"{old}\n{e}")
            refresh(); self.finish(done, errors)
        lb.bind("<Double-Button-1>", lambda e: edit_name())
        self.enable_drop(lb, add_paths)
        def swap(i, j):
            pdfs[i], pdfs[j] = pdfs[j], pdfs[i]; display_names[i], display_names[j] = display_names[j], display_names[i]
        self.enable_listbox_drag(lb, lambda: len(pdfs), swap, refresh)
        row = ttk.Frame(body); row.pack(fill="x", pady=5)
        for text, cmd in [("Add PDFs", add_files), ("Add Folder", add_folder), ("Move Up", lambda: move(-1)), ("Move Down", lambda: move(1)), ("Edit Name", edit_name), ("Title Case", title_case), ("Add Prefixes", add_prefixes), ("Remove Prefixes", remove_prefixes), ("Rename Files", rename_on_disk)]:
            ttk.Button(row, text=text, command=cmd).pack(side="left", padx=3)
        refresh()

    # ---- Text / Page numbering (shared) --------------------------------------
    def text_module(self):
        self._text_overlay("heading")

    def number_module(self):
        self._text_overlay("number")

    def _text_overlay(self, kind):
        is_num = (kind == "number")
        title = "Page Numbering" if is_num else "Text Watermark / Heading"
        subtitle = "Add page numbers to selected pages - the preview updates as you type." if is_num else "Add text to selected pages - the preview updates as you type."
        f = self.header(title, subtitle)
        main = ttk.Frame(f); main.pack(fill="both", expand=True)
        left_scroll = ScrollableFrame(main); left_scroll.pack(side="left", fill="both", expand=True, padx=(0, 12)); left = left_scroll.inner
        preview = PDFPreview(main); preview.pack(side="right", fill="y")

        default_size = "9" if is_num else "10"
        pos = tk.StringVar(value="Bottom Center" if is_num else "Top Center"); pages = tk.StringVar(value="all")
        mx = tk.StringVar(value="8"); my = tk.StringVar(value="8"); cx = tk.StringVar(value="10"); cy = tk.StringVar(value="10")
        font = tk.StringVar(value=self.font_values[0]); size = tk.StringVar(value=default_size)
        bold = tk.BooleanVar(); underline = tk.BooleanVar(); diagonal = tk.BooleanVar(); hexc = tk.StringVar(value="#000000"); opacity = tk.DoubleVar(value=100.0)
        fmt = tk.StringVar(value=PAGE_FORMATS[0]); cfmt = tk.StringVar(value=PAGE_FORMATS[0]); startn = tk.StringVar(value="1")
        src = tk.StringVar(value="File name without extension"); custom = tk.StringVar()

        sched = self.debounced(preview, lambda: refresh_preview())
        pdfs = []

        # Source -------------------------------------------------------------
        src_grp = self.group(left, "Source")
        self.pdf_list_selector(src_grp, pdfs, on_change=lambda: (update_apply(), sched()))
        if is_num:
            sub = ttk.Frame(src_grp); sub.pack(fill="x")
            self.row_combo(sub, "Format", fmt, PAGE_FORMATS)
            cfmt_row = self.row_entry(sub, "Custom Format  ({n} {total} {page})", cfmt)
            self.row_num(src_grp, "Start Number", startn)
            def sync_src(*_): self._show_row(cfmt_row._row, fmt.get() == "Custom")
            fmt.trace_add("write", sync_src); sync_src()
        else:
            sub = ttk.Frame(src_grp); sub.pack(fill="x")
            self.row_combo(sub, "Text Source", src, ["File name without extension", "Custom text"])
            custom_row = self.row_entry(sub, "Custom Text", custom)
            def sync_src(*_): self._show_row(custom_row._row, src.get().startswith("Custom"))
            src.trace_add("write", sync_src); sync_src()

        # Placement ----------------------------------------------------------
        place_grp = self.group(left, "Placement")
        self.row_combo(place_grp, "Position", pos, POSITIONS)
        self.row_entry(place_grp, "Pages", pages)
        detail = ttk.Frame(place_grp); detail.pack(fill="x")
        def rebuild_placement(*_):
            for w in detail.winfo_children(): w.destroy()
            p = pos.get()
            if p == "Custom X/Y":
                self.row_num(detail, "Custom X mm", cx); self.row_num(detail, "Custom Y mm", cy)
            elif p == "Center":
                ttk.Label(detail, text="Centered - margins not used.", foreground="#777").pack(anchor="w", padx=2, pady=2)
            else:
                self.row_num(detail, "Side Margin mm", mx); self.row_num(detail, "Top/Bottom Margin mm", my)
        pos.trace_add("write", rebuild_placement); rebuild_placement()
        diag_row = ttk.Frame(place_grp); diag_row.pack(fill="x", pady=(2, 0))
        ttk.Label(diag_row, text="", width=30).pack(side="left")
        ttk.Checkbutton(diag_row, text="Diagonal watermark (centered, 45° - ignores position/margins)", variable=diagonal).pack(side="left")

        # Style + Output -----------------------------------------------------
        self.style_group(left, font, size, bold, underline, hexc, opacity)
        out_mode, out_folder, suffix, if_exists = self.output_group(left, MODULE_OUTPUT_SUFFIXES["page_numbering"] if is_num else MODULE_OUTPUT_SUFFIXES["text_heading"])

        def fmt_string():
            return cfmt.get() if fmt.get() == "Custom" else fmt.get()

        def text_for(pdf, idx, total, page_no):
            if is_num:
                n = safe_int(startn.get(), 1) + idx
                return fmt_string().replace("{n}", str(n)).replace("{total}", str(total)).replace("{page}", str(page_no + 1))
            if pdf and src.get().startswith("File"):
                return clean_title(pdf)
            return custom.get() or "Sample Heading Preview"

        def preview_text():
            if is_num:
                return fmt_string().replace("{n}", "1").replace("{total}", "10").replace("{page}", "1")
            return text_for(pdfs[0] if pdfs else "", 0, 1, 0)

        def refresh_preview():
            preview.set_pdf(pdfs[0] if pdfs else "")
            sz = safe_float(size.get(), float(default_size))
            spec = preview_font_spec(font.get(), bold.get(), sz)
            if diagonal.get():
                preview.overlay_diagonal(preview_text(), sz, hexc.get(), font_spec=spec)
            else:
                preview.overlay_text(preview_text(), pos.get(), safe_float(mx.get(), 8), safe_float(my.get(), 8), safe_float(cx.get(), 10), safe_float(cy.get(), 10), sz, hexc.get(), underline.get(), font_spec=spec)

        def run():
            if not is_num and not src.get().startswith("File") and not custom.get().strip():
                messagebox.showerror("Error", "Enter the custom text to apply."); return
            sz = safe_float(size.get(), float(default_size))
            fontname, fontfile = font_for_selection(font.get(), self.include_app_fonts.get(), self.include_windows_fonts.get(), self.include_user_fonts.get())
            fontname, fontfile, fake = apply_bold(fontname, fontfile, bold.get())
            col = hex_to_rgb01(hexc.get()); opa = max(0.0, min(100.0, safe_float(opacity.get(), 100))) / 100
            m = (safe_float(mx.get(), 8), safe_float(my.get(), 8), safe_float(cx.get(), 10), safe_float(cy.get(), 10))
            pos_v, pages_v, ul, diag = pos.get(), pages.get(), underline.get(), diagonal.get()
            def mutate(doc, pdf):
                selected = parse_pages(pages_v, len(doc)); total = len(selected)
                for idx, pno in enumerate(selected):
                    page = doc[pno]
                    text = text_for(pdf, idx, total, pno)
                    if diag:
                        insert_diagonal_text(page, text, fontname, fontfile, sz, col, opa)
                    else:
                        tw = text_width(text, sz, fontname)
                        pt = text_point(page.rect.width, page.rect.height, tw, sz, pos_v, *m)
                        insert_text(page, text, pt, sz, fontname, fontfile, col, opa, ul, fake)
            self.run_files(pdfs, mutate, out_mode.get(), out_folder.get(), suffix.get(), if_exists.get(), title)

        # Action + live wiring ----------------------------------------------
        action = ttk.Frame(left); action.pack(fill="x", pady=10)
        apply_btn = ttk.Button(action, text="Add Page Numbers" if is_num else "Apply Text", command=run)
        apply_btn.pack(side="right")
        def update_apply():
            apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()
        for v in (pos, pages, mx, my, cx, cy, font, size, bold, underline, diagonal, hexc, opacity, fmt, cfmt, startn, src, custom):
            v.trace_add("write", sched)
        refresh_preview()

    # ---- Sign / Stamp ---------------------------------------------------------
    def sign_module(self):
        f = self.header("Sign / Stamp", "Apply one signature/seal image - the preview updates as you type.")
        main = ttk.Frame(f); main.pack(fill="both", expand=True)
        left_scroll = ScrollableFrame(main); left_scroll.pack(side="left", fill="both", expand=True, padx=(0, 12)); left = left_scroll.inner
        preview = PDFPreview(main); preview.pack(side="right")

        img = tk.StringVar(value=self.settings.get("last_image", "")); pos = tk.StringVar(value="Bottom Right"); width = tk.StringVar(value="27"); pages = tk.StringVar(value="all"); mx = tk.StringVar(value="4"); my = tk.StringVar(value="3"); cx = tk.StringVar(value="10"); cy = tk.StringVar(value="10")
        sched = self.debounced(preview, lambda: refresh_preview())
        pdfs = []

        src_grp = self.group(left, "Source")
        self.pdf_list_selector(src_grp, pdfs, on_change=lambda: (update_apply(), sched()))
        img_row = self.row_file(src_grp, "Image", img, lambda: (img.set(choose_image(self.root) or img.get()), self.settings.update({"last_image": img.get()}), save_settings(self.settings)))
        self.enable_drop(img_row._entry, lambda paths: img.set(next((p for p in paths if Path(p).suffix.lower() in (".png", ".jpg", ".jpeg")), img.get())))

        place_grp = self.group(left, "Placement")
        self.row_combo(place_grp, "Position", pos, POSITIONS)
        self.row_num(place_grp, "Width mm", width)
        self.row_entry(place_grp, "Pages", pages)
        detail = ttk.Frame(place_grp); detail.pack(fill="x")
        def rebuild_placement(*_):
            for w in detail.winfo_children(): w.destroy()
            p = pos.get()
            if p == "Custom X/Y":
                self.row_num(detail, "Custom X mm", cx); self.row_num(detail, "Custom Y mm", cy)
            elif p == "Center":
                ttk.Label(detail, text="Centered - margins not used.", foreground="#777").pack(anchor="w", padx=2, pady=2)
            else:
                self.row_num(detail, "Side Margin mm", mx); self.row_num(detail, "Top/Bottom Margin mm", my)
        pos.trace_add("write", rebuild_placement); rebuild_placement()

        out_mode, out_folder, suffix, if_exists = self.output_group(left, MODULE_OUTPUT_SUFFIXES["sign_stamp"])

        def refresh_preview():
            preview.set_pdf(pdfs[0] if pdfs else "")
            preview.overlay_image(img.get(), pos.get(), safe_float(width.get(), 27), safe_float(mx.get(), 4), safe_float(my.get(), 3), safe_float(cx.get(), 10), safe_float(cy.get(), 10))

        def run():
            if not pdfs or not img.get():
                messagebox.showerror("Error", "Select PDF(s) and an image."); return
            try:
                with Image.open(img.get()) as im: ratio = im.size[1] / im.size[0]
            except Exception as e:
                messagebox.showerror("Error", f"Unable to read image:\n{e}"); return
            iw = safe_float(width.get(), 27) * MM; ih = iw * ratio
            m = (safe_float(mx.get(), 4), safe_float(my.get(), 3), safe_float(cx.get(), 10), safe_float(cy.get(), 10))
            pos_v, pages_v, image_path = pos.get(), pages.get(), img.get()
            def mutate(doc, pdf):
                toc = doc.get_toc(simple=False); meta = doc.metadata
                for pno in parse_pages(pages_v, len(doc)):
                    page = doc[pno]
                    rect = image_rect(page.rect.width, page.rect.height, iw, ih, pos_v, *m)
                    page.insert_image(rect, filename=image_path, overlay=True)
                if toc: doc.set_toc(toc)
                if meta: doc.set_metadata(meta)
            self.run_files(pdfs, mutate, out_mode.get(), out_folder.get(), suffix.get(), if_exists.get(), "Applying Sign / Stamp")

        action = ttk.Frame(left); action.pack(fill="x", pady=10)
        apply_btn = ttk.Button(action, text="Apply Sign / Stamp", command=run); apply_btn.pack(side="right")
        def update_apply():
            apply_btn.configure(state=("normal" if (pdfs and img.get()) else "disabled"))
        update_apply()
        for v in (img, pos, width, pages, mx, my, cx, cy):
            v.trace_add("write", sched)
        img.trace_add("write", lambda *a: update_apply())
        refresh_preview()

    # ---- Merge ----------------------------------------------------------------
    def merge_module(self):
        f = self.header("Merge PDFs", "Combine PDFs in order; optionally bookmark each by file name.")
        body = self.scroll_body(f)
        pdfs = []; lb, refresh = self.pdf_list_selector(body, pdfs); out = tk.StringVar(value=str(documents_dir() / "Merged_Output.pdf")); bookmarks = tk.BooleanVar(value=True)
        row = ttk.Frame(body); row.pack(fill="x", pady=5)
        def move(delta):
            sel = lb.curselection()
            if sel and sel[0] < len(pdfs):
                i = sel[0]; j = i + delta
                if 0 <= j < len(pdfs): pdfs[i], pdfs[j] = pdfs[j], pdfs[i]; refresh(); lb.selection_set(j)
        ttk.Button(row, text="Move Up", command=lambda: move(-1)).pack(side="left"); ttk.Button(row, text="Move Down", command=lambda: move(1)).pack(side="left", padx=6)
        ttk.Label(row, text="(or drag items to reorder)", foreground="#777").pack(side="left", padx=8)
        def swap(i, j): pdfs[i], pdfs[j] = pdfs[j], pdfs[i]
        self.enable_listbox_drag(lb, lambda: len(pdfs), swap, refresh)
        ttk.Checkbutton(body, text="Create bookmarks from file names", variable=bookmarks).pack(anchor="w", pady=4)
        self.row_file(body, "Output PDF", out, lambda: out.set(filedialog.asksaveasfilename(parent=self.root, defaultextension=".pdf", initialdir=str(documents_dir()), filetypes=[("PDF", "*.pdf")]) or out.get()))
        def run():
            if not pdfs or not out.get(): messagebox.showerror("Error", "Select PDFs and an output file."); return
            try:
                with fitz.open() as doc:
                    toc = []
                    for pdf in pdfs:
                        with fitz.open(pdf) as src: start = len(doc); doc.insert_pdf(src)
                        if bookmarks.get(): toc.append([1, clean_title(pdf), start + 1])
                    if toc: doc.set_toc(toc)
                    doc.save(out.get(), garbage=4, deflate=True)
                messagebox.showinfo("Done", f"Merged PDF created:\n{out.get()}")
            except Exception as e:
                logger.error("Merge failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        ttk.Button(body, text="Merge PDFs", command=run).pack(anchor="e", pady=12)

    # ---- Index Builder --------------------------------------------------------
    def index_module(self):
        f = self.header("Index Builder", "Build an editable index from bookmarks (single file) or file names (multiple files), then save it as a PDF page.")
        main = ttk.Frame(f); main.pack(fill="both", expand=True)
        left_scroll = ScrollableFrame(main); left_scroll.pack(side="left", fill="both", expand=True, padx=(0, 12)); left = left_scroll.inner
        preview = PDFPreview(main); preview.pack(side="right", fill="y")
        pdfs = []; rows = []
        title = tk.StringVar(value="INDEX")
        tmp_path = Path(tempfile.gettempdir()) / "pdf_partner_index_preview.pdf"

        src = self.group(left, "Source")
        self.pdf_list_selector(src, pdfs)
        ttk.Label(src, text="Add ONE file with bookmarks, or MULTIPLE files (rows come from file names).", foreground="#777").pack(anchor="w", padx=2, pady=(2, 0))

        cfg = self.group(left, "Index page")
        self.row_entry(cfg, "Heading", title)

        tbl = self.group(left, "Index rows  (edit in place)")
        tree = ttk.Treeview(tbl, columns=("sr", "particulars", "from", "to"), show="headings", height=12)
        for col, w, anchor, head in [("sr", 50, "center", "Sr"), ("particulars", 430, "w", "Particulars"), ("from", 60, "center", "From"), ("to", 60, "center", "To")]:
            tree.heading(col, text=head); tree.column(col, width=w, anchor=anchor)
        tree.pack(fill="both", expand=True, pady=4)

        def renumber():
            for i, r in enumerate(rows, 1): r[0] = i
        def refresh_tree():
            tree.delete(*tree.get_children())
            for i, r in enumerate(rows): tree.insert("", "end", iid=str(i), values=(r[0], r[1], r[2], r[3]))
        def build():
            if not pdfs:
                messagebox.showerror("Error", "Add file(s) first."); return
            rows.clear()
            if len(pdfs) == 1:
                new_rows, warn = index_rows_from_pdf(pdfs[0])
            else:
                new_rows, warn = index_rows_from_files(pdfs)
            if warn:
                messagebox.showwarning("Index", warn)
            rows.extend([list(r) for r in new_rows]); renumber(); refresh_tree()
        edit_state = {"entry": None}
        def cancel_edit():
            if edit_state["entry"] is not None:
                try: edit_state["entry"].destroy()
                except Exception: pass
                edit_state["entry"] = None
        def begin_edit(event):
            cancel_edit()
            if tree.identify("region", event.x, event.y) != "cell":
                return
            rowid = tree.identify_row(event.y); col = tree.identify_column(event.x)
            if not rowid or not col:
                return
            ci = int(col[1:]) - 1            # 0=Sr, 1=Particulars, 2=From, 3=To
            if ci == 0:
                return                       # Sr is auto-numbered, not editable
            try:
                bx, by, bw, bh = tree.bbox(rowid, col)
            except Exception:
                return
            idx = int(rowid)
            ent = ttk.Entry(tree)
            ent.place(x=bx, y=by, width=bw, height=bh)
            ent.insert(0, str(rows[idx][ci])); ent.focus_set(); ent.select_range(0, tk.END)
            edit_state["entry"] = ent
            def commit(_=None):
                val = ent.get()
                if ci in (2, 3):
                    rows[idx][ci] = safe_int(val, rows[idx][ci])
                else:
                    rows[idx][ci] = val
                cancel_edit(); refresh_tree()
                try: tree.selection_set(rowid)
                except Exception: pass
            ent.bind("<Return>", commit)
            ent.bind("<KP_Enter>", commit)
            ent.bind("<FocusOut>", commit)
            ent.bind("<Escape>", lambda e: cancel_edit())
        def add_row():
            rows.append([len(rows) + 1, "New Entry", 1, 1]); renumber(); refresh_tree()
        def delete_row():
            cancel_edit()
            for it in reversed(tree.selection()): rows.pop(int(it))
            renumber(); refresh_tree()
        def move(d):
            cancel_edit()
            sel = tree.selection()
            if not sel: return
            i = int(sel[0]); j = i + d
            if 0 <= j < len(rows):
                rows[i], rows[j] = rows[j], rows[i]; renumber(); refresh_tree(); tree.selection_set(str(j))
        tree.bind("<Double-Button-1>", begin_edit)
        ttk.Label(tbl, text="Double-click a Particulars / From / To cell to edit it right here.", foreground="#777").pack(anchor="w", padx=2)
        btns = ttk.Frame(tbl); btns.pack(fill="x", pady=4)
        for t, c in [("Build from file(s)", build), ("Add", add_row), ("Delete", delete_row), ("Move Up", lambda: move(-1)), ("Move Down", lambda: move(1))]:
            ttk.Button(btns, text=t, command=c).pack(side="left", padx=3)

        def do_preview():
            if not rows:
                messagebox.showinfo("Index", "Build or add rows first."); return
            try:
                doc = render_index_pdf(rows, 595, 842, title.get()); doc.save(str(tmp_path)); doc.close()
                preview.set_pdf(str(tmp_path))
            except Exception as e:
                logger.error("Index preview failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        def save_pdf():
            if not rows:
                messagebox.showinfo("Index", "Build or add rows first."); return
            out = filedialog.asksaveasfilename(parent=self.root, defaultextension=".pdf", initialdir=str(documents_dir()), initialfile="Index.pdf", filetypes=[("PDF", "*.pdf")])
            if not out: return
            try:
                doc = render_index_pdf(rows, 595, 842, title.get()); doc.save(out, garbage=4, deflate=True); doc.close()
                messagebox.showinfo("Done", f"Index saved:\n{out}")
            except Exception as e:
                logger.error("Index save failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        def prepend_pdf():
            if not rows:
                messagebox.showinfo("Index", "Build or add rows first."); return
            target = choose_pdfs(self.root, False, "Select the PDF to place the index in front of")
            if not target: return
            try:
                with fitz.open(target) as tdoc:
                    pw, ph = tdoc[0].rect.width, tdoc[0].rect.height
                    old_toc = tdoc.get_toc()
                    idx = render_index_pdf(rows, pw, ph, title.get())
                    k = len(idx)
                    tdoc.insert_pdf(idx, start_at=0); idx.close()
                    new_toc = [[1, "Index", 1]] + [[lvl, t, p + k] for lvl, t, p in old_toc]
                    try: tdoc.set_toc(new_toc)
                    except Exception: pass
                    out = resolve_output_path(target, "_Indexed", "Same folder", "", "Auto-increment")
                    tdoc.save(out, garbage=4, deflate=True)
                messagebox.showinfo("Done", f"Index prepended (the index page is left un-numbered):\n{out}")
            except Exception as e:
                logger.error("Index prepend failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        out_row = ttk.Frame(left); out_row.pack(fill="x", pady=10)
        ttk.Button(out_row, text="Preview Index", command=do_preview).pack(side="left")
        ttk.Button(out_row, text="Save Index PDF", command=save_pdf).pack(side="left", padx=6)
        ttk.Button(out_row, text="Prepend to PDF…", command=prepend_pdf).pack(side="right")

    # ---- Split ----------------------------------------------------------------
    def split_module(self):
        f = self.header("Split PDF", "Split by bookmarks, a fixed page count, or custom ranges.")
        body = self.scroll_body(f)
        pdf = tk.StringVar(); folder = tk.StringVar(); mode = tk.StringVar(value="Top-level bookmarks"); fixed = tk.StringVar(value="10"); ranges = tk.StringVar(value="1-5,6-10"); prefix = tk.StringVar(); numeric = tk.BooleanVar()
        self.row_file(body, "Input PDF", pdf, lambda: pdf.set(choose_pdfs(self.root, False) or pdf.get()))
        self.row_file(body, "Output Folder", folder, lambda: folder.set(filedialog.askdirectory(parent=self.root) or folder.get()))
        self.row_combo(body, "Split Mode", mode, ["Top-level bookmarks", "Fixed page count", "Custom page ranges"])
        efix = self.row_num(body, "Fixed Page Count", fixed); erng = self.row_entry(body, "Custom Ranges", ranges); self.row_entry(body, "Optional File Prefix", prefix); ttk.Checkbutton(body, text="Add numeric prefix e.g. 01 -", variable=numeric).pack(anchor="w")
        def sync(*a):
            efix.configure(state="normal" if mode.get() == "Fixed page count" else "disabled")
            erng.configure(state="normal" if mode.get() == "Custom page ranges" else "disabled")
        mode.trace_add("write", sync); sync()
        def make_name(base, i):
            s = (prefix.get().strip() + " " + base).strip() if prefix.get().strip() else base
            return sanitize_filename(f"{i:02d} - {s}" if numeric.get() else s)
        def save_part(src, a, b, n, i):
            with fitz.open() as d:
                d.insert_pdf(src, from_page=a, to_page=b - 1)
                d.save(str(Path(folder.get()) / (make_name(n, i) + ".pdf")), garbage=4, deflate=True)
        def run():
            if not pdf.get() or not folder.get(): messagebox.showerror("Error", "Select a PDF and an output folder."); return
            try:
                with fitz.open(pdf.get()) as src:
                    total = len(src); count = 0
                    if mode.get() == "Top-level bookmarks":
                        top = [(t, p) for lvl, t, p, *_ in src.get_toc() if lvl == 1]
                        if not top: messagebox.showerror("No bookmarks", "No top-level bookmarks found."); return
                        for idx, (t, p) in enumerate(top, 1): save_part(src, p - 1, (top[idx][1] - 1 if idx < len(top) else total), t, idx); count += 1
                    elif mode.get() == "Fixed page count":
                        step = max(1, safe_int(fixed.get(), 10)); idx = 1
                        for a in range(0, total, step): b = min(total, a + step); save_part(src, a, b, f"Pages {a+1}-{b}", idx); idx += 1; count += 1
                    else:
                        idx = 1
                        for part in ranges.get().split(','):
                            part = part.strip()
                            if not part: continue
                            if '-' in part: a, b = part.split('-', 1); a, b = max(1, safe_int(a, 1)), min(total, safe_int(b, total))
                            else: a = b = safe_int(part, 1)
                            if 1 <= a <= b <= total: save_part(src, a - 1, b, f"Pages {a}-{b}", idx); idx += 1; count += 1
                messagebox.showinfo("Done", f"Created {count} split PDF(s).")
            except Exception as e:
                logger.error("Split failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        ttk.Button(body, text="Split PDF", command=run).pack(anchor="e", pady=12)

    # ---- Delete ---------------------------------------------------------------
    def delete_module(self):
        f = self.header("Delete Pages", "Remove pages and save as a new PDF.")
        body = self.scroll_body(f)
        pdfs = []
        src_grp = self.group(body, "Source"); self.pdf_list_selector(src_grp, pdfs, on_change=lambda: update_apply())
        opt_grp = self.group(body, "Pages")
        pages = tk.StringVar(value="1"); self.row_entry(opt_grp, "Pages to Delete", pages)
        out_mode, out_folder, suffix, if_exists = self.output_group(body, MODULE_OUTPUT_SUFFIXES["delete"])
        def run():
            pages_v = pages.get()
            def mutate(doc, pdf):
                for pno in sorted(parse_pages(pages_v, len(doc)), reverse=True): doc.delete_page(pno)
            self.run_files(pdfs, mutate, out_mode.get(), out_folder.get(), suffix.get(), if_exists.get(), "Deleting Pages")
        action = ttk.Frame(body); action.pack(fill="x", pady=12)
        apply_btn = ttk.Button(action, text="Delete Pages", command=run); apply_btn.pack(side="right")
        def update_apply(): apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()

    # ---- Rotate (unified Pages field) ----------------------------------------
    def rotate_module(self):
        f = self.header("Rotate Pages", "Rotate selected pages. The Pages field accepts all / odd / even / first / last and ranges.")
        body = self.scroll_body(f)
        pdfs = []
        src_grp = self.group(body, "Source"); self.pdf_list_selector(src_grp, pdfs, on_change=lambda: update_apply())
        opt_grp = self.group(body, "Options")
        pages = tk.StringVar(value="all"); angle = tk.StringVar(value="90° clockwise")
        self.row_entry(opt_grp, "Pages", pages)
        self.row_combo(opt_grp, "Rotation", angle, ROTATION_OPTIONS)
        out_mode, out_folder, suffix, if_exists = self.output_group(body, MODULE_OUTPUT_SUFFIXES["rotate"])
        def degrees(): return 90 if angle.get() == "90° clockwise" else (-90 if angle.get() == "90° counter-clockwise" else 180)
        def run():
            deg = degrees(); pages_v = pages.get()
            def mutate(doc, pdf):
                for pno in parse_pages(pages_v, len(doc)):
                    page = doc[pno]; page.set_rotation((page.rotation + deg) % 360)
            self.run_files(pdfs, mutate, out_mode.get(), out_folder.get(), suffix.get(), if_exists.get(), "Rotating Pages")
        action = ttk.Frame(body); action.pack(fill="x", pady=12)
        apply_btn = ttk.Button(action, text="Rotate Pages", command=run); apply_btn.pack(side="right")
        def update_apply(): apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()

    # ---- Bookmark editor ------------------------------------------------------
    def bookmark_module(self):
        f = self.header("Bookmark Editor", "Hierarchy-aware editor using Level | Title | Page No.")
        body = self.scroll_body(f)
        pdf = tk.StringVar(); self.row_file(body, "Input PDF", pdf, lambda: (pdf.set(choose_pdfs(self.root, False) or pdf.get()), load()))
        tree = ttk.Treeview(body, columns=("level", "title", "page"), show="headings", height=14)
        for col, w in [("level", 70), ("title", 520), ("page", 90)]: tree.heading(col, text=col.title()); tree.column(col, width=w)
        tree.pack(fill="both", expand=True, pady=6); bookmarks = []
        def refresh():
            tree.delete(*tree.get_children())
            for i, b in enumerate(bookmarks): tree.insert("", "end", iid=str(i), values=(b[0], b[1], b[2]))
        def load():
            bookmarks.clear()
            if pdf.get():
                try:
                    with fitz.open(pdf.get()) as doc: bookmarks.extend([x[:3] for x in doc.get_toc()])
                except Exception as e:
                    logger.error("Bookmark load failed: %s", e); messagebox.showerror("Error", str(e))
            refresh()
        def add_edit(edit=False):
            if edit:
                sel = tree.selection()
                if not sel: return
                idx = int(sel[0]); default = bookmarks[idx]
            else: idx = None; default = [1, "New Bookmark", 1]
            level = simpledialog.askinteger("Level", "Level (1 = top):", initialvalue=default[0], parent=self.root, minvalue=1)
            if not level: return
            title = simpledialog.askstring("Title", "Bookmark title:", initialvalue=default[1], parent=self.root)
            if not title: return
            page = simpledialog.askinteger("Page", "Page number:", initialvalue=default[2], parent=self.root, minvalue=1)
            if not page: return
            if edit: bookmarks[idx] = [level, title, page]
            else: bookmarks.append([level, title, page])
            refresh()
        def delete():
            for item in reversed(tree.selection()): bookmarks.pop(int(item))
            refresh()
        def validate(bm):
            if not bm: return True, ""
            if bm[0][0] != 1: return False, "The first bookmark must be Level 1."
            prev = 0
            for lvl, _t, _p in bm:
                if lvl < 1: return False, "Levels must be 1 or greater."
                if lvl > prev + 1: return False, f"A level jumps from {prev} to {lvl}; levels may only increase one step at a time."
                prev = lvl
            return True, ""
        def save():
            if not pdf.get(): return
            ok, msg = validate(bookmarks)
            if not ok:
                messagebox.showerror("Invalid bookmark hierarchy", msg); return
            try:
                with fitz.open(pdf.get()) as doc:
                    doc.set_toc(bookmarks); out = resolve_output_path(pdf.get(), "_BookmarksEdited", "Same folder", "", "Auto-increment"); doc.save(out, garbage=4, deflate=True)
                messagebox.showinfo("Done", f"Saved:\n{out}")
            except Exception as e:
                logger.error("Bookmark save failed: %s\n%s", e, traceback.format_exc()); messagebox.showerror("Error", str(e))
        tree.bind("<Double-Button-1>", lambda e: add_edit(True))
        row = ttk.Frame(body); row.pack(fill="x", pady=5)
        for t, c in [("Reload", load), ("Add", lambda: add_edit(False)), ("Edit", lambda: add_edit(True)), ("Delete", delete), ("Save PDF", save)]:
            ttk.Button(row, text=t, command=c).pack(side="left", padx=4)

    # ---- Metadata -------------------------------------------------------------
    def metadata_module(self):
        f = self.header("Metadata Editor", "Read/edit metadata for one or more PDFs (loads automatically when you add the first file).")
        body = self.scroll_body(f)
        pdfs = []
        fields = {k: tk.StringVar() for k in ["title", "author", "subject", "keywords", "creator", "producer"]}
        def load_first():
            if not pdfs: return
            try:
                with fitz.open(pdfs[0]) as doc: meta = doc.metadata or {}
                for k, v in fields.items(): v.set(meta.get(k, "") or "")
            except Exception as e:
                logger.error("Metadata load failed: %s", e); messagebox.showerror("Error", str(e))
        def maybe_autoload():
            if pdfs and not any(v.get() for v in fields.values()):
                load_first()
        src_grp = self.group(body, "Source"); self.pdf_list_selector(src_grp, pdfs, on_change=maybe_autoload)
        fld_grp = self.group(body, "Fields")
        for k, v in fields.items(): self.row_entry(fld_grp, k.title(), v)
        out_mode, out_folder, suffix, if_exists = self.output_group(body, MODULE_OUTPUT_SUFFIXES["metadata"])
        def clear():
            for v in fields.values(): v.set("")
        def apply():
            meta = {k: v.get() for k, v in fields.items()}
            def mutate(doc, pdf):
                old = doc.metadata or {}; old.update(meta); doc.set_metadata(old)
            self.run_files(pdfs, mutate, out_mode.get(), out_folder.get(), suffix.get(), if_exists.get(), "Applying Metadata")
        row = ttk.Frame(body); row.pack(fill="x", pady=10)
        ttk.Button(row, text="Reload from first PDF", command=load_first).pack(side="left")
        ttk.Button(row, text="Clear Fields", command=clear).pack(side="left", padx=8)
        ttk.Button(row, text="Apply Metadata", command=apply).pack(side="right")


def main():
    setup_logging()
    # Crisp rendering on high-DPI Windows displays (no effect elsewhere).
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception as exc:
        logger.debug("DPI awareness setting unavailable: %s", exc)
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names(): style.theme_use("vista")
    except Exception as exc:
        logger.debug("Vista theme unavailable: %s", exc)
    PDFPartner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
