# PDF-Workbench (PDF Partner)

A modular PDF utility application designed for legal document workflows, particularly Indian Tribunal requirements.
First order of business in this tool is to improve the UI, then move into improvement of existing modules and then to incorporate new modules.

## Features

### Core Modules

1. **PDF Merge And Organiser** - Arrange PDFs, edit display names, and optionally rename files on disk
2. **Text Watermark / Heading** - Add file names or custom text using built-in, app-folder, and Windows fonts
3. **Sign / Stamp** - Apply PNG/JPG signature or seal with PDF page preview
4. **Merge PDFs** - Combine PDFs in custom order with optional file name bookmarks
5. **Index Builder** - Build editable index from bookmarks or file names, save as PDF page
6. **Page Numbering** - Add page numbers with custom formats, fonts, colors, and positions
7. **Split PDF** - Split by bookmarks, fixed page count, or custom page ranges
8. **Delete Pages** - Remove selected pages or ranges
9. **Rotate Pages** - Rotate all/selected/odd/even/first/last pages
10. **Bookmark Editor** - View, add, edit, and delete hierarchical bookmarks
11. **Metadata Editor** - Read, edit, clear, and batch-apply PDF metadata


## Key Features

### 1. PDF Merge And Organise
- Add multiple PDF files.
- Reorder selected files before processing.
- Drag-to-reorder support in merge and organiser workflows.
- Save merged PDFs with configurable output-folder options.

### 2. Text Watermark / Heading
- Add text watermark or heading to selected pages.
- Supports placement options such as top-left, top-center, top-right, center, bottom-left, bottom-center, bottom-right, and custom X/Y.
- Supports font selection, font size, colour, opacity, underline, and bold.
- Includes diagonal watermark mode for labels such as `DRAFT` or `CONFIDENTIAL`.

### 3. Image Stamp
- Add image-based stamps to PDFs.
- Supports image placement, size, opacity, and live preview.
- Useful for signature stamps, approval stamps, or internal document markings.

### 4. Page Numbering
- Add page numbers to PDFs.
- Supports multiple page-number formats.
- Allows custom text formats.
- Supports page-range selection such as:
  - `all`
  - `first`
  - `last`
  - `odd`
  - `even`
  - `3-5`
  - `first,last,3-5,odd`

### 5. Rotate Pages
- Rotate selected pages by:
  - 90° clockwise
  - 90° counter-clockwise
  - 180°
- Uses the same page-selection format as other modules.

### 6. Editable Index Builder
- Build an editable index table with columns:
  - Sr
  - Particulars
  - From
  - To
- Generate index rows from:
  - A single PDF’s top-level bookmarks; or
  - Multiple PDF file names and cumulative page counts.
- Preview the index.
- Save the index as a standalone PDF.
- Prepend the index to an existing PDF.
- Keeps the index page unnumbered so that body page numbering starts correctly.

### 7. Bookmark Handling
- Reads top-level PDF bookmarks for index generation.
- Validates bookmark hierarchy before saving.
- Re-points bookmarks when an index is prepended.

### 8. Font Management
- Supports built-in PDF fonts such as Helvetica, Times, and Courier.
- Supports external fonts from:
  - Application font folder
  - Windows fonts folder
  - User fonts folder
- Uses real bold for built-in fonts and synthetic bold for external fonts.

### 9. Output Management
- Save output in:
  - Same folder
  - Chosen output folder
  - Output subfolder
  - Dated output folder
- Handles existing files using:
  - Auto-increment
  - Overwrite
  - Ask before overwrite

### 10. User Experience Features
- Live debounced preview.
- Collapsible panels for cleaner screens.
- Progressive disclosure of fields based on selected options.
- Colour picker support.
- Opacity slider.
- Optional drag-and-drop support using `tkinterdnd2`.
- Rolling log file for diagnostics.

---

## Installation

### Requirements
- Python 3.x
- `PyMuPDF` (fitz)
- `Pillow` (PIL)
- `tkinter` (usually included with Python)

### Optional
```bash
pip install tkinterdnd2  # Enables drag-and-drop from Explorer
pip install fonttools     # For proper font name extraction
