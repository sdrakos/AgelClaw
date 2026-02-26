# Outlook Email Digest - Οδηγίες Εγκατάστασης

## 📋 Τι κάνει το σύστημα

Αυτόματη ανάγνωση emails από Outlook (sdrakos@agel.ai), δημιουργία περίληψης με AI, και αποστολή στο Gmail (stefanos.drakos@gmail.com).

## ✅ Τι έχει ήδη ρυθμιστεί

- ✅ Azure AD credentials (CLIENT_ID, TENANT_ID)
- ✅ Outlook email: sdrakos@agel.ai
- ✅ Gmail recipient: stefanos.drakos@gmail.com
- ✅ Python dependencies εγκατεστημένα
- ✅ Script tested και λειτουργεί

## ⚠️ Τι χρειάζεται ακόμα

### 1. Gmail App Password (ΑΠΑΡΑΙΤΗΤΟ για αποστολή email)

**Βήματα:**
1. Πήγαινε στο: https://myaccount.google.com/apppasswords
2. Αν δεν έχεις ενεργοποιημένο 2-Step Verification, ενεργοποίησέ το πρώτα
3. Στα "App passwords" κλικ "Generate"
4. Επίλεξε "Mail" και "Other (Custom name)"
5. Γράψε "Outlook Digest"
6. Αντέγραψε τον 16-character κωδικό (πχ. "xxxx xxxx xxxx xxxx")
7. Άνοιξε PowerShell ή CMD και τρέξε:
   ```cmd
   setx GMAIL_APP_PASSWORD "xxxx xxxx xxxx xxxx"
   ```
8. Κλείσε και ξανάνοιξε το terminal

### 2. OpenAI API Key (ΠΡΟΑΙΡΕΤΙΚΟ - για AI summarization)

**Χωρίς OpenAI:** Θα δημιουργεί απλή λίστα emails
**Με OpenAI:** Θα δημιουργεί έξυπνη περίληψη στα Ελληνικά με κατηγορίες (ΕΠΕΙΓΟΝ/ΣΗΜΑΝΤΙΚΑ/FYI)

**Βήματα:**
1. Πήγαινε στο: https://platform.openai.com/api-keys
2. Κάνε login ή εγγραφή
3. Κλικ "Create new secret key"
4. Αντέγραψε το key (αρχίζει με "sk-...")
5. Άνοιξε PowerShell ή CMD και τρέξε:
   ```cmd
   setx OPENAI_API_KEY "sk-..."
   ```
6. Κλείσε και ξανάνοιξε το terminal

## 🧪 Τεστάρισμα

Μετά την ρύθμιση των credentials, τρέξε:

```bash
cd "C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\.Claude\Skills\outlook-email-digest"
python scripts/outlook_digest.py --once
```

Αναμενόμενα αποτελέσματα:
- ✅ Authentication successful
- ✅ Found X emails
- ✅ Email sent to stefanos.drakos@gmail.com
- ✅ Backup saved to digest_YYYYMMDD_HHMMSS.html

## 📅 Αυτοματοποίηση (Επιλογές)

### Επιλογή Α: Schedule εντός Python

```bash
# Τρέχει κάθε μέρα στις 8:00 πμ
python scripts/outlook_digest.py --schedule

# Τρέχει κάθε μέρα σε custom ώρα
python scripts/outlook_digest.py --schedule --time 09:30
```

Μειονέκτημα: Πρέπει να τρέχει συνέχεια το terminal

### Επιλογή Β: Windows Task Scheduler (ΠΡΟΤΕΙΝΕΤΑΙ)

1. Πάτα `Win + R`, γράψε `taskschd.msc`, Enter
2. Κλικ "Create Basic Task"
3. Name: "Outlook Email Digest"
4. Trigger: "Daily"
5. Time: 08:00
6. Action: "Start a program"
   - Program/script: `python`
   - Add arguments: `scripts\outlook_digest.py --once`
   - Start in: `C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\.Claude\Skills\outlook-email-digest`
7. Finish
8. Right-click το task → Properties
9. Check "Run with highest privileges"
10. OK

## 📊 Τι να περιμένεις

Κάθε πρωί θα λαμβάνεις email στο stefanos.drakos@gmail.com με:
- 📧 Header: "Outlook Email Digest"
- 📅 Ημερομηνία/ώρα
- 🔢 Αριθμός emails
- 📝 Περίληψη (AI-powered αν έχεις OpenAI key)

## 🔧 Troubleshooting

**Problem: "Gmail App Password not set!"**
- Solution: Βεβαιώσου ότι έτρεξες `setx GMAIL_APP_PASSWORD "..."` και ξανάνοιξες το terminal

**Problem: "OpenAI API key not set"**
- Αυτό είναι warning, όχι error. Θα δουλέψει με basic summary.
- Αν θες AI summarization, βάλε OPENAI_API_KEY

**Problem: "Authentication failed"**
- Οι Azure credentials είναι ήδη ρυθμισμένες στο script
- Αν αλλάξουν, edit το scripts/outlook_digest.py

## 📁 Backup Files

Κάθε φορά που τρέχει, δημιουργεί backup:
- Location: `C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\.Claude\Skills\outlook-email-digest\`
- Format: `digest_YYYYMMDD_HHMMSS.html`
- Μπορείς να τα ανοίξεις σε browser για να δεις την περίληψη

## ✅ Next Steps

1. [ ] Set GMAIL_APP_PASSWORD environment variable
2. [ ] Set OPENAI_API_KEY environment variable (optional)
3. [ ] Test run: `python scripts/outlook_digest.py --once`
4. [ ] Set up Windows Task Scheduler for daily execution
5. [ ] Wait for tomorrow morning's first digest!

---
Created: 2026-02-15
Status: READY TO DEPLOY (needs credentials setup)
