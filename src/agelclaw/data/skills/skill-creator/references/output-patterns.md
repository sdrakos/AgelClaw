# Output Patterns Guide

This document provides two key patterns for ensuring consistent, high-quality output in skills:

## 1. Template Pattern

Use templates to specify output format, matching strictness to your needs:

### For Strict Requirements (API responses, data formats):
```markdown
## Report structure

ALWAYS use this exact template structure:

# [Analysis Title]

## Executive summary
[One-paragraph overview of key findings]

## Key findings
- Finding 1 with supporting data
- Finding 2 with supporting data
- Finding 3 with supporting data

## Recommendations
1. Specific actionable recommendation
2. Specific actionable recommendation
```

### For Flexible Guidance (when adaptation is useful):
```markdown
## Report structure

Here is a sensible default format, but use your best judgment:

# [Analysis Title]

## Executive summary
[Overview]

## Key findings
[Adapt sections based on what you discover]

## Recommendations
[Tailor to the specific context]

Adjust sections as needed for the specific analysis type.
```

## 2. Examples Pattern

Provide input/output pairs to demonstrate desired style and detail level:

```markdown
## Commit message format

Generate commit messages following these examples:

**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
Add login endpoint and token validation middleware

**Example 2:**
Input: Fixed bug where dates displayed incorrectly in reports
Output: fix(reports): correct date formatting in timezone conversion
Use UTC timestamps consistently across report generation

Follow this style: type(scope): brief description, then detailed explanation.
```

**Key takeaway:** Examples help Claude understand desired style and detail more clearly than descriptions alone.
