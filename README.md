# PDF-Workbench (PDF Partner)

**PDF Partner** is a modular desktop PDF utility application developed by **BloodPro** for professional PDF preparation, litigation documentation, and structured document compilation workflows.

The application is designed especially for legal, tax, tribunal, appeal, and documentation preparation use cases where PDFs need to be merged, organised, indexed, stamped, numbered, bookmarked, and prepared in a structured manner.

> This application has been built through vibe coding, with a practical focus on solving real document-preparation problems faced in professional workflows.

---

## Current Version

## V1.0.2 — Stability & UI Polish Update

Version `V1.0.2` is a stability and UI polish update built on top of the Phase 1 UI Refresh introduced in `v1.0.1`.

This release focuses on improving application stability, sidebar usability, output-file safety, version metadata, and release-build readiness while preserving the existing PDF processing functionality.

---

## What is New in V1.0.2

### Stability Improvements

- Permanently cleaned the Tkinter padding issue that could cause runtime errors in the dashboard/sidebar UI.
- Improved application reliability after the Phase 1 UI refresh.
- Preserved the existing PDF processing modules and workflows.

### UI Polish

- Added active sidebar highlighting.
- The sidebar now gives visual feedback for the currently selected tool.
- Navigation between dashboard and modules is clearer and more professional.

### Output Safety Improvements

- Improved output-path generation.
- Added safer output suffix handling.
- Reduced the risk of accidentally overwriting original input PDFs.
- Added fallback output suffix handling where required.

### Versioning Improvements

- Updated application version to `1.0.2`.
- Added updated Windows executable metadata through `version_info_v1.0.2.txt`.
- Recommended executable release name:


## Project Roadmap

The development approach for PDF Partner is as follows:

1. Improve the user interface and dashboard experience.
2. Improve and stabilise existing modules.
3. Add new modules and advanced workflows.

Version `v1.0.1` represents the first step in this roadmap by introducing a more professional dashboard and workflow-oriented layout.

---

## What is New in V1.0.1

## Phase 1 UI Refresh

The dashboard has been redesigned to make the application easier to navigate and more suitable for professional litigation and documentation workflows.

### Updated Dashboard Structure

The application now groups tools into the following workflow sections:

### Core PDF Tools

- Merge PDFs
- Split PDFs
- Delete Pages
- Rotate Pages

### Watermarking & Stamping

- Text Watermark
- Page Numbering
- Sign / Stamp

### Litigation Tools

- Index Builder
- Bookmark Editor
- PDF Organiser

### Document Properties

- Metadata Editor

---

## UI / UX Improvements In v1.0.1

- Professional dashboard layout
- Left-side navigation panel
- Categorised tool grouping
- Improved tool discoverability
- BloodPro branding inside the application
- GitHub repository link inside the application
- Updated Windows executable metadata
- Cleaner workflow-oriented presentation
- Better separation between PDF tools, watermarking tools, litigation tools, and metadata tools

---

## Key Features

---

## 1. PDF Organiser

The PDF Organiser module helps users arrange and prepare PDF files before processing.

### Features

- Add multiple PDF files
- Add all PDF files from a folder
- Reorder selected files
- Drag-to-reorder support
- Edit display names
- Convert display names to Title Case
- Add numeric prefixes
- Remove numeric prefixes
- Optionally rename actual files on disk

---

## 2. Merge PDFs

The Merge PDFs module combines multiple PDFs into one output file.

### Features

- Add multiple PDFs
- Reorder PDFs before merging
- Drag-to-reorder support
- Create bookmarks from file names
- Save merged output to a selected file
- Suitable for creating appeal papers, annexure compilations, paper books, and document bundles

---

## 3. Text Watermark / Heading

The Text Watermark / Heading module allows users to add text-based headings, labels, or watermarks to PDF pages.

### Features

