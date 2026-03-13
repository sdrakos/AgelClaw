import { useState } from 'react'

const SECTIONS = [
  { key: 'overview', label: 'Πώς λειτουργεί' },
  { key: 'mydata', label: 'Κλειδί myDATA' },
  { key: 'setup', label: 'Ρύθμιση στην εφαρμογή' },
  { key: 'faq', label: 'Συχνές Ερωτήσεις' },
]

export default function Help() {
  const [active, setActive] = useState('overview')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Βοήθεια</h1>

      {/* Section nav */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit flex-wrap">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => setActive(s.key)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              active === s.key
                ? 'bg-white text-slate-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {active === 'overview' && <OverviewSection />}
      {active === 'mydata' && <MyDataSection />}
      {active === 'setup' && <SetupSection />}
      {active === 'faq' && <FaqSection />}
    </div>
  )
}

function OverviewSection() {
  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Τι είναι το Timologia</h2>
        <p className="text-sm text-slate-600 leading-relaxed">
          Το Timologia είναι μια εφαρμογή διαχείρισης παραστατικών που συνδέεται
          με την πλατφόρμα <b>myDATA</b> της ΑΑΔΕ. Σας επιτρέπει να:
        </p>
        <ul className="mt-3 space-y-2 text-sm text-slate-600">
          <ListItem>Βλέπετε όλα τα παραστατικά σας (εσόδων και εξόδων) σε πραγματικό χρόνο</ListItem>
          <ListItem>Δημιουργείτε αναφορές και στατιστικά (ημερήσια, μηνιαία, ετήσια)</ListItem>
          <ListItem>Προγραμματίζετε αυτόματη αποστολή αναφορών με email</ListItem>
          <ListItem>Διαχειρίζεστε πολλές εταιρείες με ξεχωριστά δικαιώματα</ListItem>
          <ListItem>Χρησιμοποιείτε AI chat για ερωτήσεις σχετικά με τα παραστατικά σας</ListItem>
        </ul>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Πώς λειτουργεί</h2>
        <div className="space-y-4">
          <Step number={1} title="Δημιουργία εταιρείας">
            Δημιουργήστε μια εταιρεία εισάγοντας την επωνυμία και το ΑΦΜ.
          </Step>
          <Step number={2} title="Σύνδεση με myDATA">
            Εισάγετε τα κλειδιά API (User ID & Subscription Key) από την ΑΑΔΕ.
            Δείτε την ενότητα <b>"Κλειδί myDATA"</b> για οδηγίες.
          </Step>
          <Step number={3} title="Αυτόματος συγχρονισμός">
            Τα παραστατικά σας φορτώνονται αυτόματα από το myDATA.
            Ο συγχρονισμός γίνεται κάθε 15 λεπτά.
          </Step>
          <Step number={4} title="Αναφορές & Στατιστικά">
            Δημιουργήστε αναφορές Excel, δείτε γραφήματα εσόδων/εξόδων,
            και προγραμματίστε αυτόματη αποστολή.
          </Step>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Ρόλοι χρηστών</h2>
        <div className="space-y-3">
          <RoleBadge role="Ιδιοκτήτης" color="indigo" desc="Πλήρη δικαιώματα: ρυθμίσεις εταιρείας, διαχείριση μελών, ΑΑΔΕ κλειδιά, αναφορές, chat." />
          <RoleBadge role="Λογιστής" color="emerald" desc="Προβολή παραστατικών, δημιουργία αναφορών, προγραμματισμός, chat. Δεν αλλάζει ρυθμίσεις." />
          <RoleBadge role="Αναγνώστης" color="slate" desc="Μόνο προβολή παραστατικών και αναφορών." />
        </div>
      </Card>
    </div>
  )
}

