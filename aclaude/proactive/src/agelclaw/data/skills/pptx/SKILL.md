---
name: pptx
description: Create, edit, and analyze PowerPoint presentations (.pptx files). Use when creating new presentations with HTML, editing existing slides, working with templates, or converting slides to images.
---

# PPTX Skill Documentation

This is a comprehensive guide for creating, editing, and analyzing PowerPoint presentations (.pptx files).

## Overview
- .pptx files are ZIP archives containing XML files and resources
- Different workflows available for different tasks (creation, editing, analysis)

## Reading & Analyzing Content

**Text Extraction:**
```bash
python -m markitdown path-to-file.pptx
```

**Raw XML Access (for advanced features):**
```bash
python ooxml/scripts/unpack.py <office_file> <output_dir>
```

Key file structures:
- `ppt/presentation.xml` - Main presentation metadata
- `ppt/slides/slide{N}.xml` - Individual slide contents
- `ppt/notesSlides/notesSlide{N}.xml` - Speaker notes
- `ppt/comments/` - Comments
- `ppt/theme/` - Theme and styling

## Creating New Presentations (Without Template)

**Workflow:**
1. Read `html2pptx.md` completely (mandatory)
2. Create HTML files for each slide (720pt × 405pt for 16:9)
3. Use `html2pptx.js` library to convert HTML to PowerPoint
4. Generate thumbnails for validation
5. Validate layout and regenerate if needed

**Design Requirements:**
- State your design approach before coding
- Use web-safe fonts only (Arial, Helvetica, Times New Roman, Georgia, Courier New, Verdana, Tahoma, Trebuchet MS, Impact)
- Ensure readable contrast and clear visual hierarchy
- Maintain consistency across slides

**Color Palette Examples:**
- Classic Blue: #1C2833, #2E4053, #AAB7B8, #F4F6F6
- Teal & Coral: #5EA8A7, #277884, #FE4447, #FFFFFF
- Burgundy Luxury: #5D1D2E, #951233, #C15937, #997929

## Editing Existing Presentations

**Workflow:**
1. Read `ooxml.md` completely (mandatory)
2. Unpack: `python ooxml/scripts/unpack.py <file> <dir>`
3. Edit XML files (primarily `ppt/slides/slide{N}.xml`)
4. Validate: `python ooxml/scripts/validate.py <dir> --original <file>`
5. Pack: `python ooxml/scripts/pack.py <dir> <output_file>`

## Creating from Template

**Workflow:**
1. Extract template text and create thumbnails
2. Analyze and save template inventory to `template-inventory.md`
3. Create presentation outline matching template inventory
4. Rearrange slides: `python scripts/rearrange.py template.pptx working.pptx 0,34,34,50,52`
5. Extract all text: `python scripts/inventory.py working.pptx text-inventory.json`
6. Generate replacement text and save to `replacement-text.json`
7. Apply replacements: `python scripts/replace.py working.pptx replacement-text.json output.pptx`

**Critical Template Rules:**
- Match layout structure to actual content (don't force content into mismatched layouts)
- Never use layouts with more placeholders than content
- Verify all shapes in replacement JSON exist in inventory
- Only include "paragraphs" field for shapes needing content
- All shapes without "paragraphs" will be automatically cleared

## Creating Thumbnail Grids

```bash
python scripts/thumbnail.py template.pptx [output_prefix]
python scripts/thumbnail.py template.pptx analysis --cols 4
```

Features:
- Default: 5 columns, max 30 slides per grid
- Custom columns: `--cols 3` to `--cols 6`
- Creates `thumbnails.jpg` (or numbered variants for large presentations)

## Converting Slides to Images

```bash
soffice --headless --convert-to pdf template.pptx
pdftoppm -jpeg -r 150 template.pdf slide
```

Options:
- `-r 150` - Sets resolution to 150 DPI
- `-f N -l N` - Convert specific page range

## Dependencies

Required installations:
- **markitdown**: `pip install "markitdown[pptx]"`
- **pptxgenjs**: `npm install -g pptxgenjs`
- **playwright**: `npm install -g playwright`
- **react-icons**: `npm install -g react-icons react react-dom`
- **sharp**: `npm install -g sharp`
- **LibreOffice**: `sudo apt-get install libreoffice`
- **Poppler**: `sudo apt-get install poppler-utils`
- **defusedxml**: `pip install defusedxml`

## Code Style Guidelines
- Write concise code
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements
