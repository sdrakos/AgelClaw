# AgelClaw — Οδηγός Δημιουργίας Installer (Απλά Λόγια)

## Τι είναι αυτό;

Το AgelClaw είναι ένα πρόγραμμα γραμμένο σε Python. Κανονικά, για να το εγκαταστήσει κάποιος, πρέπει:
1. Να έχει εγκατεστημένη Python
2. Να έχει git
3. Να ανοίξει terminal και να γράψει εντολές

Αυτό είναι δύσκολο για τον μέσο χρήστη. Γι' αυτό φτιάχνουμε ένα **installer** — ένα κλασικό `Setup.exe` που κάνεις διπλό κλικ, πατάς "Next, Next, Install" και τελείωσε.

---

## Η Διαδικασία σε 4 Βήματα

### Βήμα 1: Μετατροπή Python → EXE (Nuitka)

Το πρόγραμμα Nuitka παίρνει τον Python κώδικα και τον μετατρέπει σε κανονικό Windows πρόγραμμα (.exe).

Σκέψου το σαν "μεταφραστή": ο κώδικας Python μεταφράζεται σε γλώσσα που καταλαβαίνει απευθείας ο υπολογιστής, χωρίς να χρειάζεται Python εγκατεστημένη.

**Τι παράγει:** Ένα φάκελο `AgelClaw.dist/` που περιέχει:
- `AgelClaw.exe` — το κύριο πρόγραμμα
- Δεκάδες αρχεία `.dll` — βιβλιοθήκες που χρειάζεται το πρόγραμμα για να τρέξει

### Βήμα 2: Δημιουργία AgelClaw-Mem.exe

Το AgelClaw έχει δύο "είσοδους":
- `AgelClaw.exe` — η κύρια εφαρμογή (chat, web, telegram, daemon)
- `AgelClaw-Mem.exe` — εργαλείο μνήμης (tasks, learnings, skills)

Αντί να κάνουμε compile δύο φορές (χρονοβόρο), απλά **αντιγράφουμε** το AgelClaw.exe με νέο όνομα. Το πρόγραμμα κοιτάει πώς λέγεται το αρχείο που τρέχει — αν λέγεται "AgelClaw-Mem", συμπεριφέρεται ως εργαλείο μνήμης.

### Βήμα 3: Ενσωμάτωση Python Embeddable

Κάποια κομμάτια του AgelClaw (τα MCP server scripts) χρειάζονται μια "αληθινή" Python για να τρέξουν. Γι' αυτό κατεβάζουμε μια μίνι-έκδοση Python (~12MB) από το python.org και την βάζουμε μέσα στον φάκελο του προγράμματος. Ο χρήστης δεν χρειάζεται να ξέρει ότι υπάρχει — δουλεύει αυτόματα στο παρασκήνιο.

### Βήμα 4: Πακετάρισμα σε Installer (Inno Setup)

Το Inno Setup είναι ένα δωρεάν εργαλείο που παίρνει όλα τα παραπάνω αρχεία και τα πακετάρει σε ένα μόνο αρχείο: `AgelClaw-Setup-3.1.0.exe`.

Αυτό είναι ο installer που βλέπει ο τελικός χρήστης. Περιλαμβάνει:
- Οθόνη καλωσορίσματος
- Επιλογή φακέλου εγκατάστασης
- Επιλογές (συντομεύσεις, αυτόματη εκκίνηση κτλ)
- Εγκατάσταση Claude Code CLI (αν υπάρχει Node.js)
- Αρχική ρύθμιση (API keys κτλ)

---

## Τι χρειάζεσαι στο δικό σου PC (developer) για να χτίσεις τον installer

### Εφάπαξ εγκατάσταση

1. **Python 3.11+** — ήδη το έχεις
2. **Nuitka** — εγκατάσταση μέσω pip:
   ```
   pip install nuitka ordered-set zstandard
   ```
3. **Inno Setup 6** — κατέβασε από https://jrsoftware.org/isdl.php και εγκατέστησε (Next, Next, Install). Εγκαθίσταται στο `C:\Program Files (x86)\Inno Setup 6\`

### Πώς χτίζεις τον installer

Ανοίγεις terminal στον φάκελο `proactive/` και τρέχεις:

```
python build_installer.py
```

Αυτό κάνει αυτόματα και τα 4 βήματα. Στο τέλος, θα βρεις τον installer εδώ:

```
proactive/build/installer/AgelClaw-Setup-3.1.0.exe
```

Αυτό το αρχείο είναι ο installer. Μπορείς να το ανεβάσεις στο GitHub, να το στείλεις με email, ή να το βάλεις σε USB.

### Πόσο χρόνο παίρνει;

- **Πρώτη φορά:** 10-20 λεπτά (Nuitka compile + download Python embeddable)
- **Μετέπειτα:** 5-10 λεπτά (Nuitka ξαναεξετάζει τι άλλαξε)
- **Μόνο Inno Setup** (αν δεν άλλαξε κώδικας): ~30 δευτερόλεπτα

### Χρήσιμες παραλλαγές

| Εντολή | Τι κάνει |
|--------|----------|
| `python build_installer.py` | Πλήρες build (όλα τα βήματα) |
| `python build_installer.py --skip-nuitka` | Μόνο πακετάρισμα (χρησιμοποιεί υπάρχον compile) |
| `python build_installer.py --skip-inno` | Μόνο compile, χωρίς installer |
| `python build_installer.py --skip-embed` | Παράλειψη download Python embeddable |

---

## Τι βλέπει ο χρήστης που εγκαθιστά

### Κατά την εγκατάσταση

