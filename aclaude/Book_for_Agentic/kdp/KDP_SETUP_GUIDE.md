# KDP Setup Guide — Agentic AI Book

## Step-by-step οδηγός για publish στο Amazon KDP

---

## 1. Λογαριασμός KDP

1. Πήγαινε στο **https://kdp.amazon.com**
2. Sign in με Amazon account (ή δημιούργησε νέο)
3. Συμπλήρωσε **tax information** (W-8BEN για non-US authors):
   - Name: Stefanos Drakos
   - Country: Greece
   - TIN: ΑΦΜ σου
   - Claim tax treaty benefits: Yes → Greece → Article 12, 0% rate on royalties
4. Πρόσθεσε **bank account** (IBAN) για πληρωμές royalties
5. Royalties πληρώνονται 60 ημέρες μετά το τέλος κάθε μήνα

---

## 2. Τι θα δημοσιεύσεις

### Ebook (Kindle) — Κάνε πρώτα αυτό
- Format: **DOCX** (ήδη έχεις τον generator)
- Cover: **1600 x 2560 pixels** (JPG/TIFF, sRGB)
- Pricing: $29.99 → 70% royalty = ~$20.99 ανά πώληση
- DRM: Ενεργοποίησε (Digital Rights Management)
- KDP Select: **Ναι** (90 ημέρες exclusive, αλλά σε βάζει στο Kindle Unlimited)

### Paperback — Κάνε μετά
- Format: **PDF** (εσωτερικό) + **Cover PDF** (εξώφυλλο)
- Trim size: **7.5" x 9.25"** (ιδανικό για technical books, αρκετός χώρος για code)
- Paper: **White** (όχι cream — τα code blocks φαίνονται καλύτερα)
- Cover: Matte finish (πιο premium αίσθηση)
- Pricing: $44.99 (printing cost ~$8-10 για ~340 σελίδες, 60% royalty)

---

## 3. Metadata για το KDP Listing

### Title & Subtitle
```
Title:    Agentic AI
Subtitle: Building Intelligent Agents with Python — A Practical Guide with the OpenAI Agents SDK and the Claude Agent SDK
```

**Εναλλακτικός τίτλος** (πιο bold):
```
Title:    The Bible of Agentic AI Systems
Subtitle: Building Intelligent Agents with Python
```

> Σύσταση: Ο πρώτος τίτλος είναι καλύτερος για Amazon search. Το "Bible of" μπορεί
> να φαίνεται presumptuous σε αγγλόφωνο κοινό. Κράτα τον ως εσωτερικό branding
> αν θέλεις, αλλά στο listing χρησιμοποίησε τον πρώτο.

### Author
```
Author:         Dr. Stefanos Drakos
Contributors:   (κενό)
```

### Description (HTML — copy-paste στο KDP)

Βλέπε αρχείο: `kdp/book_description.html`

### Keywords (7 max — κρίσιμο για discoverability)

```
1. AI agents Python
2. OpenAI Agents SDK
3. Claude Agent SDK
4. multi-agent systems
5. agentic AI programming
6. LLM agent framework
7. autonomous AI systems
```

### Categories (2 BISAC categories)

```
Category 1: Computers > Programming > Open Source
Category 2: Computers > Artificial Intelligence > Natural Language Processing
```

Εναλλακτικά:
```
Category 1: Computers > Languages & Tools > Python
Category 2: Computers > Artificial Intelligence > General
```

> Tip: Αν δεν βρεις ακριβώς αυτές, ψάξε στο KDP category browser.
> Μετά το publish, μπορείς να ζητήσεις πρόσθετες categories μέσω KDP Support.

### Language & Other
```
Language:       English
Publication date: (leave blank — auto-sets to publish date)
Edition:        1st Edition
Series:         (none)
ISBN:           (use free Amazon ASIN — no need to buy ISBN for KDP)
```

---

## 4. Pricing Strategy