- Add file name as heading
- Add custom text
- Apply text to selected pages
- Support for multiple placement options:
  - Top Left
  - Top Center
  - Top Right
  - Center
  - Bottom Left
  - Bottom Center
  - Bottom Right
  - Custom X/Y
- Font selection support
- Font size control
- Colour picker
- Opacity control
- Bold and underline options
- Diagonal watermark mode for labels such as:
  - `DRAFT`
  - `CONFIDENTIAL`
  - `FINAL`
  - `WITHOUT PREJUDICE`

---

## 4. Sign / Stamp

The Sign / Stamp module allows users to place image-based stamps or signatures on PDF pages.

### Features

- Apply PNG, JPG, or JPEG image stamps
- Useful for:
  - Signature stamps
  - Seal stamps
  - Approval stamps
  - Internal document markings
- Control stamp width
- Select page range
- Choose stamp placement
- Live PDF preview before applying

---

## 5. Page Numbering

The Page Numbering module allows users to add formatted page numbers to PDFs.

### Features

- Add page numbers to selected pages
- Supports multiple numbering formats
- Supports custom numbering text
- Allows start number configuration
- Font, colour, opacity, bold, and underline support
- Placement controls similar to watermarking

### Supported Page Selection Formats

The page field supports flexible values such as:

```text
all
first
last
odd
even
3-5
first,last,3-5,odd
```

---

## 6. Split PDF

The Split PDF module allows users to divide a PDF into multiple output PDFs.

### Split Options

- Split by top-level bookmarks
- Split by fixed page count
- Split by custom page ranges

### Additional Options

- Optional file prefix
- Optional numeric prefix
- Custom output folder selection

---

## 7. Delete Pages

The Delete Pages module removes selected pages from PDF files.

### Features

- Delete single pages
- Delete page ranges
- Delete odd or even pages
- Delete first or last page
- Save as a new output PDF
- Safe output handling through suffix-based file naming

---

## 8. Rotate Pages

The Rotate Pages module rotates selected pages in a PDF.

### Rotation Options

- 90° clockwise
- 90° counter-clockwise
- 180°

### Page Selection Support

The module uses the same flexible page selection system as other modules:

```text
all
odd
even
first
last
1-5
first,last,3-5,odd
```

---

## 9. Editable Index Builder

The Index Builder is designed for litigation and structured documentation workflows.

It can generate an editable index table from bookmarks or from multiple selected files.

### Index Table Columns

- Sr
- Particulars
- From
- To

### Features

- Build index from a single PDF’s top-level bookmarks
- Build index from multiple PDF file names
- Edit index rows directly
- Add new rows
- Delete rows
- Move rows up or down
- Preview index before saving
- Save index as a standalone PDF
- Prepend index to an existing PDF
- Repoint bookmarks when index pages are inserted
- Keeps index pages unnumbered so main body numbering can start correctly

---

## 10. Bookmark Editor

The Bookmark Editor allows users to view, add, edit, delete, and save PDF bookmarks.

### Features

- Load bookmarks from PDF
- Add new bookmarks
- Edit existing bookmarks
- Delete bookmarks
- Validate bookmark hierarchy before saving
- Save edited bookmarks into a new output PDF

---

## 11. Metadata Editor

The Metadata Editor allows users to read and update PDF metadata.

### Supported Metadata Fields

- Title
- Author
- Subject
- Keywords
- Creator
- Producer

### Features

- Load metadata from the first selected PDF
- Edit metadata fields
- Clear metadata fields
- Apply metadata to one or more PDFs
- Save output using configured output options

---

## 12. Font Management

PDF Partner supports both built-in and external fonts.

### Built-In Fonts

- Helvetica
- Times Roman
- Courier

### External Font Sources

- Application `Fonts` folder
- Windows fonts folder
- User fonts folder

### Font Features

- Real bold support for built-in fonts
- Synthetic bold support for external fonts
- Optional font name extraction through `fontTools`

---

## 13. Output Management

PDF Partner includes flexible output handling.

### Output Modes

