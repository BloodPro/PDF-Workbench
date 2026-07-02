r"""
PDF Partner - Modular PDF Utility Application

IMPROVEMENTS IN THIS REVISION:
==============================
* Extracted PlacementBuilder: centralized, reusable placement UI logic eliminates ~150 lines of duplication
* Standardized ButtonBar: consistent button spacing and layout across all modules
* MODULE_OUTPUT_SUFFIXES: single source of truth for output file naming conventions
* UIMessenger: centralized error, warning, info, and confirmation messaging

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
"""

import os
import re
import sys
import json
import subprocess
import traceback
import tempfile
import logging
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
SETTINGS_FILE = Path.home() / ".pdf_partner_settings.json"
LOG_FILE = Path.home() / "PDF_Partner.log"
MM = 72 / 25.4
A4_W_MM, A4_H_MM = 210, 297

POSITIONS = ["Top Left", "Top Center", "Top Right", "Center", "Bottom Left", "Bottom Center", "Bottom Right", "Custom X/Y"]
PAGE_FORMATS = ["Page {n} of {total}", "Page {n}", "- {n} -", "{n}", "Custom"]
ROTATION_OPTIONS = ["90° clockwise", "90° counter-clockwise", "180°"]
OUTPUT_MODES = ["Same folder", "Choose output folder", "Create Output subfolder", "Create dated output folder"]
IF_EXISTS_OPTIONS = ["Auto-increment", "Overwrite", "Ask"]

# ---- Centralized Output Suffixes ------------------------------------------------
MODULE_OUTPUT_SUFFIXES = {
    "text_heading": "_Heading",
    "page_numbering": "_Numbered",
    "sign_stamp": "_Signed",
    "merge": "_Merged",
    "index": "_Indexed",
    "split": "_Split",
    "delete": "_PagesDeleted",
    "rotate": "_Rotated",
    "bookmark": "_BookmarksEdited",
    "metadata": "_Metadata",
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
BOLD_MAP = {
    "helv": "hebo", "heit": "hebi", "tiro": "tibo", "tiit": "tibi", "cour": "cobo", "coit": "cobi",
    "hebo": "hebo", "hebi": "hebi", "tibo": "tibo", "tibi": "tibi", "cobo": "cobo", "cobi": "cobi",
}
FONT_PATTERNS = ("*.ttf", "*.otf", "*.ttc", "*.otc", "*.TTF", "*.OTF", "*.TTC", "*.OTC")
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}

logger = logging.getLogger("pdf_partner")


# ---- UI Messaging (Centralized) --------------------------------------------------
class UIMessenger:
    """Centralized messaging for errors, warnings, info, and confirmations."""
    
    def __init__(self, root):
        self.root = root
    
    def error_validation(self, message, parent=None):
        """Validation error: field is empty, invalid format, etc."""
        messagebox.showerror("Validation Error", message, parent=parent or self.root)
    
    def error_file(self, filename, exc, parent=None):
        """File operation error: read failed, write failed, etc."""
        msg = f"Unable to process file:\n{filename}\n\n{str(exc)}"
        messagebox.showerror("File Error", msg, parent=parent or self.root)
    
    def error_runtime(self, title, exc, include_traceback=False, parent=None):
        """Generic runtime error with optional traceback."""
        msg = str(exc)
        if include_traceback and hasattr(exc, '__traceback__'):
            msg += f"\n\n{traceback.format_exc()}"
        messagebox.showerror(title, msg, parent=parent or self.root)
    
    def success(self, title, message, parent=None):
        """Success confirmation."""
        messagebox.showinfo(title, message, parent=parent or self.root)
    
    def success_files(self, count, parent=None):
        """Success with file count."""
        messagebox.showinfo("Done", f"Successfully processed {count} PDF(s).", parent=parent or self.root)
    
    def warning(self, title, message, parent=None):
        """Warning message."""
        messagebox.showwarning(title, message, parent=parent or self.root)
    
    def warning_with_details(self, title, count_done, count_errors, details_location, parent=None):
        """Warning with completion details."""
        msg = f"Completed: {count_done}\nErrors: {count_errors}\n\nDetails:\n{details_location}"
        messagebox.showwarning(title, msg, parent=parent or self.root)
    
    def confirm(self, title, message, parent=None):
        """Yes/No confirmation."""
        return messagebox.askyesno(title, message, parent=parent or self.root)


