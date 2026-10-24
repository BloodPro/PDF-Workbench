# PDF-Workbench

PDF-Workbench is a desktop PDF utility application designed for professional legal document preparation, tribunal workflows, litigation documentation, and structured PDF compilation.

Built with a practical focus on real-world document-processing needs, PDF-Workbench helps users merge, split, organise, watermark, number, stamp, index, bookmark, and manage PDF files efficiently for legal and procedural use cases.

The project is tailored for legal, tax, tribunal, appeal, and documentation preparation workflows where accuracy, organisation, and professional presentation matter.

> PDF-Workbench is designed for practical, production-oriented document management in legal and formal paperwork environments.

---

## Current Version

## V1.0.4 — Digital Signature, Colour Standardisation & UX Upgrade

Version `V1.0.4` is the latest update to PDF-Workbench, released as a focused enhancement over `V1.0.3`.

This release strengthens the practical experience of professional document preparation by improving the digital signature workflow, standardising the visual system across the application, and refining the overall UI/UX for more consistent and polished day-to-day use.

### Highlights of V1.0.4

- Added and refined the digital signature workflow
- Improved signature placement, scaling, and page-range handling
- Standardised the application's colour palette for a more cohesive design language
- Improved visual consistency across panels, controls, and tool sections
- Refined the interface for better usability, workflow clarity, and professional presentation
- Continued focus on legal-document preparation and tribunal-oriented PDF use cases
- Strengthened the application's readiness for repeated operational use in document-heavy workflows

### Digital Signature Module Highlights

- Added a dedicated digital signature and stamp workflow for placing signatures and seals on PDF pages
- Supports PNG, JPG, and JPEG input formats for flexible signature and approval marking
- Enables precise placement, scaling, and page-range control
- Provides live preview before applying a signature or stamp
- Suitable for legal approvals, internal markings, evidence compilation, and tribunal workflow documentation

### Standardised Colour Palette Highlights

- Introduced a more consistent visual language across interface components
- Standardised buttons, highlights, panels, and tool emphasis for clearer interaction
- Improved readability and visual hierarchy across the application
- Reduced visual clutter and created a more professional legal-document experience
- Improved consistency across multiple PDF modules and workflow tools

### UI/UX Improvements

- Refined dashboard layout for smoother navigation
- Improved visual grouping and workflow clarity across tools
- Improved spacing, hierarchy, and section readability
- Strengthened professional presentation for legal, tribunal, and documentation use cases
- Designed to reduce friction during frequent PDF preparation tasks

---

## Product Overview

PDF-Workbench is intended to support the preparation of PDF bundles, legal paper books, annexures, tribunal documents, indexed compilations, and other structured document workflows.

The application is especially useful for users who regularly work with:
- legal filings and procedural documents
- tribunal and court-related PDF bundles
- appeal paper sets and annexures
- indexed and bookmarked PDFs
- document approvals, stamping, and signatures
- large compilations requiring controlled organisation

---

## Key Features

## 1. PDF Organiser

The PDF Organiser module helps users arrange and prepare PDF files before processing.

### Features
- Add multiple PDFs
- Add all PDFs from a folder
- Reorder selected files
- Drag-to-reorder support
- Edit display names
- Convert display names to title case
- Add numeric prefixes
- Remove numeric prefixes
- Rename actual files on disk when required

---

## 2. Merge PDFs

The Merge PDFs module combines multiple PDF files into a single output document.

### Features
- Add multiple PDFs
- Rearrange files before merging
- Drag-to-reorder support
- Create bookmarks from file names
- Save merged output to a selected destination
- Suitable for appeal papers, annexures, paper books, and document bundles

---

## 3. Text Watermark / Heading

The Text Watermark / Heading module allows users to add headings, labels, and watermarks to PDF pages.

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

The Sign / Stamp module allows users to place image-based signatures, seals, or approval marks on PDF pages.

### Features
- Apply PNG, JPG, and JPEG image stamps
- Signature and seal support
- Approval and internal marking workflows
- Control stamp width
- Select page ranges
- Choose stamp placement
- Live PDF preview before applying

---

## 5. Page Numbering

The Page Numbering module allows users to add formatted page numbers to PDFs.

