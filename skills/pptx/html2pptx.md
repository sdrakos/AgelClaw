# HTML to PowerPoint Guide

This is a comprehensive guide for converting HTML slides to PowerPoint presentations using the `html2pptx.js` library and PptxGenJS.

## Creating HTML Slides

**Layout Dimensions:**
- 16:9 (default): `width: 720pt; height: 405pt`
- 4:3: `width: 720pt; height: 540pt`
- 16:10: `width: 720pt; height: 450pt`

**Critical Text Rules:**
- ✅ ALL text MUST be in `<p>`, `<h1>-<h6>`, `<ul>`, or `<ol>` tags
- ❌ Text in `<div>` or `<span>` alone will NOT appear
- ✅ Use web-safe fonts only (Arial, Helvetica, Georgia, Courier New, etc.)
- ❌ Never use manual bullet points (•, -, *)—use `<ul>` or `<ol>`

**Supported Elements:**
- Text: `<p>`, `<h1>-<h6>`, `<ul>`, `<ol>`
- Formatting: `<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<span>`
- Shapes: `<div>` with background/border
- Images: `<img>`
- Placeholders: `class="placeholder"` for charts

**Shape Styling (DIV only):**
- Backgrounds: `background` or `background-color`
- Borders: `border`, `border-left`, `border-right`, etc.
- Border radius: `border-radius: 25%` or `border-radius: 8pt`
- Box shadows: `box-shadow: 2px 2px 8px rgba(0,0,0,0.3)` (outer only)

## Using the html2pptx Library

**Dependencies:** `pptxgenjs`, `playwright`, `sharp` (globally installed)

**Basic Usage:**
```javascript
const pptxgen = require('pptxgenjs');
const html2pptx = require('./html2pptx');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_16x9';

const { slide, placeholders } = await html2pptx('slide.html', pptx);
await pptx.writeFile('output.pptx');
```

**API Reference:**
```javascript
await html2pptx(htmlFile, pres, options)
```

Returns:
```javascript
{
  slide: pptxgenSlide,
  placeholders: [
    { id, x, y, w, h },
    ...
  ]
}
```

**Validation:** Automatically checks dimensions, overflow, CSS gradients, and styling rules.

## Using PptxGenJS

⚠️ **CRITICAL: Never use `#` prefix with hex colors** — causes file corruption
- ✅ Correct: `color: "FF0000"`
- ❌ Wrong: `color: "#FF0000"`

**Adding Images:**
```javascript
const imgWidth = 1860, imgHeight = 1519;
const aspectRatio = imgWidth / imgHeight;
const h = 3, w = h * aspectRatio;
const x = (10 - w) / 2;

slide.addImage({ path: "chart.png", x, y: 1.5, w, h });
```

**Adding Charts:**

*Bar Chart:*
```javascript
slide.addChart(pptx.charts.BAR, [{
  name: "Sales",
  labels: ["Q1", "Q2", "Q3", "Q4"],
  values: [4500, 5500, 6200, 7100]
}], {
  ...placeholders[0],
  barDir: 'col',
  showTitle: true,
  title: 'Quarterly Sales',
  showCatAxisTitle: true,
  catAxisTitle: 'Quarter',
  showValAxisTitle: true,
  valAxisTitle: 'Sales ($000s)',
  chartColors: ["4472C4"]
});
```

*Scatter Chart:*
```javascript
// First series = X values, subsequent = Y values
slide.addChart(pptx.charts.SCATTER, [
  { name: 'X-Axis', values: allXValues },
  { name: 'Series 1', values: yValues1 },
  { name: 'Series 2', values: yValues2 }
], { lineSize: 0, lineDataSymbol: 'circle' });
```

*Pie Chart:*
```javascript
slide.addChart(pptx.charts.PIE, [{
  name: "Market Share",
  labels: ["Product A", "Product B", "Other"],
  values: [35, 45, 20]
}], { showPercent: true, showLegend: true });
```

**Adding Tables:**
```javascript
slide.addTable([
  ["Header 1", "Header 2", "Header 3"],
  ["Row 1, Col 1", "Row 1, Col 2", "Row 1, Col 3"],
  ["Row 2, Col 1", "Row 2, Col 2", "Row 2, Col 3"]
], {
  x: 0.5, y: 1, w: 9, h: 3,
  border: { pt: 1, color: "999999" },
  fill: { color: "F1F1F1" }
});
```

**Table Options:**
- `colW` - Column widths (array)
- `rowH` - Row heights (array)
- `align` - "left", "center", "right"
- `valign` - "top", "middle", "bottom"
- `fontSize` - Text size
