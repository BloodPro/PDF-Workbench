# PDF-Workbench (PDF Partner)

A modular PDF utility application designed for legal document workflows, particularly Indian Tribunal requirements.

## Features

### Core Modules

1. **PDF Organiser** - Arrange PDFs, edit display names, and optionally rename files on disk
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

## Key Capabilities

- **Progressive disclosure** - UI elements appear only when relevant
- **Live preview** - Real-time preview updates as you configure options
- **Drag-and-drop** - Drop files directly into lists (requires `tkinterdnd2`)
- **Flexible page selection** - Supports ranges like `first,last,3-5,odd,even`
- **Diagonal watermarks** - DRAFT/CONFIDENTIAL style 45° watermarks
- **Font support** - Built-in fonts, app-folder fonts, Windows fonts, user fonts
- **Litigation workflow** - Index builder with editable table (Sr | Particulars | From | To)
- **Safe file handling** - Reserved Windows name guards, auto-increment on conflicts
- **Rolling log file** - Central logging for debugging

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
