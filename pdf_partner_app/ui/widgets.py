"""Reusable Tkinter components for PDF Partner."""

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageTk
import fitz  # PyMuPDF

from pdf_partner_app.utils.config import A4_W_MM, A4_H_MM, MM, logger
from pdf_partner_app.core.engine import place_box


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
