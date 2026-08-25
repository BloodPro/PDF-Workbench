"""Core PDF engine and manipulation functions."""

import fitz  # PyMuPDF
from pdf_partner_app.utils.config import MM, logger
from pdf_partner_app.utils.helpers import clean_title

def text_width(text, size, fontname="helv"):
    try:
        if fontname != "customfont":
            return fitz.get_text_length(text, fontname=fontname, fontsize=size)
    except Exception:
        pass
    return len(text) * size * 0.52


def place_box(w, h, iw, ih, pos, m_side, m_tb, cx, cy):
    if pos == "Top Left":        return m_side, m_tb
    if pos == "Top Center":      return (w - iw) / 2, m_tb
    if pos == "Top Right":       return w - m_side - iw, m_tb
    if pos == "Center":          return (w - iw) / 2, (h - ih) / 2
    if pos == "Bottom Left":     return m_side, h - m_tb - ih
    if pos == "Bottom Center":   return (w - iw) / 2, h - m_tb - ih
    if pos == "Bottom Right":    return w - m_side - iw, h - m_tb - ih
    return cx, h - cy - ih


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


def wrap_text_engine(measure_font, fontsize, text, max_w):
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
        lines = wrap_text_engine(measure, body_size, particulars, part_w) if measure else [str(particulars)]
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