1. Κάνει διπλό κλικ στο `AgelClaw-Setup-3.1.0.exe`
2. Βλέπει οθόνη καλωσορίσματος
3. Επιλέγει φάκελο εγκατάστασης (προεπιλογή: `C:\Program Files\AgelClaw\`)
4. Τσεκάρει τι θέλει:
   - ✅ Προσθήκη στο PATH (ώστε να λειτουργεί η εντολή `agelclaw` από παντού)
   - ☐ Συντόμευση στο Desktop
   - ☐ Αυτόματη εκκίνηση daemon στο login
   - ✅ Εγκατάσταση Claude Code CLI (χρειάζεται Node.js)
5. Πατάει "Install" — περιμένει 1-2 λεπτά
6. Ανοίγει ο Setup Wizard για να βάλει τα API keys

### Μετά την εγκατάσταση

Ο χρήστης μπορεί:
- Από το **Start Menu** → AgelClaw Web UI (ανοίγει browser)
- Από το **Start Menu** → AgelClaw CLI (ανοίγει terminal)
- Από οποιοδήποτε **terminal** → `agelclaw web`, `agelclaw setup`, κτλ

### Απεγκατάσταση

Από τις Ρυθμίσεις Windows → Εφαρμογές → AgelClaw → Κατάργηση εγκατάστασης. Ή από το Start Menu → Uninstall AgelClaw. Σβήνει το πρόγραμμα αλλά **κρατάει** τα δεδομένα του χρήστη (ρυθμίσεις, μνήμη, skills) στο `~/.agelclaw/`.

---

## Τι περιέχει το τελικό πακέτο

```
C:\Program Files\AgelClaw\
├── AgelClaw.exe              ← Το κύριο πρόγραμμα (chat, web, telegram, daemon)
├── AgelClaw-Mem.exe          ← Εργαλείο μνήμης (tasks, skills, learnings)
├── python-embed\             ← Μίνι Python για εσωτερική χρήση
│   └── python.exe
├── agelclaw\data\            ← Δεδομένα εφαρμογής
│   ├── react_dist\           ← Web interface
│   ├── skills\               ← 15 ενσωματωμένα skills
│   ├── templates\            ← Πρότυπα config
│   └── mcp_servers\          ← MCP servers
└── *.dll, *.pyd              ← Βιβλιοθήκες που χρειάζεται το πρόγραμμα
```

Μέγεθος: ~80-100MB (ο installer), ~150-200MB (εγκατεστημένο)

---

## Συχνές Ερωτήσεις

**Ε: Χρειάζεται Python ο τελικός χρήστης;**
Α: Όχι. Το Nuitka ενσωματώνει τα πάντα μέσα στο exe.

**Ε: Χρειάζεται Node.js ο τελικός χρήστης;**
Α: Μόνο αν θέλει Claude Code CLI. Αν δεν έχει Node.js, ο installer εμφανίζει προειδοποίηση και συνεχίζει — το AgelClaw λειτουργεί κανονικά, απλά χωρίς Claude CLI.

**Ε: Αν αλλάξω κώδικα, πρέπει να ξαναφτιάξω τον installer;**
Α: Ναι. Ο installer είναι "φωτογραφία" του κώδικα τη στιγμή που τον έχτισες. Κάθε αλλαγή απαιτεί νέο build.

**Ε: Πώς ανεβάζω τον installer στο GitHub;**
Α: Μέσω GitHub Releases. Δημιουργείς ένα Release (π.χ. v3.1.0) και ανεβάζεις το `.exe` ως asset. Ή χρησιμοποιείς: `agelclaw release`

**Ε: Ο dev mode (pip install -e .) επηρεάζεται;**
Α: Καθόλου. Όλες οι αλλαγές είναι πίσω από `IS_COMPILED` guards. Αν δεν τρέχεις compiled exe, ο κώδικας συμπεριφέρεται ακριβώς όπως πριν.

**Ε: Πόσο μεγάλο είναι το AgelClaw.exe;**
Α: Περίπου 60-100MB. Αυτό περιλαμβάνει ολόκληρη τη Python runtime, όλες τις βιβλιοθήκες (FastAPI, Click, httpx κτλ) και τα δεδομένα (React UI, skills, templates).

**Ε: Γιατί δεν ενσωματώνουμε το Claude Code CLI;**
Α: Γιατί είναι 236MB και ενημερώνεται συχνά. Καλύτερα να εγκαθίσταται μέσω npm που διαχειρίζεται τις ενημερώσεις αυτόματα.

---

## Διάγραμμα Ροής

```
┌─────────────────────────────────────────────────────────┐
│                    Developer PC                         │
│                                                         │
│  Κώδικας Python ──→ Nuitka ──→ AgelClaw.exe            │
│                         │                               │
│                         ├──→ Copy ──→ AgelClaw-Mem.exe  │
│                         │                               │
│  python.org ──download──→ python-embed/                 │
│                         │                               │
│  Όλα μαζί ──→ Inno Setup ──→ AgelClaw-Setup-3.1.0.exe │
│                                       │                 │
└───────────────────────────────────────┼─────────────────┘
                                        │
                                        │ Upload σε GitHub/email/USB
                                        ▼
┌─────────────────────────────────────────────────────────┐
│                    Χρήστης PC                            │
│                                                         │
│  Διπλό κλικ Setup.exe → Next → Next → Install → Done!  │
│                                                         │
│  Αποτέλεσμα:                                            │
│    • AgelClaw στο Start Menu                            │
│    • agelclaw εντολή στο terminal                       │
│    • Web UI στο http://localhost:8000                    │
│    • Χωρίς Python, χωρίς git, χωρίς pip                │
└─────────────────────────────────────────────────────────┘
```