### Ebook
| Marketplace | Price | Royalty (70%) | Notes |
|-------------|-------|---------------|-------|
| Amazon.com (US) | $29.99 | ~$20.99 | Primary market |
| Amazon.co.uk | £24.99 | ~£17.49 | |
| Amazon.de | €27.99 | ~€19.59 | |
| Amazon.in | ₹999 | ~₹699 | Lower for Indian market |

> 70% royalty: requires price $2.99-$9.99 range... WAIT. Correction:
> 70% royalty option is available for $2.99-$9.99 ONLY.
> For $29.99 you get **35% royalty** = ~$10.50/sale.
>
> **Strategy decision**:
> - Option A: **$9.99** (max for 70% royalty) → $6.99/sale, higher volume
> - Option B: **$29.99** (35% royalty) → $10.50/sale, positions as premium
> - Option C: **$39.99** (35% royalty) → $13.99/sale, Manning-level pricing
>
> **Σύσταση**: Start at **$9.99** for launch (70% royalty, maximum reach).
> After 50+ reviews, raise to $19.99-$29.99 if reviews are strong.

### Paperback
| Marketplace | Price | Printing Cost | Royalty (60%) |
|-------------|-------|---------------|---------------|
| Amazon.com | $44.99 | ~$8.50 | ~$18.49 |
| Amazon.co.uk | £39.99 | ~£6.50 | ~£17.49 |

### Launch Strategy
1. **Week 1-2**: Ebook at $4.99 (launch price, maximize downloads + reviews)
2. **Week 3-4**: Raise to $9.99 (70% royalty sweet spot)
3. **Month 2+**: Based on reviews/sales, consider $14.99-$29.99
4. **Paperback**: Launch at $44.99 from day 1 (premium positioning)

---

## 5. Manuscript Preparation Checklist

### Front Matter (πρέπει να υπάρχουν στο DOCX)
- [x] Title page (ήδη στο generator)
- [ ] **Copyright page** (ΠΡΕΠΕΙ — βλέπε template παρακάτω)
- [x] Table of Contents
- [x] Prologue

### Back Matter
- [ ] **About the Author** (ΠΡΕΠΕΙ)
- [ ] **Also by the Author** (αν υπάρχει)

### Copyright Page Template
```
Agentic AI: Building Intelligent Agents with Python
Copyright © 2026 Dr. Stefanos Drakos

All rights reserved. No part of this publication may be reproduced,
distributed, or transmitted in any form or by any means, including
photocopying, recording, or other electronic or mechanical methods,
without the prior written permission of the author.

The code examples in this book are provided for educational purposes.
They are released under the MIT License unless otherwise noted.

Python is a registered trademark of the Python Software Foundation.
OpenAI is a trademark of OpenAI, Inc.
Claude and Anthropic are trademarks of Anthropic, PBC.
Amazon Web Services and related marks are trademarks of Amazon.com, Inc.

While every precaution has been taken in the preparation of this book,
the author assumes no responsibility for errors or omissions, or for
damages resulting from the use of the information contained herein.

SDK versions covered:
- OpenAI Agents SDK 0.1.x
- Claude Agent SDK 0.1.x
- Python 3.11+

First Edition, 2026
```

### About the Author Template
```
Dr. Stefanos Drakos is a software engineer and AI systems architect
based in Greece. He is the creator of AgelClaw, an open-source
autonomous AI assistant that combines the Claude Agent SDK and
OpenAI Agents SDK with persistent memory, skills, and multi-agent
orchestration.

His work focuses on building practical AI agent systems for
real-world applications, from autonomous daemons to multi-provider
routing architectures.

Contact: sdrakos@agel.ai
GitHub: github.com/sdrakos
```

> Πρόσθεσε ό,τι θέλεις: PhD institution, years of experience,
> previous publications, LinkedIn URL, website.

---

## 6. Cover Design

### Ebook Cover Specs
- **Dimensions**: 1600 x 2560 pixels (width x height)
- **Format**: JPG or TIFF
- **Color space**: sRGB
- **File size**: max 50MB
- **DPI**: 300 (but pixels matter more)

