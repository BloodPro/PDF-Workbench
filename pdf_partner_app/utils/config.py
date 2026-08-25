"""Config and constants for PDF Partner."""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

APP_NAME = "PDF Partner"
APP_AUTHOR = "BloodPro"
APP_REPOSITORY = "https://github.com/BloodPro/PDF-Workbench.git"
APP_DESCRIPTION = "Professional PDF Workbench for Litigation & Documentation preparation"
APP_COPYRIGHT = "© BloodPro"
APP_VERSION = "1.0.2"
SETTINGS_FILE = Path.home() / ".pdf_partner_settings.json"
LOG_FILE = Path.home() / "PDF_Partner.log"

THEME = {
    "bg": "#F8FAFC",
    "surface": "#FFFFFF",
    "sidebar": "#0F172A",
    "sidebar_hover": "#1E293B",
    "primary": "#2563EB",
    "primary_dark": "#1D4ED8",
    "text": "#0F172A",
    "muted": "#64748B",
    "border": "#E2E8F0",
    "success": "#059669",
    "warning": "#D97706",
    "danger": "#DC2626",
    "accent": "#3B82F6",
}

MM = 72 / 25.4
A4_W_MM, A4_H_MM = 210, 297

POSITIONS = [
    "Top Left", "Top Center", "Top Right", "Center",
    "Bottom Left", "Bottom Center", "Bottom Right", "Custom X/Y"
]
PAGE_FORMATS = ["Page {n} of {total}", "Page {n}", "- {n} -", "{n}", "Custom"]
ROTATION_OPTIONS = ["90° clockwise", "90° counter-clockwise", "180°"]
OUTPUT_MODES = ["Same folder", "Choose output folder", "Create Output subfolder", "Create dated output folder"]
IF_EXISTS_OPTIONS = ["Auto-increment", "Overwrite", "Ask"]

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

MODULE_CATEGORIES = {
    "PDF Organiser": ("Litigation Tools", "Arrange PDFs, edit display names, and rename files on disk."),
    "Text Watermark / Heading": ("Watermarking & Stamping", "Add text-based headings, labels, or watermarks."),
    "Page Numbering": ("Watermarking & Stamping", "Add formatted page numbers with position controls."),
    "Sign / Stamp": ("Watermarking & Stamping", "Place image-based signatures, seals, or approval stamps."),
    "Merge PDFs": ("Core PDF Tools", "Combine multiple PDF files into one structured document."),
    "Index Builder": ("Litigation Tools", "Generate editable index tables from bookmarks or file names."),
    "Split PDF": ("Core PDF Tools", "Divide a PDF by top-level bookmarks, page count, or page ranges."),
    "Delete Pages": ("Core PDF Tools", "Remove selected pages or ranges from a PDF document."),
    "Rotate Pages": ("Core PDF Tools", "Rotate selected or all pages in a PDF document."),
    "Bookmark Editor": ("Litigation Tools", "View, add, edit, delete, and validate PDF bookmark hierarchy."),
    "Metadata Editor": ("Document Properties", "Read, edit, clear, and batch-apply PDF document metadata."),
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
