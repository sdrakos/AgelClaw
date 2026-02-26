# PDF Processing Advanced Reference

This is a comprehensive reference document covering advanced PDF processing techniques using multiple libraries and tools.

## Key Libraries & Tools Covered

### Python Libraries
- **pypdfium2** (Apache/BSD) - Fast PDF rendering and text extraction
- **pdfplumber** (MIT) - Structured data and table extraction
- **reportlab** (BSD) - Professional PDF creation with tables
- **pypdf** (BSD) - General PDF manipulation
- **pdfjs-dist** (Apache) - Browser-based PDF rendering

### Command-Line Tools
- **poppler-utils** (GPL-2) - Text/image extraction with `pdftotext`, `pdftoppm`, `pdfimages`
- **qpdf** (Apache) - Advanced page manipulation, encryption, repair
- **pdf-lib** (MIT) - JavaScript library for PDF creation/modification

## Major Sections

### 1. **pypdfium2 Library**
- Render PDFs to high-resolution images
- Fast text extraction by page
- Direct PIL image conversion

### 2. **JavaScript Libraries**
- **pdf-lib**: Load/manipulate existing PDFs, create complex PDFs, merge/split operations
- **pdfjs-dist**: Browser rendering, text extraction with coordinates, annotation extraction

### 3. **Advanced Command-Line Operations**
- Extract text with bounding box coordinates
- Batch image conversion with quality control
- Extract embedded images
- Complex page manipulation and splitting
- PDF optimization and compression
- Encryption/decryption with permissions

### 4. **Advanced Python Techniques**
- Extract text with precise pixel coordinates
- Advanced table extraction with custom detection strategies
- Create professional reports with styled tables

### 5. **Complex Workflows**
- Extract figures/images using `pdfimages` or pypdfium2
- Batch processing with error handling
- PDF cropping and page manipulation
- Chunk processing for large files

## Performance Optimization Tips

| Task | Recommendation |
|------|-----------------|
| Large PDFs | Process in chunks; use `qpdf --split-pages` |
| Text Extraction | Use `pdftotext -bbox-layout` (fastest) |
| Image Extraction | Use `pdfimages` command-line tool |
| Form Filling | Use pdf-lib for structure preservation |
| Memory | Process pages individually; implement chunking |

## Troubleshooting

- **Encrypted PDFs**: Use `PdfReader.decrypt()` with password
- **Corrupted PDFs**: Repair with `qpdf --check` and `--replace-input`
- **Text Extraction Issues**: Fall back to OCR (`pytesseract`) for scanned PDFs

## License Summary
All referenced libraries use permissive licenses (MIT, Apache, BSD) suitable for most projects.
