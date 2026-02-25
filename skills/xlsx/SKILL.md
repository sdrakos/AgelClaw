---
name: xlsx
description: Create, edit, and analyze Excel spreadsheets (.xlsx files). Use when working with financial models, data analysis, formulas, formatting, or Excel-specific features. Follows industry-standard color coding and formula best practices.
---

# XLSX Skill Documentation

This is Anthropic's official skill for comprehensive spreadsheet creation, editing, and analysis.

## Core Requirements

### All Excel Files Must Have:
- **Zero formula errors** (#REF!, #DIV/0!, #VALUE!, #N/A, #NAME?)
- **Preserved templates** - Match existing format when updating files
- Existing template conventions **always override** these guidelines

## Financial Model Standards

### Color Coding (Industry Standard)
- **Blue text (RGB: 0,0,255)**: Hardcoded inputs and user-changeable numbers
- **Black text (RGB: 0,0,0)**: ALL formulas and calculations
- **Green text (RGB: 0,128,0)**: Internal worksheet links
- **Red text (RGB: 255,0,0)**: External file links
- **Yellow background (RGB: 255,255,0)**: Key assumptions needing attention

### Number Formatting
- **Years**: Text strings ("2024", not "2,024")
- **Currency**: $#,##0 format with units in headers ("Revenue ($mm)")
- **Zeros**: Display as "-" using format rules
- **Percentages**: 0.0% format (one decimal)
- **Multiples**: 0.0x format (e.g., "2.5x")
- **Negatives**: Use parentheses (123) not minus -123

### Formula Rules
- Use cell references, not hardcoded values: `=B5*(1+$B$6)` not `=B5*1.05`
- Place ALL assumptions in separate cells
- Document hardcoded values with sources (e.g., "Source: Company 10-K, FY2024, Page 45")

## CRITICAL: Use Formulas, Not Hardcoded Values

❌ **WRONG** - Calculating in Python and hardcoding:
```python
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000
```

✅ **CORRECT** - Using Excel formulas:
```python
sheet['B10'] = '=SUM(B2:B9)'
```

## Tools & Libraries

**pandas**: Data analysis, bulk operations, simple exports
```python
import pandas as pd
df = pd.read_excel('file.xlsx')
df.to_excel('output.xlsx', index=False)
```

**openpyxl**: Formulas, formatting, Excel-specific features
```python
from openpyxl import load_workbook
wb = load_workbook('existing.xlsx')
sheet = wb.active
sheet['A1'] = '=SUM(A2:A10)'
wb.save('modified.xlsx')
```

## Formula Recalculation (MANDATORY)

After creating/modifying files with formulas, recalculate using the provided `recalc.py`:

```bash
python recalc.py output.xlsx 30
```

The script:
- Automatically sets up LibreOffice on first run
- Recalculates all formulas in all sheets
- Scans for Excel errors
- Returns JSON with error locations and counts
- Works on Linux and macOS

**Example output**:
```json
{
  "status": "success",
  "total_errors": 0,
  "total_formulas": 42,
  "error_summary": {}
}
```

## Verification Checklist

- ✓ Test 2-3 sample references before full build
- ✓ Confirm column mapping (column 64 = BL)
- ✓ Remember Excel rows are 1-indexed (DataFrame row 5 = Excel row 6)
- ✓ Check for NaN values with `pd.notna()`
- ✓ Verify no division by zero (#DIV/0!)
- ✓ Verify correct cell references (#REF!)
- ✓ Use proper cross-sheet format (Sheet1!A1)

## Code Style Guidelines

**Python code**: Write minimal, concise code without unnecessary comments or print statements

**Excel files**: Add comments explaining complex formulas, document data sources, include notes for key calculations