### Features
- Add page numbers to selected pages
- Support for multiple numbering formats
- Custom numbering text
- Start number configuration
- Font, colour, opacity, bold, and underline support
- Placement controls similar to watermarking

### Supported Page Selection Formats

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

The Split PDF module allows users to divide a PDF into multiple output files.

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
- Safe output handling using suffix-based file naming

---

## 8. Rotate Pages

The Rotate Pages module rotates selected pages in a PDF.

### Rotation Options
- 90° clockwise
- 90° counter-clockwise
- 180°

### Page Selection Support

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
- Build index from a single PDF’s bookmarks
- Build index from multiple file names
- Edit index rows directly
- Add new rows
- Delete rows
- Move rows up or down
- Preview index before saving
- Save index as a standalone PDF
- Prepend index to an existing PDF
- Repoint bookmarks when index pages are inserted
- Keep index pages unnumbered so main body numbering can start correctly

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

PDF-Workbench supports built-in and external fonts.

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

PDF-Workbench includes flexible output handling.

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
- Live preview support
- Collapsible panels
- Progressive disclosure of form fields
- Colour picker
- Opacity slider
- Drag-and-drop support where available
- Rolling log support for diagnostics
- Window icon support
- Windows executable metadata support

---

## Installation

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

For improved font detection and metadata handling:

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

A ready-to-use Windows executable is available in the GitHub Releases section.

For the current release build, the recommended executable name is:

```text
PDF_Partner_v1.0.4_Windows.exe
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

```bash
python -m PyInstaller --onefile --windowed --name PDF_Partner --icon icon.ico --version-file version_info.txt --collect-all tkinterdnd2 pdf_partner.py
```

---

## Release History

## V1.0.4 — Digital Signature, Colour Standardisation & UX Upgrade

### Added
- More refined digital signature workflow
- Improved visual consistency through standardised design palette
- Stronger focus on professional workflow usability

### Improved
- Signature placement and export handling
- Dashboard usability and module clarity
- Overall UI/UX consistency
- Colour harmony and control readability across the interface

### Preserved
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

---

## V1.0.3 — Stability & Release Refinement

### Added
- Improved release-version clarity and metadata structure
- More stable output generation and overwrite handling
- Stronger operational consistency across workflow modules

### Improved
- Dashboard usability
- Output safety and naming consistency
- Workflow reliability
- Visual presentation and UI consistency

### Preserved
- Core PDF processing features remained intact

---

## V1.0.2 — Stability & UI Polish Update

### Added
- Active sidebar highlighting
- Improved output-file safety handling
- Updated version metadata and release readiness

### Improved
- Dashboard and sidebar stability
- File output generation and suffix handling
- UI clarity and professional polish

### Preserved
- Core PDF processing features remained intact

---

## V1.0.1 — Phase 1 UI Refresh

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
- Navigation logic
- Presentation for professional litigation and documentation workflows

---

## V1.0.0 — Initial Executable Release

Initial Windows executable release introducing the core PDF utility modules.

---

## Suggested Release Asset Name

```text
PDF_Partner_v1.0.4_Windows.exe
```

---

## Repository

```text
https://github.com/BloodPro/PDF-Workbench.git
```

---

## Developer

```text
BloodPro
```

---

## Disclaimer

This application is a self-built desktop utility created for practical PDF workflow automation.

The Windows executable is not digitally signed. As a result, Windows SmartScreen may display a warning when the executable is opened for the first time.

Users may review the source code in this repository and build the executable independently if required.

---

## Intended Use

PDF-Workbench is intended for document preparation, PDF organisation, litigation compilations, indexed bundles, tribunal filings, appeal papers, annexures, and internal documentation workflows.

Users should verify final PDFs before filing, submission, or official use.

---

## Development Note

The project is being developed iteratively with a focus on improving usability, stability, and professional workflow support.

The broad development sequence is:

1. UI and dashboard improvement
2. Existing module refinement
3. Advanced module development
4. Workflow optimisation and usability refinement

---

## Summary

PDF-Workbench is a practical PDF solution for legal and professional document preparation workflows, with a clear emphasis on organisation, usability, and production-ready processing. The latest update continues that direction through refined digital-signature functionality, a more cohesive colour system, and a more polished user experience across the product.
