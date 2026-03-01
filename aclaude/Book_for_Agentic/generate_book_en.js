const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, PageBreak,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType,
  AlignmentType, PageNumber, Footer, Header,
  LevelFormat, convertInchesToTwip,
} = require("docx");

const CHAPTERS_DIR = path.join(__dirname, "chapters_en");
const OUTPUT_DIR = path.join(__dirname, "chapters_docs");

const FONT = "Calibri";
const CODE_FONT = "Consolas";
const FONT_SIZE = 22; // 11pt in half-points
const CODE_FONT_SIZE = 18; // 9pt
const H1_SIZE = 36; // 18pt
const H2_SIZE = 28; // 14pt
const H3_SIZE = 24; // 12pt

// Chapter files in order
const CHAPTER_FILES = [
  "00-prologue.md",
  "01-ti-einai-agentic-ai.md",
  "02-i-python-pou-xreiazeste.md",
  "03-egkatastasi-kai-prota-vimata.md",
  "04-o-protos-agent-openai.md",
  "05-ergaleia-ta-xeria-tou-agent.md",
  "06-structured-output.md",
  "07-context.md",
  "08-handoffs.md",
  "09-multi-agent.md",
  "10-guardrails.md",
  "11-streaming.md",
  "12-sessions.md",
  "13-human-in-the-loop.md",
  "14-mcp.md",
  "15-voice-realtime.md",
  "16-models.md",
  "17-claude-sdk-intro.md",
  "18-skills.md",
  "19-mcp-claude.md",
  "20-subagents.md",
  "21-parallel.md",
  "22-resume.md",
  "23-events.md",
  "24-filesystem-agents.md",
  "25-comparison.md",
  "26-production.md",
  "27-security.md",
  "28-project-researcher.md",
  "29-project-customer-service.md",
  "30-project-daemon.md",
  "31-project-voice.md",
  "32-future.md",
  "appendix-a-openai-api.md",
  "appendix-b-claude-api.md",
  "appendix-c-troubleshooting.md",
  "appendix-d-bibliography.md",
];

// Part titles for section breaks
const PARTS = {
  "00-prologue.md": null,
  "01-ti-einai-agentic-ai.md": "PART I\nThe Foundations",
  "04-o-protos-agent-openai.md": "PART II\nOpenAI Agents SDK in Depth",
  "17-claude-sdk-intro.md": "PART III\nClaude Agent SDK in Depth",
  "25-comparison.md": "PART IV\nComparison and Advanced Topics",
  "28-project-researcher.md": "PART V\nReal-World Projects",
  "32-future.md": "PART VI\nEpilogue and Future",
  "appendix-a-openai-api.md": "Appendices",
};

// --- Markdown Parsing ---

