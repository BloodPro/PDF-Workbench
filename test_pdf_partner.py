import sys
from unittest.mock import MagicMock

# Mock GUI and PDF dependencies if not installed in headless Linux test env
for mod in [
    "tkinter", "tkinter.font", "tkinter.ttk", "tkinter.filedialog",
    "tkinter.messagebox", "tkinter.simpledialog", "tkinter.colorchooser",
    "fitz", "PIL", "tkinterdnd2", "pyhanko", "pyhanko.pdf_utils.incremental_writer",
    "pyhanko.sign", "pyhanko.sign.fields", "pyhanko.sign.signers", "pyhanko.sign.pkcs11"
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest
from pathlib import Path
from pdf_partner_app.utils.helpers import (
    parse_pages,
    sanitize_filename,
    clean_title,
    hex_to_rgb01,
    safe_int,
    safe_float,
    apply_bold,
    resolve_output_path,
)
from pdf_partner_app.core.engine import (
    index_rows_from_files,
    place_box,
    text_width,
)
from pdf_partner_app.core.crypto_sign import (
    detect_usb_token_drivers,
    sign_pdf_with_pfx,
    sign_pdf_with_pkcs11,
)

def test_parse_pages():
    assert parse_pages("all", 5) == [0, 1, 2, 3, 4]
    assert parse_pages("1, 3, 5", 5) == [0, 2, 4]
    assert parse_pages("first, last", 5) == [0, 4]
    assert parse_pages("odd", 5) == [0, 2, 4]
    assert parse_pages("even", 5) == [1, 3]
    assert parse_pages("1-3", 5) == [0, 1, 2]
    assert parse_pages("first, 3-4, even", 5) == [0, 1, 2, 3]

def test_sanitize_filename():
    assert sanitize_filename("test/file:name?.pdf") == "test_file_name_.pdf"
    assert sanitize_filename("CON.pdf") == "_CON.pdf"
    assert sanitize_filename("") == "Untitled"

def test_clean_title():
    assert clean_title("/path/to/some_document_file.pdf") == "some document file"

def test_hex_to_rgb01():
    assert hex_to_rgb01("#000000") == (0.0, 0.0, 0.0)
    assert hex_to_rgb01("#FFFFFF") == (1.0, 1.0, 1.0)
    assert hex_to_rgb01("#FF0000") == (1.0, 0.0, 0.0)
    assert hex_to_rgb01("invalid") == (0.0, 0.0, 0.0)

def test_safe_int_and_float():
    assert safe_int("10") == 10
    assert safe_int("invalid", default=5) == 5
    assert safe_float("12.34") == 12.34
    assert safe_float("abc", default=1.0) == 1.0

def test_apply_bold():
    name, fpath, fake = apply_bold("helv", None, True)
    assert name == "hebo"
    assert fpath is None
    assert fake is False

    name, fpath, fake = apply_bold("customfont", "/path/font.ttf", True)
    assert name == "customfont"
    assert fpath == "/path/font.ttf"
    assert fake is True

def test_resolve_output_path(tmp_path):
    input_file = tmp_path / "doc.pdf"
    input_file.write_text("fake pdf content")

    out_path = resolve_output_path(input_file, "_Numbered", "Same folder")
    assert out_path.name == "doc_Numbered.pdf"
    assert out_path.parent == tmp_path

    sub_out = resolve_output_path(input_file, "_Numbered", "Create Output subfolder")
    assert sub_out.parent == tmp_path / "Output"

def test_index_rows_from_files():
    files = ["/tmp/Appeal_Brief.pdf", "/tmp/Annexure_A.pdf"]
    rows, warn = index_rows_from_files(files)
    assert len(rows) == 2
    assert rows[0][1] == "Appeal Brief"
    assert rows[1][1] == "Annexure A"
    assert warn == ""

def test_place_box_positions():
    w, h, iw, ih = 100, 200, 20, 10
    assert place_box(w, h, iw, ih, "Top Left", 5, 5, 0, 0) == (5, 5)
    assert place_box(w, h, iw, ih, "Center", 5, 5, 0, 0) == (40, 95)
    assert place_box(w, h, iw, ih, "Bottom Right", 5, 5, 0, 0) == (75, 185)

def test_detect_usb_token_drivers():
    drivers = detect_usb_token_drivers()
    assert isinstance(drivers, list)