- Same folder
- Choose output folder
- Create Output subfolder
- Create dated output folder

### Existing File Handling

- Auto-increment
- Overwrite
- Ask before overwrite

---

## 14. User Experience Features

- Professional dashboard layout
- Sidebar navigation
- Live debounced preview
- Collapsible panels
- Progressive disclosure of form fields
- Colour picker
- Opacity slider
- Drag-and-drop support where available
- Rolling log file for diagnostics
- Window icon support
- Windows executable metadata support

---

## Installation From Source

### Requirements

- Python 3.x
- PyMuPDF
- Pillow
- Tkinter

Tkinter is usually included with standard Python installations on Windows.

### Install Required Packages

```bash
pip install pymupdf pillow
```

### Optional Packages

For drag-and-drop support:

```bash
pip install tkinterdnd2
```

For improved font name extraction:

```bash
pip install fonttools
```

---

## Running From Source

To run the application:

```bash
python pdf_partner.py
```

---

## Windows Executable

A ready-to-use Windows executable is available under the GitHub Releases section.

For version `v1.0.1`, the recommended executable name is:

```text
PDF_Partner_v1.0.1_Windows.exe
```

This executable is generated from the Python source code using PyInstaller.

---

## Building The Executable

### Build Without Icon

```bash
python -m PyInstaller --onefile --windowed --name PDF_Partner --version-file version_info.txt pdf_partner.py
```

### Build With Icon

```bash
python -m PyInstaller --onefile --windowed --name PDF_Partner --icon icon.ico --version-file version_info.txt pdf_partner.py
```

### Build With Drag-And-Drop Support

If `tkinterdnd2` is installed and drag-and-drop support is required in the executable:

```bash
python -m PyInstaller --onefile --windowed --name PDF_Partner --icon icon.ico --version-file version_info.txt --collect-all tkinterdnd2 pdf_partner.py
```

---

## Release Notes

## v1.0.1 — Phase 1 UI Refresh

### Added

- Professional dashboard layout
- Left sidebar navigation
- Categorised tool sections
- BloodPro branding
- GitHub repository link inside the application
- Updated Windows executable metadata
- `version_info.txt` for application properties

### Improved

- Dashboard readability
- Tool discoverability
- Navigation between modules
- Application presentation for professional document and litigation workflows
- Visual grouping of core PDF, watermarking, litigation, and metadata tools

### Preserved

The core PDF features from `v1.0.0` are retained, including:

- Merge PDFs
- Split PDF
- Delete Pages
- Rotate Pages
- Text Watermark / Heading
- Page Numbering
- Sign / Stamp
- Index Builder
- Bookmark Editor
- PDF Organiser
- Metadata Editor

### Notes

- This version is focused on UI and dashboard improvements.
- No major PDF processing engine change is intended in this release.

---

## v1.0.0 — Initial Executable Release

Initial Windows executable release of PDF Partner with core PDF utility modules.

---

## Suggested Release Asset Name

For GitHub Releases, the executable may be uploaded as:

```text
PDF_Partner_v1.0.1_Windows.exe
```

---

## Repository

```text
https://github.com/BloodPro/PDF-Workbench.git
```

---

## Developer

Developed by:

```text
BloodPro
```

---

## Disclaimer

This application is a self-built desktop utility created for practical PDF workflow automation.

The Windows executable is not digitally signed. As a result, Windows SmartScreen may show a warning when the executable is opened for the first time.

Users may review the source code in this repository and build the executable independently if required.

---

## Intended Use

PDF Partner is intended for document preparation, PDF organisation, litigation compilations, indexed bundles, tribunal filings, appeal papers, annexures, and internal documentation workflows.

Users should verify final PDFs before filing, submission, or official use.

---

## Development Note

This project is being developed iteratively. The current priority is to improve the user interface and refine the existing modules before adding new modules.

The broad development sequence is:

1. UI and dashboard improvement
2. Existing module improvement
3. New module development