function parseInlineFormatting(text) {
  const runs = [];
  // Process inline code, bold, italic
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|[^`*]+)/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    const segment = match[0];
    if (segment.startsWith("`") && segment.endsWith("`")) {
      runs.push(new TextRun({
        text: segment.slice(1, -1),
        font: CODE_FONT,
        size: CODE_FONT_SIZE,
        shading: { type: ShadingType.CLEAR, color: "auto", fill: "E8E8E8" },
      }));
    } else if (segment.startsWith("**") && segment.endsWith("**")) {
      runs.push(new TextRun({ text: segment.slice(2, -2), bold: true, font: FONT, size: FONT_SIZE }));
    } else if (segment.startsWith("*") && segment.endsWith("*") && !segment.startsWith("**")) {
      runs.push(new TextRun({ text: segment.slice(1, -1), italics: true, font: FONT, size: FONT_SIZE }));
    } else if (segment.length > 0) {
      runs.push(new TextRun({ text: segment, font: FONT, size: FONT_SIZE }));
    }
  }
  return runs.length > 0 ? runs : [new TextRun({ text, font: FONT, size: FONT_SIZE })];
}

function parseMarkdownToElements(content, numbering) {
  const lines = content.split("\n");
  const elements = [];
  let i = 0;
  let inCodeBlock = false;
  let codeLines = [];
  let codeLang = "";

  while (i < lines.length) {
    const line = lines[i];

    // Code block start/end
    if (line.trimStart().startsWith("```")) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeLang = line.trimStart().slice(3).trim();
        codeLines = [];
        i++;
        continue;
      } else {
        // End code block - emit code paragraph
        inCodeBlock = false;
        if (codeLang) {
          elements.push(new Paragraph({
            children: [new TextRun({ text: codeLang, font: CODE_FONT, size: 16, color: "666666", italics: true })],
            spacing: { before: 120, after: 0 },
          }));
        }
        for (let ci = 0; ci < codeLines.length; ci++) {
          elements.push(new Paragraph({
            children: [new TextRun({
              text: codeLines[ci] || " ",
              font: CODE_FONT,
              size: CODE_FONT_SIZE,
              color: "1A1A1A",
            })],
            shading: { type: ShadingType.CLEAR, color: "auto", fill: "F5F5F5" },
            spacing: { before: 0, after: 0, line: 260 },
            indent: { left: convertInchesToTwip(0.3) },
          }));
        }
        elements.push(new Paragraph({ children: [], spacing: { before: 60, after: 120 } }));
        i++;
        continue;
      }
    }

    if (inCodeBlock) {
      codeLines.push(line);
      i++;
      continue;
    }

    // Headings
    if (line.startsWith("# ")) {
      elements.push(new Paragraph({
        children: [new TextRun({ text: line.slice(2).trim(), font: FONT, size: H1_SIZE, bold: true, color: "1B3A5C" })],
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 360, after: 200 },
      }));
      i++;
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(new Paragraph({
        children: [new TextRun({ text: line.slice(3).trim(), font: FONT, size: H2_SIZE, bold: true, color: "2C5F8A" })],
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 300, after: 160 },
      }));
      i++;
      continue;
    }
    if (line.startsWith("### ")) {
      elements.push(new Paragraph({
        children: [new TextRun({ text: line.slice(4).trim(), font: FONT, size: H3_SIZE, bold: true, color: "3D7AB5" })],
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 240, after: 120 },
      }));
      i++;
      continue;
    }

    // Table detection
    if (line.includes("|") && line.trim().startsWith("|")) {
      const tableRows = [];
      while (i < lines.length && lines[i].includes("|") && lines[i].trim().startsWith("|")) {
        const row = lines[i].trim();
        // Skip separator rows (|---|---|)
        if (/^\|[\s-:|]+\|$/.test(row)) {
          i++;
          continue;
        }
        const cells = row.split("|").filter((c, idx, arr) => idx > 0 && idx < arr.length - 1).map(c => c.trim());
        tableRows.push(cells);
        i++;
      }
      if (tableRows.length > 0) {
        const maxCols = Math.max(...tableRows.map(r => r.length));
        const colWidth = Math.floor(9360 / maxCols);
        const table = new Table({
          columnWidths: Array(maxCols).fill(colWidth),
          rows: tableRows.map((row, rowIdx) => new TableRow({
            children: Array.from({ length: maxCols }, (_, ci) => new TableCell({
              children: [new Paragraph({
                children: [new TextRun({
                  text: row[ci] || "",
                  font: FONT,
                  size: FONT_SIZE - 2,
                  bold: rowIdx === 0,
                })],
                spacing: { before: 40, after: 40 },
              })],
              width: { size: colWidth, type: WidthType.DXA },
              shading: rowIdx === 0 ? { type: ShadingType.CLEAR, color: "auto", fill: "D6E4F0" } : undefined,
              borders: {
                top: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                bottom: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                left: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                right: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
              },
              margins: { top: 40, bottom: 40, left: 80, right: 80 },
            })),
          })),
        });
        elements.push(table);
        elements.push(new Paragraph({ children: [], spacing: { before: 60, after: 120 } }));
      }
      continue;
    }

    // Simple table format (without | prefix): "Key -- Value -- Value"
    if (line.includes(" -- ") && !line.startsWith("#")) {
      const parts = line.split(" -- ").map(p => p.trim());
      if (parts.length >= 2) {
        // Check if next lines also have --
        const simpleTableRows = [parts];
        let j = i + 1;
        while (j < lines.length && lines[j].includes(" -- ")) {
          simpleTableRows.push(lines[j].split(" -- ").map(p => p.trim()));
          j++;
        }
        if (simpleTableRows.length > 1) {
          const maxCols = Math.max(...simpleTableRows.map(r => r.length));
          const colWidth = Math.floor(9360 / maxCols);
          const table = new Table({
            columnWidths: Array(maxCols).fill(colWidth),
            rows: simpleTableRows.map((row, rowIdx) => new TableRow({
              children: Array.from({ length: maxCols }, (_, ci) => new TableCell({
                children: [new Paragraph({
                  children: parseInlineFormatting(row[ci] || ""),
                  spacing: { before: 40, after: 40 },
                })],
                width: { size: colWidth, type: WidthType.DXA },
                shading: rowIdx === 0 ? { type: ShadingType.CLEAR, color: "auto", fill: "D6E4F0" } : undefined,
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "AAAAAA" },
                },
                margins: { top: 40, bottom: 40, left: 80, right: 80 },
              })),
            })),
          });
          elements.push(table);
          elements.push(new Paragraph({ children: [], spacing: { before: 60, after: 120 } }));
          i = j;
          continue;
        }
      }
    }

    // Bullet list
    if (line.match(/^[-*]\s+/)) {
      const text = line.replace(/^[-*]\s+/, "").trim();
      elements.push(new Paragraph({
        children: parseInlineFormatting(text),
        numbering: { reference: "bullet-list", level: 0 },
        spacing: { before: 40, after: 40 },
        indent: { left: convertInchesToTwip(0.5) },
      }));
      i++;
      continue;
    }

    // Numbered list
    if (line.match(/^\d+\.\s+/)) {
      const text = line.replace(/^\d+\.\s+/, "").trim();
      elements.push(new Paragraph({
        children: parseInlineFormatting(text),
        numbering: { reference: "numbered-list", level: 0 },
        spacing: { before: 40, after: 40 },
        indent: { left: convertInchesToTwip(0.5) },
      }));
      i++;
      continue;
    }

    // Horizontal rule
    if (line.match(/^-{3,}$/) || line.match(/^\*{3,}$/)) {
      elements.push(new Paragraph({
        children: [new TextRun({ text: "_______________________________________________", color: "CCCCCC", font: FONT, size: 16 })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 200, after: 200 },
      }));
      i++;
      continue;
    }

    // Empty line
    if (line.trim() === "") {
      i++;
      continue;
    }

    // Regular paragraph
    elements.push(new Paragraph({
      children: parseInlineFormatting(line),
      spacing: { before: 60, after: 60, line: 320 },
    }));
    i++;
  }

  return elements;
}