function MyDataSection() {
  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <h2 className="mb-2 text-lg font-semibold text-slate-800">Τι είναι το myDATA REST API</h2>
        <p className="text-sm text-slate-600 leading-relaxed">
          Το <b>myDATA REST API</b> είναι η διεπαφή της ΑΑΔΕ που επιτρέπει σε εφαρμογές
          (όπως το Timologia) να διαβάζουν και να αποστέλλουν παραστατικά ηλεκτρονικά.
          Για να συνδέσετε την εταιρεία σας, χρειάζεστε δύο κλειδιά:
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4">
            <p className="text-sm font-semibold text-indigo-700">User ID</p>
            <p className="mt-1 text-xs text-indigo-600/80">Το όνομα χρήστη που δημιουργήσατε στην ΑΑΔΕ (π.χ. "mycompanyerp")</p>
          </div>
          <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-4">
            <p className="text-sm font-semibold text-indigo-700">Subscription Key</p>
            <p className="mt-1 text-xs text-indigo-600/80">Το κλειδί API που εκδίδει η ΑΑΔΕ (αλφαριθμητικό 32 χαρακτήρων)</p>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Βήμα-βήμα οδηγίες</h2>

        {/* Step 1 */}
        <div className="mb-8">
          <StepHeader number={1} title='Σύνδεση στο myDATA' />
          <p className="mt-2 text-sm text-slate-600">
            Συνδεθείτε στο <b>myDATA</b> μέσω του TAXISnet στη διεύθυνση{' '}
            <a href="https://www1.aade.gr/saadeapps2/bookkeeper-web" target="_blank" rel="noopener noreferrer"
              className="font-medium text-indigo-600 hover:text-indigo-500 underline underline-offset-2">
              mydata.aade.gr
            </a>.
            Από το κεντρικό μενού, εντοπίστε την επιλογή <b>"Εγγραφή στο myDATA Rest API"</b>.
          </p>
          <ImageWithCaption
            src="/help/mydata1.png"
            alt="Περιβάλλον myDATA - Κεντρική σελίδα"
            caption='Η κεντρική σελίδα του myDATA. Πατήστε "Εγγραφή στο myDATA Rest API".'
          />
        </div>

        {/* Step 2 */}
        <div className="mb-8">
          <StepHeader number={2} title="Μενού εφαρμογής" />
          <p className="mt-2 text-sm text-slate-600">
            Εναλλακτικά, μπορείτε να βρείτε την επιλογή από το μενού (hamburger icon)
            στο πάνω μέρος. Ανοίξτε το μενού και επιλέξτε <b>"Εγγραφή στο myDATA REST API"</b>.
          </p>
          <ImageWithCaption
            src="/help/mydata2.png"
            alt="myDATA - Μενού εφαρμογής"
            caption='Το μενού της εφαρμογής. Η επιλογή "Εγγραφή στο myDATA REST API" βρίσκεται στη λίστα.'
          />
        </div>

        {/* Step 3 */}
        <div className="mb-8">
          <StepHeader number={3} title="Εγγραφή & λήψη κλειδιού" />
          <p className="mt-2 text-sm text-slate-600">
            Στη σελίδα εγγραφής θα δείτε τα <b>Στοιχεία μητρώου</b> σας (ΑΦΜ, Επωνυμία)
            και πιο κάτω την ενότητα <b>"Χρήστες"</b>. Εδώ βλέπετε τους ενεργούς χρήστες API
            με τα Subscription Keys τους.
          </p>
          <ul className="mt-2 space-y-1.5 text-sm text-slate-600">
            <ListItem>
              Αν δεν υπάρχει χρήστης, πατήστε <b>"Νέα εγγραφή χρήστη"</b> για να δημιουργήσετε έναν
            </ListItem>
            <ListItem>
              Το <b>Όνομα χρήστη</b> (Username) είναι το <b>User ID</b> που θα χρειαστείτε
            </ListItem>
            <ListItem>
              Το <b>Subscription Key</b> εμφανίζεται μερικώς κρυφό — αντιγράψτε το πλήρες κλειδί κατά τη δημιουργία
            </ListItem>
          </ul>
          {/* Screenshot 3 with blurred personal data */}
          <div className="relative mt-4 overflow-hidden rounded-lg border border-gray-200 shadow-sm">
            <img
              src="/help/mydata3.png"
              alt="myDATA REST API - Χρήστες και Subscription Keys"
              className="w-full"
            />
            {/* Blur overlays for personal data */}
            {/* Top right name "ΣΤΕΦΑΝΟΣ ΔΡΑΚΟΣ" */}
            <div className="absolute" style={{ top: '0%', left: '84%', width: '16%', height: '8%', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', background: 'rgba(240,240,245,0.6)', borderRadius: '4px' }} />
            {/* AFM value "101660691" */}
            <div className="absolute" style={{ top: '49%', left: '3%', width: '15%', height: '7%', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', background: 'rgba(240,240,245,0.6)', borderRadius: '4px' }} />
            {/* Name "ΣΤΕΦΑΝΟΣ ΔΡΑΚΟΣ" in data row */}
            <div className="absolute" style={{ top: '49%', left: '18%', width: '41%', height: '7%', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', background: 'rgba(240,240,245,0.6)', borderRadius: '4px' }} />
            {/* Address "ΠΕΙΡΑΙΩΣ 44 - 85100 - ΡΟΔΟΣ" */}
            <div className="absolute" style={{ top: '49%', left: '60%', width: '38%', height: '7%', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', background: 'rgba(240,240,245,0.6)', borderRadius: '4px' }} />
            {/* Users table - subscription keys, usernames, emails */}
            <div className="absolute" style={{ top: '74%', left: '5%', width: '70%', height: '17%', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', background: 'rgba(240,240,245,0.6)', borderRadius: '4px' }} />
          </div>
          <p className="mt-2 text-xs text-slate-400 italic text-center">
            Σελίδα "Εγγραφή στο myDATA REST API" — Χρήστες & Subscription Keys (τα προσωπικά στοιχεία έχουν αποκρυφτεί)
          </p>
        </div>

        {/* Important note */}
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex gap-2">
            <svg className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <div className="text-sm text-amber-800">
              <p className="font-semibold">Σημαντικό</p>
              <p className="mt-1 text-amber-700">
                Αντιγράψτε το Subscription Key αμέσως μετά τη δημιουργία του χρήστη.
                Μετά, εμφανίζεται μερικώς κρυμμένο και δεν μπορείτε να το δείτε ολόκληρο.
                Αν το χάσετε, θα πρέπει να δημιουργήσετε νέο χρήστη.
              </p>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-lg font-semibold text-slate-800">Δοκιμαστικό vs Παραγωγικό περιβάλλον</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4">
            <p className="text-sm font-semibold text-blue-700">Δοκιμαστικό (dev)</p>
            <p className="mt-1 text-xs text-blue-600/80">
              Χρησιμοποιεί τα test servers της ΑΑΔΕ. Κατάλληλο για δοκιμές χωρίς
              να επηρεάζει τα πραγματικά παραστατικά σας.
            </p>
          </div>
          <div className="rounded-lg border border-green-100 bg-green-50/50 p-4">
            <p className="text-sm font-semibold text-green-700">Παραγωγή (prod)</p>
            <p className="mt-1 text-xs text-green-600/80">
              Συνδέεται με τα πραγματικά δεδομένα της ΑΑΔΕ.
              Χρησιμοποιήστε αυτό για κανονική λειτουργία.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}

function SetupSection() {
  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Πού βάζω τα κλειδιά στην εφαρμογή</h2>
        <p className="mb-4 text-sm text-slate-600">
          Αφού αποκτήσετε τα κλειδιά API από την ΑΑΔΕ, ακολουθήστε τα παρακάτω βήματα:
        </p>

        <div className="space-y-6">
          <Step number={1} title="Ρυθμίσεις > Εταιρεία">
            Πλοηγηθείτε στο μενού <b>Ρυθμίσεις</b> (αριστερό sidebar) και βεβαιωθείτε
            ότι βρίσκεστε στην καρτέλα <b>"Εταιρεία"</b>.
          </Step>

          <Step number={2} title="Συμπληρώστε τα στοιχεία">
            Βεβαιωθείτε ότι η <b>Επωνυμία</b> και το <b>ΑΦΜ</b> είναι σωστά.
          </Step>

          <Step number={3} title="Επιλέξτε περιβάλλον">
            Επιλέξτε <b>Δοκιμαστικό</b> για tests ή <b>Παραγωγή</b> για πραγματικά δεδομένα.
          </Step>

          <Step number={4} title='Εισάγετε τα κλειδιά ΑΑΔΕ'>
            Στην ενότητα <b>"Διαπιστευτήρια ΑΑΔΕ"</b>:
            <div className="mt-2 space-y-2">
              <FieldGuide label="User ID" desc='Το όνομα χρήστη που δημιουργήσατε στην ΑΑΔΕ (π.χ. "mycompanyerp")' />
              <FieldGuide label="Subscription Key" desc="Το αλφαριθμητικό κλειδί API 32 χαρακτήρων" />
            </div>
          </Step>

          <Step number={5} title="Αποθήκευση">
            Πατήστε <b>"Αποθήκευση"</b>. Τα κλειδιά αποθηκεύονται κρυπτογραφημένα.
            Μετά την αποθήκευση, τα παραστατικά σας θα φορτωθούν αυτόματα.
          </Step>
        </div>
      </Card>

      {/* Visual guide - Settings page mock */}
      <Card>
        <h2 className="mb-4 text-lg font-semibold text-slate-800">Οπτικός οδηγός</h2>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-5">
          {/* Mock settings form */}
          <div className="space-y-4">
            <div className="flex gap-1 rounded-lg bg-gray-100 p-1 w-fit">
              <div className="rounded-md bg-white px-4 py-1.5 text-xs font-medium text-slate-700 shadow-sm">Εταιρεία</div>
              <div className="rounded-md px-4 py-1.5 text-xs text-gray-400">Μέλη</div>
              <div className="rounded-md px-4 py-1.5 text-xs text-gray-400">Λογαριασμός</div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <MockField label="Επωνυμία" value="ΕΤΑΙΡΕΙΑ ΔΕΙΓΜΑ Ο.Ε." />
              <MockField label="ΑΦΜ" value="123456789" mono />
            </div>

            <div className="border-t border-gray-200 pt-3">
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-slate-400">Διαπιστευτήρια ΑΑΔΕ</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <MockField label="User ID" value="mycompanyerp" highlight />
                <MockField label="Subscription Key" value="0f34a2b8c9d1e5f6..." highlight secret />
              </div>
            </div>

            <div className="flex justify-end">
              <div className="rounded-lg bg-indigo-600 px-4 py-2 text-xs font-medium text-white">
                Αποθήκευση
              </div>
            </div>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-400 text-center">
          Ρυθμίσεις &gt; Εταιρεία — Τα πεδία User ID και Subscription Key (επισημασμένα)
        </p>
      </Card>

      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
        <div className="flex gap-2">
          <svg className="mt-0.5 h-5 w-5 shrink-0 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <div className="text-sm text-green-800">
            <p className="font-semibold">Ασφάλεια</p>
            <p className="mt-1 text-green-700">
              Τα κλειδιά σας αποθηκεύονται <b>κρυπτογραφημένα</b> (Fernet encryption) στη βάση δεδομένων.
              Κανείς δεν μπορεί να τα δει σε καθαρό κείμενο — ούτε οι διαχειριστές.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function FaqSection() {
  return (
    <div className="max-w-3xl space-y-4">
      <FaqItem
        q="Μπορώ να έχω πολλές εταιρείες;"
        a="Ναι. Από το dropdown στο πάνω μέρος μπορείτε να προσθέσετε και να εναλλάσσετε μεταξύ εταιρειών. Κάθε εταιρεία έχει δικά της κλειδιά ΑΑΔΕ."
      />
      <FaqItem
        q="Τι γίνεται αν αλλάξω Subscription Key στην ΑΑΔΕ;"
        a='Πηγαίνετε στις Ρυθμίσεις > Εταιρεία, αλλάξτε το κλειδί, και πατήστε "Αποθήκευση". Τα παλιά κλειδιά αντικαθίστανται αμέσως.'
      />
      <FaqItem
        q="Πόσο συχνά ανανεώνονται τα παραστατικά;"
        a="Αυτόματα κάθε 15 λεπτά. Μπορείτε επίσης να πατήσετε ανανέωση χειροκίνητα στη σελίδα Παραστατικά."
      />
      <FaqItem
        q="Τι σημαίνει Δοκιμαστικό / Παραγωγή;"
        a='Το "Δοκιμαστικό" (dev) χρησιμοποιεί τα test servers της ΑΑΔΕ — δεν βλέπετε πραγματικά παραστατικά. Το "Παραγωγή" (prod) συνδέεται με τα πραγματικά δεδομένα σας.'
      />
      <FaqItem
        q="Μπορεί ο λογιστής μου να δει τα κλειδιά;"
        a="Όχι. Τα κλειδιά εμφανίζονται ως ******** για όλους. Μόνο ο ιδιοκτήτης μπορεί να τα αλλάξει εισάγοντας νέα."
      />
      <FaqItem
        q="Πώς προσκαλώ τον λογιστή μου;"
        a='Πηγαίνετε στις Ρυθμίσεις > Μέλη, εισάγετε το email του, επιλέξτε ρόλο "Λογιστής", και πατήστε "Πρόσκληση". Θα λάβει email με σύνδεσμο.'
      />
      <FaqItem
        q="Τι κάνει ο AI Chat;"
        a="Μπορείτε να ρωτήσετε οτιδήποτε σχετικά με τα παραστατικά σας σε φυσική γλώσσα. Π.χ. 'Πόσα τιμολόγια εξέδωσα τον Φεβρουάριο;' ή 'Φτιάξε αναφορά εξόδων για αυτό τον μήνα'."
      />
    </div>
  )
}


// ── Reusable components ──

function Card({ children }) {
  return <div className="rounded-xl bg-white p-6 shadow-sm">{children}</div>
}

function ListItem({ children }) {
  return (
    <li className="flex gap-2">
      <svg className="mt-1 h-4 w-4 shrink-0 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
      <span>{children}</span>
    </li>
  )
}

function Step({ number, title, children }) {
  return (
    <div className="flex gap-4">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-bold text-indigo-600">
        {number}
      </div>
      <div className="pt-0.5">
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <p className="mt-1 text-sm text-slate-600">{children}</p>
      </div>
    </div>
  )
}

function StepHeader({ number, title }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
        {number}
      </div>
      <h3 className="text-base font-semibold text-slate-800">{title}</h3>
    </div>
  )
}

function ImageWithCaption({ src, alt, caption }) {
  return (
    <div className="mt-4">
      <div className="overflow-hidden rounded-lg border border-gray-200 shadow-sm">
        <img src={src} alt={alt} className="w-full" loading="lazy" />
      </div>
      <p className="mt-2 text-xs text-slate-400 italic text-center">{caption}</p>
    </div>
  )
}

function RoleBadge({ role, color, desc }) {
  const colors = {
    indigo: 'bg-indigo-100 text-indigo-700 border-indigo-200',
    emerald: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    slate: 'bg-slate-100 text-slate-600 border-slate-200',
  }
  return (
    <div className="flex items-start gap-3">
      <span className={`shrink-0 rounded-full border px-3 py-0.5 text-xs font-medium ${colors[color]}`}>{role}</span>
      <p className="text-sm text-slate-600">{desc}</p>
    </div>
  )
}

function FieldGuide({ label, desc }) {
  return (
    <div className="flex items-start gap-2 rounded-md bg-indigo-50/50 px-3 py-2">
      <span className="shrink-0 rounded bg-indigo-100 px-2 py-0.5 text-xs font-mono font-medium text-indigo-700">{label}</span>
      <span className="text-xs text-indigo-600/80">{desc}</span>
    </div>
  )
}

function MockField({ label, value, mono, highlight, secret }) {
  return (
    <div>
      <p className={`mb-1 text-[11px] font-medium ${highlight ? 'text-indigo-600' : 'text-slate-500'}`}>{label}</p>
      <div className={`rounded-md border px-3 py-2 text-xs ${
        highlight
          ? 'border-indigo-300 bg-indigo-50 text-indigo-700 ring-2 ring-indigo-200/50'
          : 'border-gray-200 bg-white text-slate-600'
      } ${mono ? 'font-mono' : ''}`}>
        {secret ? '0f34a2b8c9d1e5f6...' : value}
      </div>
    </div>
  )
}

function FaqItem({ q, a }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm">
      <p className="text-sm font-semibold text-slate-800">{q}</p>
      <p className="mt-2 text-sm text-slate-600">{a}</p>
    </div>
  )
}
