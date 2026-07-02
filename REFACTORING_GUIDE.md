# UI Standardization Refactoring Guide

This guide walks through integrating the four major UI improvements into `pdf_partner.py`.

## Overview of Changes

### 1. PlacementBuilder (HIGHEST PRIORITY)
**Saves ~150 lines of duplicated placement logic**

Currently duplicated in:
- `_text_overlay()` (lines 1254-1270)
- `sign_module()` (lines 1350-1364)
- And potentially in future modules

**Integration Steps:**

#### Step 1: Add PlacementBuilder class (before PDFPartner)
```python
class PlacementBuilder:
    """Unified placement UI builder for overlay operations."""
    
    def __init__(self, parent, app, pos_var, mx_var, my_var, cx_var, cy_var):
        self.parent = parent
        self.app = app
        self.pos_var = pos_var
        self.mx_var = mx_var
        self.my_var = my_var
        self.cx_var = cx_var
        self.cy_var = cy_var
        self.detail_frame = None
    
    def build(self, title="Placement", show_pages=True, pages_var=None):
        """Build and return the placement group frame."""
        place_grp = self.app.group(self.parent, title)
        self.app.row_combo(place_grp, "Position", self.pos_var, POSITIONS)
        
        if show_pages and pages_var:
            self.app.row_entry(place_grp, "Pages", pages_var)
        
        self.detail_frame = ttk.Frame(place_grp)
        self.detail_frame.pack(fill="x")
        
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
```

#### Step 2: Replace placement logic in `_text_overlay()` (around line 1253)

**BEFORE:**
```python
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
```

**AFTER:**
```python
# Placement ----------------------------------------------------------
builder = PlacementBuilder(left, self, pos, mx, my, cx, cy)
place_grp = builder.build(title="Placement", show_pages=True, pages_var=pages)
```

#### Step 3: Apply same pattern to `sign_module()` (around line 1350)

**BEFORE:**
```python
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
```

**AFTER:**
```python
builder = PlacementBuilder(left, self, pos, mx, my, cx, cy)
place_grp = builder.build(title="Placement", show_pages=True, pages_var=pages)
# Insert Width field after the combo but before Pages
self.row_num(place_grp, "Width mm", width)
```

**Net savings: ~50 lines per module, 2 modules = 100 lines saved**

---

### 2. ButtonBar (MEDIUM PRIORITY)
**Standardizes button spacing across all modules**

**Integration Steps:**

#### Step 1: Add ButtonBar class (before PDFPartner)
```python
class ButtonBar:
    """Standardized button bar with consistent spacing."""
    
    def __init__(self, parent, padding=(12, 0)):
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", pady=padding)
        self.left_frame = ttk.Frame(self.frame)
        self.left_frame.pack(side="left")
        self.right_frame = ttk.Frame(self.frame)
        self.right_frame.pack(side="right")
    
    def add_left(self, text, command, padx=3):
        btn = ttk.Button(self.left_frame, text=text, command=command)
        btn.pack(side="left", padx=padx)
        return btn
    
    def add_right(self, text, command, padx=3, primary=False):
        btn = ttk.Button(self.right_frame, text=text, command=command)
        btn.pack(side="right", padx=padx)
        return btn
```

#### Step 2: Replace action button bars

Example: In `delete_module()` (line 1632)

**BEFORE:**
```python
action = ttk.Frame(body); action.pack(fill="x", pady=12)
apply_btn = ttk.Button(action, text="Delete Pages", command=run); apply_btn.pack(side="right")
```

**AFTER:**
```python
actions = ButtonBar(body)
apply_btn = actions.add_right("Delete Pages", run)
```

Apply similarly to:
- `rotate_module()` (line 1655)
- `metadata_module()` (lines 1749-1752)
- `index_module()` (lines 1568-1571)

---

### 3. MODULE_OUTPUT_SUFFIXES (LOW PRIORITY, HIGH VALUE)
**Single source of truth for output naming**

#### Step 1: Add constant (after IF_EXISTS_OPTIONS, around line 92)
```python
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
```

#### Step 2: Update all output_group() calls

**BEFORE:**
```python
out_mode, out_folder, suffix, if_exists = self.output_group(left, "_Numbered")
```

**AFTER:**
```python
out_mode, out_folder, suffix, if_exists = self.output_group(left, MODULE_OUTPUT_SUFFIXES.get("page_numbering", ""))
```

