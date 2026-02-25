# PDF Forms Guide

This document provides comprehensive instructions for filling PDF forms, with two distinct workflows based on whether the PDF has fillable form fields.

## Quick Start

First, check if your PDF has fillable fields:
```bash
python scripts/check_fillable_fields <file.pdf>
```

Then follow the appropriate workflow below.

---

## Fillable Fields Workflow

If the PDF has native fillable form fields:

### 1. Extract Field Information
```bash
python scripts/extract_form_field_info.py <input.pdf> <field_info.json>
```

This creates a JSON file with field details including:
- `field_id`: Unique identifier
- `page`: Page number (1-based)
- `rect`: Bounding box `[left, bottom, right, top]` (PDF coordinates)
- `type`: "text", "checkbox", "radio_group", or "choice"
- `checked_value`/`unchecked_value` (for checkboxes)
- `radio_options` or `choice_options` (for multiple choice fields)

### 2. Create Field Values JSON
```json
[
  {
    "field_id": "last_name",
    "description": "The user's last name",
    "page": 1,
    "value": "Simpson"
  },
  {
    "field_id": "Checkbox12",
    "description": "Checkbox to be checked if user is 18+",
    "page": 1,
    "value": "/On"
  }
]
```

### 3. Fill the PDF
```bash
python scripts/fill_fillable_fields.py <input.pdf> <field_values.json> <output.pdf>
```

---

## Non-Fillable Fields Workflow

For PDFs without native form fields, follow these **4 mandatory steps in order**:

### Step 1: Visual Analysis

1. **Convert PDF to PNG images:**
   ```bash
   python scripts/convert_pdf_to_images.py <file.pdf> <output_directory>
   ```

2. **Analyze the images** to identify:
   - All form fields and data entry areas
   - Bounding boxes for labels and entry areas (must NOT overlap)
   - Field types (text, checkbox, etc.)

**Common Form Patterns:**

| Pattern | Description |
|---------|-------------|
| **Label inside box** | Entry area to the right of label |
| **Label before line** | Entry area above the line |
| **Label under line** | Entry area above the line (signatures/dates) |
| **Label above line** | Entry area from label bottom to line |
| **Checkboxes** | Target the square (□), NOT the text |

### Step 2: Create fields.json and Validation Images

Create `fields.json`:
```json
{
  "pages": [
    {
      "page_number": 1,
      "image_width": 612,
      "image_height": 792
    }
  ],
  "form_fields": [
    {
      "page_number": 1,
      "description": "The user's last name",
      "field_label": "Last name",
      "label_bounding_box": [30, 125, 95, 142],
      "entry_bounding_box": [100, 125, 280, 142],
      "entry_text": {
        "text": "Johnson",
        "font_size": 14,
        "font_color": "000000"
      }
    },
    {
      "page_number": 2,
      "description": "Checkbox for age verification",
      "field_label": "Yes",
      "label_bounding_box": [100, 525, 132, 540],
      "entry_bounding_box": [140, 525, 155, 540],
      "entry_text": {
        "text": "X"
      }
    }
  ]
}
```

Generate validation images for each page:
```bash
python scripts/create_validation_image.py <page_number> <fields.json> <input_image> <output_image>
```

### Step 3: Validate Bounding Boxes

**Automated check:**
```bash
python scripts/check_bounding_boxes.py <fields.json>
```

**Manual verification (CRITICAL):**
- ✓ Red rectangles cover ONLY input areas
- ✓ Red rectangles contain NO text
- ✓ Blue rectangles contain label text
- ✓ For checkboxes: red rectangle centered on checkbox square
- ✓ No overlapping bounding boxes

Iterate until all bounding boxes are accurate.

### Step 4: Add Annotations to PDF

```bash
python scripts/fill_pdf_form_with_annotations.py <input.pdf> <fields.json> <output.pdf>
```

---

## Key Requirements

⚠️ **CRITICAL CONSTRAINTS:**
- Label and entry bounding boxes MUST NOT intersect
- Entry boxes must be tall/wide enough for their text
- For checkboxes, target only the square, not the label text
- Complete all steps in order—do not skip ahead
- Visually inspect validation images before proceeding to Step 4
