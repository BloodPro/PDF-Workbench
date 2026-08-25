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
"""

import os
import re
import sys
import json
import subprocess
import traceback
import tempfile
import logging
import threading
import webbrowser
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser

from PIL import Image, ImageTk
try:
    import pymupdf as fitz
except ImportError:
    import fitz

from pdf_partner_app.utils.config import (
    APP_NAME, APP_AUTHOR, APP_REPOSITORY, APP_DESCRIPTION, APP_VERSION,
    THEME, MM, A4_W_MM, A4_H_MM, POSITIONS, PAGE_FORMATS, ROTATION_OPTIONS,
    OUTPUT_MODES, IF_EXISTS_OPTIONS, MODULE_OUTPUT_SUFFIXES, MODULE_CATEGORIES,
    LOG_FILE, logger, setup_logging
)
from pdf_partner_app.utils.helpers import (
    app_base_dir, app_fonts_dir, documents_dir, load_settings, save_settings,
    open_folder, safe_float, safe_int, sanitize_filename, clean_title,
    hex_to_rgb01, scan_external_fonts, all_font_options, font_for_selection,
    apply_bold, parse_pages, resolve_output_path, parse_drop_paths,
    FONTTOOLS_AVAILABLE, DND_AVAILABLE, TkinterDnD, DND_FILES
)
from pdf_partner_app.core.engine import (
    text_width, text_point, image_rect, insert_text, insert_diagonal_text,
    index_rows_from_pdf, index_rows_from_files, render_index_pdf
)
from pdf_partner_app.core.crypto_sign import (
    sign_pdf_with_pfx, sign_pdf_with_pkcs11, detect_usb_token_drivers,
    PYHANKO_AVAILABLE
)
from pdf_partner_app.ui.widgets import Collapsible, PDFPreview, ScrollableFrame


def preview_font_spec(selection, bold, size):
    fs = max(6, int(size * 0.85))
    name = selection or ""
    low = name.lower()
    italic = ("italic" in low) or ("oblique" in low)
    is_bold = bool(bold) or ("bold" in low)
    if "courier" in low:
        family = "Courier New"
    elif "times" in low:
        family = "Times New Roman"
    elif "helvetica" in low:
        family = "Arial"
    else:
        family = name.split(":", 1)[-1].strip()
        for word in ("Bold", "Italic", "Oblique", "Regular", "Light", "Medium", "SemiBold", "Semibold", "Black", "Thin"):
            family = re.sub(rf"\b{word}\b", "", family, flags=re.I)
        family = re.sub(r"\s+", " ", family).strip() or "Segoe UI"
    style = " ".join(s for s, on in (("bold", is_bold), ("italic", italic)) if on)
    return (family, fs, style) if style else (family, fs)


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

    def configure_styles(self):
        style = ttk.Style(self.root)
        try:
            if "clam" in style.theme_names():
                style.theme_use("clam")
            elif "vista" in style.theme_names():
                style.theme_use("vista")
        except Exception:
            pass
        try:
            self.root.configure(bg=THEME["bg"])
        except Exception:
            pass
        style.configure(".", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 9))
        style.configure("TFrame", background=THEME["bg"])
        style.configure("App.TFrame", background=THEME["bg"])
        style.configure("TLabelframe", background=THEME["bg"], bordercolor=THEME["border"], relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=THEME["bg"], foreground=THEME["text"])
        style.configure("TCheckbutton", background=THEME["bg"], foreground=THEME["text"])
        style.configure("Header.TLabel", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 22, "bold"))
        style.configure("Subheader.TLabel", background=THEME["bg"], foreground=THEME["muted"], font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=THEME["bg"], foreground=THEME["text"], font=("Segoe UI", 15, "bold"))
        style.configure("Muted.TLabel", background=THEME["bg"], foreground=THEME["muted"], font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9), padding=(8, 4))
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), background=THEME["primary"], foreground="white", borderwidth=0)
        style.map("Accent.TButton", background=[("active", THEME["primary_dark"]), ("pressed", THEME["primary_dark"])], foreground=[("active", "white")])

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
            ("WATERMARKING", [("Text Watermark", self.text_module), ("Page Numbering", self.number_module), ("Sign / Stamp", self.sign_module), ("Digital Signature (DSC)", self.digital_sig_module)]),
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

        def worker():
            nonlocal done
            for i, pdf in enumerate(pdfs, 1):
                self.root.after(0, lambda idx=i, p=pdf: (status.configure(text=f"{idx} / {total}   {Path(p).name}"), bar.configure(value=idx - 1)))
                try:
                    with fitz.open(pdf) as doc:
                        mutate(doc, pdf)
                        out = resolve_output_path(pdf, suffix, out_mode, out_folder, if_exists)
                        doc.save(out, garbage=4, deflate=True)
                    done += 1
                except Exception as e:
                    errors.append(f"{pdf}\n{e}\n{traceback.format_exc()}")
                self.root.after(0, lambda idx=i: bar.configure(value=idx))
            self.root.after(0, lambda: (win.destroy(), self.finish(done, errors)))

        threading.Thread(target=worker, daemon=True).start()

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
        self.dashboard_section(grid, "Core PDF Tools", [("Merge PDFs", "Combine PDFs in order and create bookmarks from file names.", self.merge_module), ("Split PDF", "Split PDFs by bookmarks, fixed page count, or custom ranges.", self.split_module), ("Delete Pages", "Delete selected pages or page ranges safely.", self.delete_module), ("Rotate Pages", "Rotate selected, odd, even, first, last, or all pages.", self.rotate_module)])
        self.dashboard_section(grid, "Watermarking & Stamping", [("Text Watermark", "Add file names, headings, DRAFT, CONFIDENTIAL, or custom text.", self.text_module), ("Page Numbering", "Apply professional page numbers with formatting and placement controls.", self.number_module), ("Sign / Stamp", "Apply signature, seal, or stamp images with live preview.", self.sign_module), ("Digital Signature (DSC)", "Apply cryptographic digital signatures using PFX or USB Token.", self.digital_sig_module)])
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
        category, default_desc = MODULE_CATEGORIES.get(title, ("Module", ""))
        sub_text = subtitle or default_desc
        self.active_tool = title
        self.clear()

        # Banner Card Container
        banner = tk.Frame(
            self.main_area,
            bg=THEME["surface"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            bd=0,
            padx=18,
            pady=14
        )
        banner.pack(fill="x", pady=(0, 14))

        # Top Bar inside Banner: Navigation Breadcrumbs & Back Button
        top_bar = tk.Frame(banner, bg=THEME["surface"])
        top_bar.pack(fill="x")

        back_btn = tk.Button(
            top_bar,
            text="← Back to Dashboard",
            command=self.home,
            bg="#EFF6FF",
            fg=THEME["primary"],
            activebackground="#DBEAFE",
            activeforeground=THEME["primary_dark"],
            relief="flat",
            bd=0,
            padx=10,
            pady=4,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2"
        )
        back_btn.pack(side="left")

        # Breadcrumbs
        crumb_str = f"Dashboard  /  {category}  /  {title}"
        tk.Label(
            top_bar,
            text=crumb_str,
            bg=THEME["surface"],
            fg=THEME["muted"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=14)

        # Category Badge
        badge = tk.Label(
            top_bar,
            text=category.upper(),
            bg="#F1F5F9",
            fg="#475569",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=2
        )
        badge.pack(side="right")

        # Title & Subtitle inside Banner
        title_frame = tk.Frame(banner, bg=THEME["surface"])
        title_frame.pack(fill="x", pady=(10, 0))

        tk.Label(
            title_frame,
            text=title,
            bg=THEME["surface"],
            fg=THEME["text"],
            font=("Segoe UI", 18, "bold"),
            anchor="w"
        ).pack(anchor="w")

        if sub_text:
            tk.Label(
                title_frame,
                text=sub_text,
                bg=THEME["surface"],
                fg=THEME["muted"],
                font=("Segoe UI", 10),
                anchor="w"
            ).pack(anchor="w", pady=(2, 0))

        return self.main_area

    def scroll_body(self, parent):
        scroll = ScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        return scroll.inner

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

        action = ttk.Frame(left); action.pack(fill="x", pady=10)
        apply_btn = ttk.Button(action, text="Add Page Numbers" if is_num else "Apply Text", command=run, style="Accent.TButton")
        apply_btn.pack(side="right")
        def update_apply():
            apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()
        for v in (pos, pages, mx, my, cx, cy, font, size, bold, underline, diagonal, hexc, opacity, fmt, cfmt, startn, src, custom):
            v.trace_add("write", sched)
        refresh_preview()

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
        apply_btn = ttk.Button(action, text="Apply Sign / Stamp", command=run, style="Accent.TButton"); apply_btn.pack(side="right")
        def update_apply():
            apply_btn.configure(state=("normal" if (pdfs and img.get()) else "disabled"))
        update_apply()
        for v in (img, pos, width, pages, mx, my, cx, cy):
            v.trace_add("write", sched)
        img.trace_add("write", lambda *a: update_apply())
        refresh_preview()

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
            def task():
                try:
                    with fitz.open() as doc:
                        toc = []
                        for pdf in pdfs:
                            with fitz.open(pdf) as src: start = len(doc); doc.insert_pdf(src)
                            if bookmarks.get(): toc.append([1, clean_title(pdf), start + 1])
                        if toc: doc.set_toc(toc)
                        doc.save(out.get(), garbage=4, deflate=True)
                    self.root.after(0, lambda: messagebox.showinfo("Done", f"Merged PDF created:\n{out.get()}"))
                except Exception as e:
                    logger.error("Merge failed: %s\n%s", e, traceback.format_exc())
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            threading.Thread(target=task, daemon=True).start()
        ttk.Button(body, text="Merge PDFs", command=run, style="Accent.TButton").pack(anchor="e", pady=12)

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
            ci = int(col[1:]) - 1
            if ci == 0:
                return
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
            def task():
                try:
                    with fitz.open(pdf.get()) as src:
                        total = len(src); count = 0
                        if mode.get() == "Top-level bookmarks":
                            top = [(t, p) for lvl, t, p, *_ in src.get_toc() if lvl == 1]
                            if not top:
                                self.root.after(0, lambda: messagebox.showerror("No bookmarks", "No top-level bookmarks found."))
                                return
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
                    self.root.after(0, lambda: messagebox.showinfo("Done", f"Created {count} split PDF(s)."))
                except Exception as e:
                    logger.error("Split failed: %s\n%s", e, traceback.format_exc())
                    self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            threading.Thread(target=task, daemon=True).start()
        ttk.Button(body, text="Split PDF", command=run, style="Accent.TButton").pack(anchor="e", pady=12)

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
        apply_btn = ttk.Button(action, text="Delete Pages", command=run, style="Accent.TButton"); apply_btn.pack(side="right")
        def update_apply(): apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()

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
        apply_btn = ttk.Button(action, text="Rotate Pages", command=run, style="Accent.TButton"); apply_btn.pack(side="right")
        def update_apply(): apply_btn.configure(state=("normal" if pdfs else "disabled"))
        update_apply()

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

    def digital_sig_module(self):
        f = self.header("Digital Signature (DSC)", "Apply legal cryptographic digital signatures using PFX certificate file (Solution 1) or USB Hardware Token (Solution 2).")
        body = self.scroll_body(f)
        pdfs = []

        sig_mode = tk.StringVar(value="PFX / P12 Certificate File (Solution 1)")
        pfx_path = tk.StringVar(value=self.settings.get("last_pfx_path", ""))
        pfx_pass = tk.StringVar()
        token_dll = tk.StringVar()
        token_pin = tk.StringVar()
        reason = tk.StringVar(value="Digital Legal Signature")
        location = tk.StringVar(value="Court / Tribunal")

        src_grp = self.group(body, "Source PDFs")
        self.pdf_list_selector(src_grp, pdfs)

        mode_grp = self.group(body, "Signature Method")
        self.row_combo(
            mode_grp,
            "Method",
            sig_mode,
            ["PFX / P12 Certificate File (Solution 1)", "USB Hardware Token (Solution 2 - PKCS#11)"]
        )

        pfx_grp = self.group(body, "Solution 1: PFX / P12 Certificate Details")
        self.row_file(
            pfx_grp,
            "PFX/P12 File",
            pfx_path,
            lambda: (
                pfx_path.set(
                    filedialog.askopenfilename(
                        parent=self.root,
                        title="Select PFX/P12 Certificate",
                        filetypes=[("PKCS#12 Certificates", "*.pfx *.p12"), ("All files", "*.*")]
                    ) or pfx_path.get()
                ),
                self.settings.update({"last_pfx_path": pfx_path.get()}),
                save_settings(self.settings)
            )
        )
        self.row_entry(pfx_grp, "Certificate Password", pfx_pass)

        token_grp = self.group(body, "Solution 2: Hardware USB Token Details")
        detected_drivers = detect_usb_token_drivers()
        if detected_drivers:
            token_dll.set(detected_drivers[0])
        self.row_combo(token_grp, "Token PKCS#11 DLL", token_dll, detected_drivers or ["C:\\Windows\\System32\\eps2003csp11.dll"])
        ttk.Button(
            token_grp,
            text="Browse Custom DLL…",
            command=lambda: token_dll.set(
                filedialog.askopenfilename(
                    parent=self.root,
                    title="Select PKCS#11 Driver DLL",
                    filetypes=[("DLL files", "*.dll"), ("All files", "*.*")]
                ) or token_dll.get()
            )
        ).pack(anchor="w", padx=4, pady=2)
        self.row_entry(token_grp, "Token PIN", token_pin)

        meta_grp = self.group(body, "Signature Metadata")
        self.row_entry(meta_grp, "Reason", reason)
        self.row_entry(meta_grp, "Location", location)

        out_mode, out_folder, suffix, if_exists = self.output_group(body, MODULE_OUTPUT_SUFFIXES["digital_sig"])

        def sync_mode(*_):
            is_pfx = sig_mode.get().startswith("PFX")
            self._show_row(pfx_grp, is_pfx)
            self._show_row(token_grp, not is_pfx)

        sig_mode.trace_add("write", sync_mode)
        sync_mode()

        def run():
            if not pdfs:
                messagebox.showerror("Error", "Select PDF file(s) to sign."); return
            if not PYHANKO_AVAILABLE:
                messagebox.showerror("Missing Dependency", "pyHanko library is required for digital signatures.\nInstall via: pip install pyhanko cryptography"); return

            mode = sig_mode.get()
            is_pfx = mode.startswith("PFX")

            if is_pfx and not pfx_path.get():
                messagebox.showerror("Error", "Select a PFX/P12 Certificate file."); return
            if not is_pfx and not token_dll.get():
                messagebox.showerror("Error", "Select a PKCS#11 driver DLL for the USB Token."); return

            def task():
                errors, done = [], 0
                for pdf in pdfs:
                    try:
                        out = resolve_output_path(pdf, suffix.get(), out_mode.get(), out_folder.get(), if_exists.get())
                        if is_pfx:
                            sign_pdf_with_pfx(
                                pdf, str(out), pfx_path.get(), pfx_pass.get(),
                                reason=reason.get(), location=location.get()
                            )
                        else:
                            sign_pdf_with_pkcs11(
                                pdf, str(out), token_dll.get(), token_pin.get(),
                                reason=reason.get(), location=location.get()
                            )
                        done += 1
                    except Exception as exc:
                        errors.append(f"{pdf}\n{exc}\n{traceback.format_exc()}")

                self.root.after(0, lambda: self.finish(done, errors))

            threading.Thread(target=task, daemon=True).start()

        action = ttk.Frame(body); action.pack(fill="x", pady=12)
        ttk.Button(action, text="Digitally Sign Document(s)", command=run, style="Accent.TButton").pack(side="right")

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
        ttk.Button(row, text="Apply Metadata", command=apply, style="Accent.TButton").pack(side="right")


def choose_pdfs(parent, multiple=True, title="Select PDF file(s)"):
    opts = dict(parent=parent, title=title, initialdir=str(documents_dir()), filetypes=[("PDF files", ("*.pdf", "*.PDF")), ("All files", "*.*")])
    if multiple:
        return [f for f in filedialog.askopenfilenames(**opts) if Path(f).suffix.lower() == ".pdf"]
    f = filedialog.askopenfilename(**opts)
    return f if f and Path(f).suffix.lower() == ".pdf" else ""


def choose_image(parent):
    f = filedialog.askopenfilename(parent=parent, title="Select image", initialdir=str(Path.home() / "Pictures"), filetypes=[("Images", ("*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG")), ("All files", "*.*")])
    return f if f and Path(f).suffix.lower() in [".png", ".jpg", ".jpeg"] else ""


def main():
    setup_logging()
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
