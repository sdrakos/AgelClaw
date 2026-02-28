# 📧 Outlook Email Digest - Οδηγός Εγκατάστασης

## ✅ Τι Έχει Γίνει

1. ✅ Δημιουργήθηκε το skill `outlook-email-digest`
2. ✅ Δημιουργήθηκε το Python script `outlook_digest.py`
3. ✅ Εγκαταστάθηκαν όλες οι απαραίτητες βιβλιοθήκες
4. ✅ Δοκιμάστηκε η σύνδεση με το Outlook - **ΛΕΙΤΟΥΡΓΕΙ!** (βρήκε 5 emails)

## 🔧 Τι Απομένει

### 1. Gmail App Password (ΑΠΑΡΑΙΤΗΤΟ)

Για να μπορεί το script να στέλνει emails από το Gmail σου:

1. Πήγαινε στο: https://myaccount.google.com/security
2. Ενεργοποίησε **2-Step Verification** (αν δεν είναι ήδη)
3. Πήγαινε στο: https://myaccount.google.com/apppasswords
4. Δημιούργησε ένα App Password για "Mail"
5. Αντίγραψε τον κωδικό (16 ψηφία)
6. Βάλτο στο περιβάλλον ως:

```bash
export GMAIL_APP_PASSWORD="your-16-digit-password"
```

Ή στο script απευθείας (γραμμή 48):
```python
GMAIL_APP_PASSWORD = "xxxx xxxx xxxx xxxx"
```

### 2. OpenAI API Key (ΠΡΟΑΙΡΕΤΙΚΟ - για έξυπνες περιλήψεις)

Χωρίς αυτό, το script θα κάνει απλή περίληψη (λειτουργεί αλλά όχι τόσο έξυπνη).

1. Πήγαινε στο: https://platform.openai.com/api-keys
2. Δημιούργησε API key
3. Βάλτο στο περιβάλλον:

```bash
export OPENAI_API_KEY="sk-..."
```

Ή στο script (γραμμή 53):
```python
OPENAI_API_KEY = "sk-..."
```

## 🚀 Χρήση

### Δοκιμή (τρέχει μια φορά)
```bash
cd "C:\Users\Στέφανος\agel_openai\AGENTI_SDK\aclaude\proactive"
python outlook_digest.py --once
```

### Προγραμματισμός για κάθε πρωί στις 8:00
```bash
python outlook_digest.py --schedule
```

### Προγραμματισμός σε διαφορετική ώρα (π.χ. 9:00)
```bash
python outlook_digest.py --schedule --time 09:00
```

### Τρέξιμο στο παρασκήνιο με PM2
```bash
# Εγκατάσταση PM2 (αν δεν έχεις)
npm install -g pm2

# Εκκίνηση
pm2 start outlook_digest.py --name outlook-digest --interpreter python3 -- --schedule --time 08:00

# Αυτόματη εκκίνηση στο boot
pm2 save
pm2 startup

# Έλεγχος κατάστασης
pm2 status
pm2 logs outlook-digest
```

## 📊 Τι Κάνει

1. 🔐 Συνδέεται στο Outlook με τα credentials που έδωσες
2. 📧 Διαβάζει emails από τις τελευταίες 24 ώρες
3. 🤖 Δημιουργεί έξυπνη περίληψη με AI (ή απλή αν δεν υπάρχει OpenAI key)
4. ✉️ Στέλνει την περίληψη στο **stefanos.drakos@gmail.com**
5. 💾 Αποθηκεύει backup σε HTML αρχείο

## 🎯 Τελικό Αποτέλεσμα

Κάθε πρωί στις 8:00 θα παίρνεις email σαν αυτό:

```
Θέμα: 📧 Outlook Digest - 5 emails (15/02/2026)

📧 Περίληψη 5 Emails

1. **Sender Name**: Email Subject
   Email preview text...

2. **Another Sender**: Another Subject
   Preview...
...
```

Με OpenAI key, η περίληψη θα είναι πιο έξυπνη:
```
🔴 ΕΠΕΙΓΟΝ
- Από: Manager - Θέμα: Urgent Meeting
  Χρειάζεται απάντηση σήμερα για το project deadline.

🟡 ΣΗΜΑΝΤΙΚΑ
- Από: Client - Θέμα: Proposal Review
  Ο πελάτης ζητά αλλαγές στην πρόταση.
```

## 📝 Τι Βρέθηκε Στη Δοκιμή

✅ Βρέθηκαν **5 emails** από το Outlook σου (sdrakos@agel.ai)
✅ Η σύνδεση με Microsoft Graph API λειτουργεί τέλεια
✅ Δημιουργήθηκε HTML digest (δες το αρχείο `digest_20260215_004317.html`)

## 🛠️ Troubleshooting

### Πρόβλημα: "Authentication failed"
- Έλεγξε ότι τα credentials είναι σωστά
- Βεβαιώσου ότι το Azure AD app έχει τα σωστά permissions

### Πρόβλημα: "Gmail App Password not set"
- Ακολούθησε τα βήματα παραπάνω για Gmail App Password

### Πρόβλημα: "OpenAI error"
- Το script θα δουλέψει ούτως ή άλλως με απλή περίληψη
- Αν θες έξυπνη περίληψη, πρόσθεσε OpenAI API key

## 🎉 Επόμενα Βήματα

1. Πρόσθεσε το Gmail App Password
2. (Προαιρετικά) Πρόσθεσε OpenAI API Key
3. Δοκίμασε με `--once`
4. Αν όλα πάνε καλά, τρέξε με `--schedule` ή PM2

---

**Δημιουργήθηκε από:** Claude Agent SDK
**Ημερομηνία:** 15/02/2026