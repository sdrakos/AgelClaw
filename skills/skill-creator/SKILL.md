---
name: skill-creator
description: Create new Claude skills. Use when building modular skill packages, writing SKILL.md files, organizing skill resources (scripts, references, assets), or packaging skills for distribution.
---

# Skill Creator

This is the official guide for creating effective skills in Anthropic's skills framework.

## Core Purpose
Skills are modular packages that extend Claude's capabilities with specialized knowledge, workflows, and tool integrations. They transform Claude into a specialized agent equipped with procedural knowledge.

## Key Principles

### 1. **Concise is Key**
- Context window is a shared resource
- Assume Claude is already very smart
- Only add information Claude doesn't have
- Prefer concise examples over verbose explanations

### 2. **Set Appropriate Degrees of Freedom**
- **High freedom**: Text-based instructions for multi-approach tasks
- **Medium freedom**: Pseudocode/scripts with parameters
- **Low freedom**: Specific scripts for fragile operations

### 3. **Anatomy of a Skill**
```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name + description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/ - Executable code
    ├── references/ - Documentation
    └── assets/ - Output files
```

## Bundled Resources

### Scripts (`scripts/`)
- Executable code (Python/Bash/etc.)
- For repeatedly rewritten code or deterministic reliability
- Example: `scripts/rotate_pdf.py`

### References (`references/`)
- Documentation loaded as needed
- Examples: schemas, APIs, company policies
- Keep SKILL.md lean by moving detailed info here
- **Best practice**: Avoid duplication between SKILL.md and references

### Assets (`assets/`)
- Files used in output (not loaded into context)
- Examples: templates, icons, fonts, boilerplate code

### What NOT to Include
- README.md, INSTALLATION_GUIDE.md, CHANGELOG.md
- Only include files needed for AI execution

## Progressive Disclosure Pattern

Three-level loading system:
1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - When skill triggers (<5k words)
3. **Bundled resources** - As needed by Claude

**Key patterns**:
- High-level guide with reference links
- Domain-specific organization
- Conditional details with links

## Skill Creation Process

### Step 1: Understanding with Concrete Examples
- Gather real usage examples
- Identify patterns and requirements
- Skip only if patterns are already clear

### Step 2: Planning Reusable Contents
- Analyze each example
- Identify reusable scripts, references, assets

### Step 3: Initializing the Skill
```bash
scripts/init_skill.py <skill-name> --path <output-directory>
```
- Creates directory structure
- Generates SKILL.md template with frontmatter
- Creates example resource directories

### Step 4: Editing the Skill

**SKILL.md Frontmatter**:
```yaml
name: Skill Name
description: What it does + when to use it (triggers are here, not in body)
```

**SKILL.md Body**:
- Write instructions for using the skill
- Use imperative/infinitive form
- Keep under 500 lines
- Link to references when needed

### Step 5: Packaging
```bash
scripts/package_skill.py <path/to/skill-folder>
scripts/package_skill.py <path/to/skill-folder> ./dist  # optional output dir
```
- Validates the skill automatically
- Creates .skill file (zip with .skill extension)
- Checks YAML, naming, structure, references

### Step 6: Iterate
- Test skill on real tasks
- Notice inefficiencies
- Update SKILL.md or bundled resources
- Retest

## Important Guidelines

- **Frontmatter is critical** - Contains the only fields Claude reads to determine when to use the skill
- **Include "when to use" info in description** - Not in body (body only loads after triggering)
- **Avoid deeply nested references** - Keep one level deep from SKILL.md
- **Structure long files** - Add table of contents for files >100 lines
- **Test scripts** - Run representative samples to ensure they work