// --- Cover Page ---
function createCoverPage() {
  return [
    new Paragraph({ children: [], spacing: { before: 4000 } }),
    new Paragraph({
      children: [new TextRun({
        text: "The Bible of",
        font: FONT,
        size: 48,
        color: "1B3A5C",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 100 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "Agentic AI Systems",
        font: FONT,
        size: 60,
        bold: true,
        color: "1B3A5C",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "Building Intelligent Agents with Python",
        font: FONT,
        size: 28,
        italics: true,
        color: "4A4A4A",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "A practical guide with the OpenAI Agents SDK and the Claude Agent SDK",
        font: FONT,
        size: 22,
        color: "666666",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 1600 },
    }),
    new Paragraph({
      children: [new TextRun({ text: "_______________________________________________", color: "1B3A5C", font: FONT, size: 16 })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 600 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "Dr Stefanos Drakos",
        font: FONT,
        size: 32,
        bold: true,
        color: "333333",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "2026",
        font: FONT,
        size: 24,
        color: "666666",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

// --- Copyright Page ---
function createCopyrightPage() {
  const lines = [
    { text: "Agentic AI: Building Intelligent Agents with Python", bold: true, size: 22 },
    { text: "" },
    { text: "Copyright \u00A9 2026 Dr. Stefanos Drakos" },
    { text: "" },
    { text: "All rights reserved. No part of this publication may be reproduced, distributed, or transmitted in any form or by any means, including photocopying, recording, or other electronic or mechanical methods, without the prior written permission of the author." },
    { text: "" },
    { text: "The code examples in this book are provided for educational purposes. They are released under the MIT License unless otherwise noted." },
    { text: "" },
    { text: "Python is a registered trademark of the Python Software Foundation. OpenAI is a trademark of OpenAI, Inc. Claude and Anthropic are trademarks of Anthropic, PBC. Amazon Web Services and related marks are trademarks of Amazon.com, Inc." },
    { text: "" },
    { text: "While every precaution has been taken in the preparation of this book, the author assumes no responsibility for errors or omissions, or for damages resulting from the use of the information contained herein." },
    { text: "" },
    { text: "SDK versions covered:", bold: true },
    { text: "\u2022  OpenAI Agents SDK 0.1.x" },
    { text: "\u2022  Claude Agent SDK 0.1.x" },
    { text: "\u2022  Python 3.11+" },
    { text: "" },
    { text: "First Edition, 2026" },
  ];

  const elems = [new Paragraph({ children: [], spacing: { before: 6000 } })];
  for (const line of lines) {
    if (line.text === "") {
      elems.push(new Paragraph({ children: [], spacing: { before: 60, after: 60 } }));
    } else {
      elems.push(new Paragraph({
        children: [new TextRun({
          text: line.text,
          font: FONT,
          size: line.size || 18,
          bold: line.bold || false,
          color: "444444",
        })],
        spacing: { before: 20, after: 20, line: 280 },
      }));
    }
  }
  elems.push(new Paragraph({ children: [new PageBreak()] }));
  return elems;
}

// --- About the Author Page ---
function createAboutAuthorPage() {
  return [
    new Paragraph({ children: [], spacing: { before: 3000 } }),
    new Paragraph({
      children: [new TextRun({
        text: "About the Author",
        font: FONT,
        size: 36,
        bold: true,
        color: "1B3A5C",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({
      children: [new TextRun({ text: "_______________________________________________", color: "1B3A5C", font: FONT, size: 16 })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "Dr. Stefanos Drakos is a software engineer and AI systems architect based in Greece. He is the creator of AgelClaw, an open-source autonomous AI assistant that combines the Claude Agent SDK and OpenAI Agents SDK with persistent memory, skills, and multi-agent orchestration.",
        font: FONT,
        size: FONT_SIZE,
        color: "333333",
      })],
      spacing: { before: 60, after: 120, line: 360 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "His work focuses on building practical AI agent systems for real-world applications, from autonomous daemons and multi-provider routing architectures to voice-enabled agent workflows.",
        font: FONT,
        size: FONT_SIZE,
        color: "333333",
      })],
      spacing: { before: 60, after: 120, line: 360 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "Contact: sdrakos@agel.ai",
        font: FONT,
        size: FONT_SIZE,
        color: "2C5F8A",
      })],
      spacing: { before: 200, after: 40 },
    }),
    new Paragraph({
      children: [new TextRun({
        text: "GitHub: github.com/sdrakos",
        font: FONT,
        size: FONT_SIZE,
        color: "2C5F8A",
      })],
      spacing: { before: 40, after: 40 },
    }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

// --- Part Title Page ---
function createPartPage(partTitle) {
  const lines = partTitle.split("\n");
  const elems = [
    new Paragraph({ children: [], spacing: { before: 3000 } }),
  ];
  for (const line of lines) {
    elems.push(new Paragraph({
      children: [new TextRun({
        text: line,
        font: FONT,
        size: line.startsWith("PART") || line === "Appendices" ? 44 : 36,
        bold: true,
        color: "1B3A5C",
      })],
      alignment: AlignmentType.CENTER,
      spacing: { after: 100 },
    }));
  }
  elems.push(new Paragraph({ children: [], spacing: { before: 1000 } }));
  elems.push(new Paragraph({ children: [new PageBreak()] }));
  return elems;
}

// --- Main ---
async function generateBook() {
  console.log("Generating English book...");

  const allChildren = [];

  // Cover page
  allChildren.push(...createCoverPage());

  // Copyright page
  allChildren.push(...createCopyrightPage());

  // TOC page - generated from TOC_en.md
  allChildren.push(new Paragraph({
    children: [new TextRun({ text: "Table of Contents", font: FONT, size: 44, bold: true, color: "1B3A5C" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 200, after: 400 },
  }));
  allChildren.push(new Paragraph({
    children: [new TextRun({ text: "_______________________________________________", color: "1B3A5C", font: FONT, size: 16 })],
    alignment: AlignmentType.CENTER,
    spacing: { after: 300 },
  }));

  // Parse TOC_en.md for content
  const tocPath = path.join(__dirname, "TOC_en.md");
  if (fs.existsSync(tocPath)) {
    const tocContent = fs.readFileSync(tocPath, "utf-8");
    const tocLines = tocContent.split("\n");
    for (const tocLine of tocLines) {
      // Skip the main title and subtitle
      if (tocLine.startsWith("# ") || tocLine.startsWith("## A Practical Guide")) continue;
      // Skip horizontal rules and empty lines
      if (tocLine.trim() === "" || tocLine.trim() === "---") continue;
      // Skip the page estimate table at the end
      if (tocLine.startsWith("## Estimated") || tocLine.startsWith("| Part") || tocLine.startsWith("|---") || tocLine.startsWith("| **Total")) continue;
      if (/^\|\s*Part/.test(tocLine) || /^\|\s*Append/.test(tocLine)) continue;

      // Part headings (## PART)
      if (tocLine.startsWith("## PART")) {
        const partText = tocLine.replace("## ", "").trim();
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: partText, font: FONT, size: 26, bold: true, color: "1B3A5C" })],
          spacing: { before: 300, after: 100 },
        }));
        continue;
      }

      // Prologue
      if (tocLine.startsWith("## Prologue")) {
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: "Prologue", font: FONT, size: 24, bold: true, color: "2C5F8A" })],
          spacing: { before: 200, after: 60 },
        }));
        continue;
      }

      // Appendices section header
      if (tocLine.startsWith("## Appendices")) {
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: "Appendices", font: FONT, size: 26, bold: true, color: "1B3A5C" })],
          spacing: { before: 300, after: 100 },
        }));
        continue;
      }

      // Chapter titles (### Chapter or ### Appendix)
      if (tocLine.startsWith("### ")) {
        const chTitle = tocLine.replace("### ", "").trim();
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: chTitle, font: FONT, size: 22, bold: true, color: "2C5F8A" })],
          spacing: { before: 140, after: 40 },
          indent: { left: convertInchesToTwip(0.3) },
        }));
        continue;
      }

      // Section entries (1.1, 2.3, etc.)
      if (/^\d+\.\d+\s/.test(tocLine.trim()) || /^[A-D]\.\d+\s/.test(tocLine.trim())) {
        const secText = tocLine.trim();
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: secText, font: FONT, size: 20, color: "444444" })],
          spacing: { before: 20, after: 20 },
          indent: { left: convertInchesToTwip(0.7) },
        }));
        continue;
      }

      // Description lines
      if (tocLine.trim().length > 0 && !tocLine.startsWith("#") && !tocLine.startsWith("|")) {
        allChildren.push(new Paragraph({
          children: [new TextRun({ text: tocLine.trim(), font: FONT, size: 20, italics: true, color: "666666" })],
          spacing: { before: 20, after: 20 },
          indent: { left: convertInchesToTwip(0.5) },
        }));
      }
    }
  }

  allChildren.push(new Paragraph({ children: [new PageBreak()] }));

  // Process each chapter
  for (const file of CHAPTER_FILES) {
    const filePath = path.join(CHAPTERS_DIR, file);
    if (!fs.existsSync(filePath)) {
      console.log(`  SKIP: ${file} (not found)`);
      continue;
    }

    // Part title page
    if (PARTS[file]) {
      allChildren.push(...createPartPage(PARTS[file]));
    }

    console.log(`  Processing: ${file}`);
    const content = fs.readFileSync(filePath, "utf-8");
    const elements = parseMarkdownToElements(content, null);
    allChildren.push(...elements);

    // Page break after each chapter
    allChildren.push(new Paragraph({ children: [new PageBreak()] }));
  }

  // About the Author (back matter)
  allChildren.push(...createAboutAuthorPage());

  const doc = new Document({
    styles: {
      default: {
        document: {
          run: { font: FONT, size: FONT_SIZE, color: "1A1A1A" },
          paragraph: { spacing: { line: 320 } },
        },
        heading1: {
          run: { font: FONT, size: H1_SIZE, bold: true, color: "1B3A5C" },
          paragraph: { spacing: { before: 360, after: 200 } },
        },
        heading2: {
          run: { font: FONT, size: H2_SIZE, bold: true, color: "2C5F8A" },
          paragraph: { spacing: { before: 300, after: 160 } },
        },
        heading3: {
          run: { font: FONT, size: H3_SIZE, bold: true, color: "3D7AB5" },
          paragraph: { spacing: { before: 240, after: 120 } },
        },
      },
    },
    numbering: {
      config: [
        {
          reference: "bullet-list",
          levels: [{
            level: 0,
            format: LevelFormat.BULLET,
            text: "\u2022",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.5), hanging: convertInchesToTwip(0.25) } } },
          }],
        },
        {
          reference: "numbered-list",
          levels: [{
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: convertInchesToTwip(0.5), hanging: convertInchesToTwip(0.25) } } },
          }],
        },
      ],
    },
    features: { updateFields: true },
    sections: [{
      properties: {
        page: {
          margin: {
            top: convertInchesToTwip(1),
            right: convertInchesToTwip(1),
            bottom: convertInchesToTwip(1),
            left: convertInchesToTwip(1.2),
          },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            children: [new TextRun({
              text: "The Bible of Agentic AI Systems",
              font: FONT,
              size: 16,
              color: "999999",
              italics: true,
            })],
            alignment: AlignmentType.RIGHT,
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            children: [
              new TextRun({ text: "Dr Stefanos Drakos", font: FONT, size: 16, color: "999999" }),
              new TextRun({ text: "    —    ", font: FONT, size: 16, color: "CCCCCC" }),
              new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "999999" }),
            ],
            alignment: AlignmentType.CENTER,
          })],
        }),
      },
      children: allChildren,
    }],
  });

  // Generate full book
  const fullPath = path.join(OUTPUT_DIR, "The_Bible_of_Agentic_AI_Systems.docx");
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(fullPath, buffer);
  console.log(`\nBook saved: ${fullPath}`);
  console.log(`Size: ${(buffer.length / 1024 / 1024).toFixed(1)} MB`);
}

generateBook().catch(err => {
  console.error("Error:", err.message);
  process.exit(1);
});
