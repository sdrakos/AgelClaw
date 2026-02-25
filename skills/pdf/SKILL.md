---
name: pdf
description: Process PDF files with Python and command-line tools. Use when extracting text/tables from PDFs, creating new PDFs, merging/splitting documents, OCR for scanned PDFs, adding watermarks, or password protection.
---

# PDF Processing Guide

This is a comprehensive guide for PDF manipulation using Python libraries and command-line tools.

## Overview

The guide covers essential PDF operations including:
- Extracting text and tables
- Creating new PDFs
- Merging/splitting documents
- Handling forms

## Key Python Libraries

### **pypdf** - Basic Operations
Used for fundamental PDF manipulation:

```python
from pypdf import PdfReader, PdfWriter

# Read a PDF
reader = PdfReader("document.pdf")
print(f"Pages: {len(reader.pages)}")

# Extract text
text = ""
for page in reader.pages:
    text += page.extract_text()
```

**Common tasks:**
- **Merge PDFs** - Loop through files, add pages to writer
- **Split PDFs** - Save individual pages to separate files
- **Extract Metadata** - Access `reader.metadata` (title, author, subject, creator)
- **Rotate Pages** - Use `page.rotate(90)`

### **pdfplumber** - Text and Table Extraction
Best for extracting text with layout and tables:

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        tables = page.extract_tables()
```

**Advanced: Extract tables to Excel**
```python
import pandas as pd

all_tables = []
for page in pdf.pages:
    tables = page.extract_tables()
    for table in tables:
        if table:
            df = pd.DataFrame(table[1:], columns=table[0])
            all_tables.append(df)

combined_df = pd.concat(all_tables, ignore_index=True)
combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### **reportlab** - Create PDFs

**Basic creation:**
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter

c.drawString(100, height - 100, "Hello World!")
c.line(100, height - 140, 400, height - 140)
c.save()
```

**Multi-page with Platypus:**
```python
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = [
    Paragraph("Report Title", styles['Title']),
    Paragraph("Content...", styles['Normal']),
    PageBreak(),
    Paragraph("Page 2", styles['Heading1'])
]
doc.build(story)
```

## Command-Line Tools

### **pdftotext** (poppler-utils)
```bash
pdftotext input.pdf output.txt              # Extract text
pdftotext -layout input.pdf output.txt      # Preserve layout
pdftotext -f 1 -l 5 input.pdf output.txt    # Pages 1-5
```

### **qpdf**
```bash
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf  # Merge
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf            # Extract pages
qpdf input.pdf output.pdf --rotate=+90:1                # Rotate
qpdf --password=pass --decrypt encrypted.pdf decrypted.pdf
```

### **pdftk**
```bash
pdftk file1.pdf file2.pdf cat output merged.pdf
pdftk input.pdf burst                      # Split all pages
pdftk input.pdf rotate 1east output rotated.pdf
```

## Common Tasks

### Extract Text from Scanned PDFs (OCR)
```python
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = ""
for i, image in enumerate(images):
    text += f"Page {i+1}:\n"
    text += pytesseract.image_to_string(image)
```

### Add Watermark
```python
watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)

with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### Password Protection
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()

for page in reader.pages:
    writer.add_page(page)

writer.encrypt("userpassword", "ownerpassword")
with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

### Extract Images
```bash
pdfimages -j input.pdf output_prefix
# Outputs: output_prefix-000.jpg, output_prefix-001.jpg, etc.
```

## Quick Reference Table

| Task | Best Tool | Command/Code |
|------|-----------|--------------|
| Merge PDFs | pypdf | `writer.add_page(page)` |
| Extract text | pdfplumber | `page.extract_text()` |
| Extract tables | pdfplumber | `page.extract_tables()` |
| Create PDFs | reportlab | Canvas or Platypus |
| Command line merge | qpdf | `qpdf --empty --pages ...` |
| OCR | pytesseract | Convert to image first |