Apply to all 11 modules:
1. `_text_overlay("heading")` → `MODULE_OUTPUT_SUFFIXES["text_heading"]`
2. `_text_overlay("number")` → `MODULE_OUTPUT_SUFFIXES["page_numbering"]`
3. `sign_module()` → `MODULE_OUTPUT_SUFFIXES["sign_stamp"]`
4. `merge_module()` → N/A (doesn't use output_group)
5. `index_module()` → N/A (custom logic)
6. `split_module()` → N/A (custom folder output)
7. `delete_module()` → `MODULE_OUTPUT_SUFFIXES["delete"]`
8. `rotate_module()` → `MODULE_OUTPUT_SUFFIXES["rotate"]`
9. `bookmark_module()` → `MODULE_OUTPUT_SUFFIXES["bookmark"]`
10. `metadata_module()` → `MODULE_OUTPUT_SUFFIXES["metadata"]`

---

### 4. UIMessenger (LOW PRIORITY, FOR FUTURE USE)
**Centralized error/warning/info messaging**

#### Step 1: Add UIMessenger class (before PDFPartner)
```python
class UIMessenger:
    """Centralized messaging for errors, warnings, info, and confirmations."""
    
    def __init__(self, root):
        self.root = root
    
    def error_validation(self, message, parent=None):
        messagebox.showerror("Validation Error", message, parent=parent or self.root)
    
    def error_file(self, filename, exc, parent=None):
        msg = f"Unable to process file:\n{filename}\n\n{str(exc)}"
        messagebox.showerror("File Error", msg, parent=parent or self.root)
    
    def error_runtime(self, title, exc, include_traceback=False, parent=None):
        msg = str(exc)
        if include_traceback and hasattr(exc, '__traceback__'):
            msg += f"\n\n{traceback.format_exc()}"
        messagebox.showerror(title, msg, parent=parent or self.root)
    
    def success(self, title, message, parent=None):
        messagebox.showinfo(title, message, parent=parent or self.root)
    
    def success_files(self, count, parent=None):
        messagebox.showinfo("Done", f"Successfully processed {count} PDF(s).", parent=parent or self.root)
    
    def warning(self, title, message, parent=None):
        messagebox.showwarning(title, message, parent=parent or self.root)
    
    def warning_with_details(self, title, count_done, count_errors, details_location, parent=None):
        msg = f"Completed: {count_done}\nErrors: {count_errors}\n\nDetails:\n{details_location}"
        messagebox.showwarning(title, msg, parent=parent or self.root)
    
    def confirm(self, title, message, parent=None):
        return messagebox.askyesno(title, message, parent=parent or self.root)
```

#### Step 2: Initialize in PDFPartner.__init__()
```python
self.messenger = UIMessenger(root)
```

#### Step 3: Gradually replace messagebox calls

**BEFORE:**
```python
if not pdfs:
    messagebox.showerror("Error", "Select PDF(s).")
    return
```

**AFTER:**
```python
if not pdfs:
    self.messenger.error_validation("Select PDF(s).")
    return
```

---

## Integration Priority

**Phase 1 (Immediate):**
1. Add PlacementBuilder class
2. Refactor `_text_overlay()` to use PlacementBuilder
3. Refactor `sign_module()` to use PlacementBuilder

**Phase 2 (Next):**
4. Add ButtonBar class
5. Refactor all action button bars
6. Add MODULE_OUTPUT_SUFFIXES constant
7. Update all output_group() calls

**Phase 3 (Future):**
8. Add UIMessenger class
9. Gradually replace messagebox calls throughout

---

## Testing Checklist

After each phase:

- [ ] Text Watermark/Heading module loads and placement builder works
- [ ] Sign/Stamp module loads and placement builder works
- [ ] All button bars display with consistent spacing
- [ ] Output suffixes are correct in all modules
- [ ] Drag-and-drop still works
- [ ] Preview still updates live
- [ ] File save/load operations work correctly

---

## Estimated Benefits

- **Lines of code saved**: ~150 lines (PlacementBuilder)
- **Modules affected**: 11
- **Maintainability improvement**: High (single source of truth for messaging, buttons, placement)
- **Visual consistency**: High (standardized spacing)
- **New bugs introduced**: Low (components are isolated, tested separately)

---

## Quick Reference

### PlacementBuilder Usage
```python
builder = PlacementBuilder(parent, self, pos_var, mx_var, my_var, cx_var, cy_var)
place_grp = builder.build(title="Placement", show_pages=True, pages_var=pages)
```

### ButtonBar Usage
```python
actions = ButtonBar(parent)
actions.add_left("Clear", clear_fn)
actions.add_right("Apply", apply_fn)
```

### MODULE_OUTPUT_SUFFIXES Usage
```python
suffix = MODULE_OUTPUT_SUFFIXES.get("page_numbering", "")
out_mode, out_folder, suffix_var, if_exists = self.output_group(left, suffix)
```

### UIMessenger Usage
```python
self.messenger.error_validation("Field is required")
self.messenger.success_files(count)
self.messenger.warning("Warning", "Check your settings")
if self.messenger.confirm("Delete", "Are you sure?"):
    # delete logic
```