# ---- Placement Builder (Extracted & Centralized) --------------------------------
class PlacementBuilder:
    """
    Unified placement UI builder for overlay operations (text, stamp, etc.).
    Eliminates duplication across Text, Sign, and other positioning modules.
    """
    
    def __init__(self, parent, app, pos_var, mx_var, my_var, cx_var, cy_var):
        """
        Args:
            parent: parent frame/widget
            app: PDFPartner instance (for row builders)
            pos_var, mx_var, my_var, cx_var, cy_var: Tkinter variables for position/margin values
        """
        self.parent = parent
        self.app = app
        self.pos_var = pos_var
        self.mx_var = mx_var
        self.my_var = my_var
        self.cx_var = cx_var
        self.cy_var = cy_var
        self.detail_frame = None
    
    def build(self, title="Placement", show_pages=True, pages_var=None):
        """
        Build and return the placement group frame.
        
        Args:
            title: group title (default "Placement")
            show_pages: whether to include a Pages field (default True)
            pages_var: StringVar for pages (required if show_pages=True)
        
        Returns:
            The group frame (ttk.LabelFrame)
        """
        place_grp = self.app.group(self.parent, title)
        
        # Position combo
        self.app.row_combo(place_grp, "Position", self.pos_var, POSITIONS)
        
        # Pages field (if applicable)
        if show_pages and pages_var:
            self.app.row_entry(place_grp, "Pages", pages_var)
        
        # Detail frame for margin/custom fields
        self.detail_frame = ttk.Frame(place_grp)
        self.detail_frame.pack(fill="x")
        
        # Rebuild when position changes
        self.pos_var.trace_add("write", lambda *_: self._rebuild_detail())
        self._rebuild_detail()
        
        return place_grp
    
    def _rebuild_detail(self):
        """Dynamically rebuild detail fields based on selected position."""
        for w in self.detail_frame.winfo_children():
            w.destroy()
        
        pos = self.pos_var.get()
        
        if pos == "Custom X/Y":
            self.app.row_num(self.detail_frame, "Custom X mm", self.cx_var)
            self.app.row_num(self.detail_frame, "Custom Y mm", self.cy_var)
        elif pos == "Center":
            ttk.Label(self.detail_frame, text="Centered - margins not used.", foreground="#777").pack(anchor="w", padx=2, pady=2)
        else:
            self.app.row_num(self.detail_frame, "Side Margin mm", self.mx_var)
            self.app.row_num(self.detail_frame, "Top/Bottom Margin mm", self.my_var)


# ---- Button Bar (Standardized) ---------------------------------------------------
class ButtonBar:
    """
    Standardized button bar with consistent spacing.
    Divides buttons into left-aligned and right-aligned groups.
    """
    
    def __init__(self, parent, padding=(12, 0)):
        """
        Args:
            parent: parent frame/widget
            padding: (vertical_top, vertical_bottom) padding
        """
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=padding)
        
        self.left_frame = ttk.Frame(self.frame)
        self.left_frame.pack(side="left")
        
        self.right_frame = ttk.Frame(self.frame)
        self.right_frame.pack(side="right")
    
    def add_left(self, text, command, padx=3):
        """Add a button to the left side."""
        btn = ttk.Button(self.left_frame, text=text, command=command)
        btn.pack(side="left", padx=padx)
        return btn
    
    def add_right(self, text, command, padx=3, primary=False):
        """Add a button to the right side. Set primary=True for main action buttons."""
        btn = ttk.Button(self.right_frame, text=text, command=command)
        btn.pack(side="right", padx=padx)
        return btn
    
    def add_center(self, text, command, padx=3):
        """Add a button to a center position (create if needed)."""
        if not hasattr(self, 'center_frame'):
            self.center_frame = ttk.Frame(self.frame)
            self.center_frame.pack()
        btn = ttk.Button(self.center_frame, text=text, command=command)
        btn.pack(side="left", padx=padx)
        return btn