### Paperback Cover Specs (7.5" x 9.25" trim)
- Amazon provides a **Cover Calculator**: https://kdp.amazon.com/cover-calculator
- Input: Trim size 7.5x9.25, ~340 pages, white paper
- It generates a template PDF with exact spine width

### Cover Design Options
1. **99designs.com** — contest-based, ~$300-500 για book cover
2. **Fiverr** — $50-150 για decent technical book cover
3. **Reedsy** — professional book designers, $300-800
4. **Canva** — free/cheap, αλλά generic

### Cover Design Guidance
- Technical books: clean, minimal, dark background
- Include: title, subtitle, author name
- Reference covers: O'Reilly animals, Manning "in Action" series, Pragmatic Bookshelf
- **Avoid**: stock photos of robots, generic AI imagery, too many colors
- Suggested palette: dark blue (#1B3A5C — matches your heading colors) + white text + accent

---

## 7. KDP Select vs Wide Distribution

### KDP Select (recommended for launch)
- **90-day exclusivity** — only on Amazon (no Apple Books, Google Play, etc.)
- **Benefits**: Kindle Unlimited (readers read free, you get paid per page), Kindle Countdown Deals, Free Book Promotions
- **Revenue**: ~$0.004-0.005 per page read (KENP). 340 pages ≈ ~$1.50-1.70 per full read
- **Auto-renews** every 90 days — can opt out

### Wide Distribution (after establishing on Amazon)
- After 1-2 KDP Select cycles, consider going wide:
- **Draft2Digital** — distributes to Apple Books, Kobo, Barnes & Noble, libraries
- **Leanpub** — popular for technical books, pay-what-you-want pricing
- **Gumroad** — direct sales, 100% minus fees

> Σύσταση: Start with KDP Select for 90 days. Measure. Then decide.

---

## 8. Marketing Checklist (post-publish)

- [ ] **GitHub repo** με τα code examples (κρίσιμο για technical books)
- [ ] **LinkedIn article** announcing the book
- [ ] Post στα subreddits: r/Python, r/MachineLearning, r/artificial, r/LocalLLaMA
- [ ] **Hacker News** "Show HN" post
- [ ] **Twitter/X** announcement thread
- [ ] **Medium article** (ένα κεφάλαιο δωρεάν ως teaser — π.χ. Chapter 9 Multi-Agent)
- [ ] Amazon Author Central profile (author page on Amazon)
- [ ] Request **editorial reviews** (ask 3-5 people to review on Amazon in first week)
- [ ] **Companion website** with updates, errata, code downloads

---

## 9. Execution Timeline

| Day | Action |
|-----|--------|
| 1-3 | Update manuscript (copyright + about author pages) |
| 1-3 | Order cover design (Fiverr/99designs) |
| 4-5 | Generate final DOCX, proofread front/back matter |
| 5 | Create KDP account + tax info if not done |
| 6 | Upload ebook manuscript + cover to KDP |
| 6 | Fill in all metadata (title, description, keywords, categories) |
| 6 | Set pricing, enable KDP Select, submit for review |
| 7-9 | Amazon review (usually 24-72 hours) |
| 10 | **LIVE on Amazon** |
| 10-12 | Set up Amazon Author Central, create GitHub repo |
| 10-14 | LinkedIn + social media announcements |
| 14-21 | Paperback preparation (PDF formatting, cover with spine) |
| 21 | Submit paperback |
| 30 | First sales data, adjust pricing if needed |

---

## 10. File Checklist — What to Upload

### Ebook Upload
```
✅ Manuscript:  The_Bible_of_Agentic_AI_Systems.docx  (from generator)
✅ Cover:       cover_ebook.jpg                        (1600x2560px)
```

### Paperback Upload
```
✅ Interior:    book_interior.pdf       (7.5"x9.25", embedded fonts)
✅ Cover:       cover_paperback.pdf     (from KDP Cover Calculator template)
```

Generate the DOCX:
```bash
cd Book_for_Agentic
node generate_book_en.js
# Output: chapters_docs/The_Bible_of_Agentic_AI_Systems.docx
```