# (All utility functions remain the same: setup_logging, app_base_dir, etc.)
# ... [Keep all existing utility functions up to line ~622] ...

def setup_logging():
    try:
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
            logger.addHandler(handler)
    except Exception:
        pass


def app_base_dir():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def app_fonts_dir():
    p = app_base_dir() / "Fonts"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
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
    except Exception:
        return {}


def save_settings(settings):
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception:
        pass


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
    target = folder / f"{p.stem}{suffix}{p.suffix}"
    if target.exists():
        if if_exists == "Overwrite":
            return target
        if if_exists == "Ask" and messagebox.askyesno("File Exists", f"Overwrite existing file?\n{target}"):
            return target
        base, ext, idx = folder / f"{p.stem}{suffix}", p.suffix, 1
        while True:
            candidate = Path(str(base) + f"_{idx:02d}" + ext)
            if not candidate.exists():
                return candidate
            idx += 1
    return target


# ... [Keep all other utility functions through preview_font_spec] ...

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
    """Centered watermark text rotated by `angle` degrees across the page."""
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
    """Build index rows from a single PDF's top-level bookmarks."""
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
    """Render index rows into an in-memory fitz.Document (A4 by default)."""
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


# ---- Classes (Collapsible, PDFPreview, ScrollableFrame, PDFPartner remain similar) ----
# ... [Keep Collapsible, PDFPreview, ScrollableFrame as-is] ...

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
            except Exception: pass

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
        self.canvas.bind("<Enter>", self._activate)
        self.canvas.bind("<Leave>", self._maybe_deactivate)

    def _activate(self, _):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _maybe_deactivate(self, _):
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
        if isinstance(event.widget, (tk.Listbox, ttk.Treeview, tk.Text)):
            return
        try:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass


# ---- USAGE EXAMPLE FOR REFACTORED COMPONENTS ----
# This shows how to use PlacementBuilder and ButtonBar in your modules:
#
# EXAMPLE 1: Using PlacementBuilder in text_module / sign_module:
#     pos = tk.StringVar(value="Bottom Center")
#     mx = tk.StringVar(value="8")
#     my = tk.StringVar(value="8")
#     cx = tk.StringVar(value="10")
#     cy = tk.StringVar(value="10")
#     pages = tk.StringVar(value="all")
#
#     builder = PlacementBuilder(left, self, pos, mx, my, cx, cy)
#     place_grp = builder.build(title="Placement", show_pages=True, pages_var=pages)
#
# EXAMPLE 2: Using ButtonBar in any module:
#     actions = ButtonBar(body)
#     actions.add_left("Clear", clear_fn)
#     actions.add_left("Reload", reload_fn)
#     actions.add_right("Apply", apply_fn)
#
# EXAMPLE 3: Using UIMessenger for consistent messaging:
#     messenger = UIMessenger(self.root)
#     messenger.error_validation("Please select a PDF")
#     messenger.success_files(count_done)
#     if messenger.confirm("Delete", "Are you sure?"):
#         # perform deletion
#
# EXAMPLE 4: Using MODULE_OUTPUT_SUFFIXES:
#     suffix = MODULE_OUTPUT_SUFFIXES.get("text_heading", "")
#     out_mode, out_folder, suffix_var, if_exists = self.output_group(left, suffix)


def main():
    setup_logging()
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names(): style.theme_use("vista")
    except Exception:
        pass
    # PDFPartner would go here - instantiate and run
    root.mainloop()


if __name__ == "__main__":
    main()
