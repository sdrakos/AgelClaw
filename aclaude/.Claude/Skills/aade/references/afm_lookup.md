# ΑΦΜ Lookup, ΚΑΔ Mapping & Auto-Classification

## Overview

This module enables the agent to:
1. **Validate** an ΑΦΜ locally (check digit algorithm)
2. **Lookup** business details from AADE (name, address, KAD codes, DOY, status)
3. **Map** KAD codes to the correct myDATA invoice type and income/expense classification
4. **Cache** results in SQLite so repeated lookups are instant

## Prerequisites

The AADE ΑΦΜ lookup service (RgWsPublic2) requires separate credentials from myDATA:
- Register at `https://www1.gsis.gr/sgsisapps/tokenservices/protected/displayConsole.htm`
- You need TAXISnet login, then you get a **special username/password** for the SOAP service
- The WSDL endpoint is: `https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2?WSDL`
- It's a SOAP 1.2 service (JAX-WS 2.0) using TLS 1.2

**Important**: When you look up an ΑΦΜ, the owner of that ΑΦΜ gets a notification in their TAXISnet that you searched for them. This is by design for transparency.

## Dependencies

```bash
pip install zeep httpx lxml python-dotenv
```

## .env additions

```
# AADE AFM Lookup (RgWsPublic2) - separate from myDATA credentials
GSIS_AFM_USERNAME=your-special-username
GSIS_AFM_PASSWORD=your-special-password
GSIS_CALLER_AFM=999999999
```

## afm_lookup.py — Complete Module

```python
"""
AADE ΑΦΜ Lookup Client with local validation, SOAP lookup, KAD-to-myDATA
mapping, and SQLite caching.

Usage:
    from afm_lookup import AFMLookup
    
    lookup = AFMLookup.from_env()
    info = await lookup.get_business_info("012345678")
    classification = lookup.get_classification("012345678")
"""

import os
import re
import sqlite3
import json
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

from zeep import Client as SoapClient
from zeep.transports import Transport
import httpx


# ──────────────────────────────────────────────
# AFM Validation (local, no API call)
# ──────────────────────────────────────────────

def validate_afm(afm: str) -> bool:
    """Validate Greek ΑΦΜ using the official check digit algorithm.
    Returns True if the ΑΦΜ is syntactically valid.
    Does NOT check if it exists in TAXIS.
    """
    afm = afm.strip().replace("EL", "").replace("el", "")
    
    if not re.match(r'^\d{9}$', afm):
        return False
    
    digits = [int(d) for d in afm]
    
    # The check digit algorithm:
    # Multiply each of the first 8 digits by 2^(8-position)
    # Sum them, mod 11, mod 10 = check digit (9th digit)
    total = 0
    for i in range(8):
        total += digits[i] * (2 ** (8 - i))
    
    check = (total % 11) % 10
    return check == digits[8]


# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────

@dataclass
class KADInfo:
    """A single KAD (activity code) entry."""
    kad_code: str          # e.g. "62.01"
    kad_description: str   # e.g. "Δραστηριότητες προγραμματισμού Η/Υ"
    kad_kind: str          # "ΚΥΡΙΑ" or "ΔΕΥΤΕΡΕΥΟΥΣΑ"
    kad_kind_code: int     # 1=primary, 2-4=secondary


@dataclass
class BusinessInfo:
    """Complete business information from AADE lookup."""
    afm: str
    name: str                          # Επωνυμία
    commercial_title: str = ""         # Διακριτικός τίτλος
    doy_code: str = ""                 # Κωδικός ΔΟΥ
    doy_description: str = ""          # Περιγραφή ΔΟΥ
    legal_status: str = ""             # Νομική μορφή (ΑΕ, ΕΠΕ, ΙΚΕ, ατομική κλπ)
    is_active: bool = True             # Ενεργός ΑΦΜ
    is_business: bool = True           # Επιτηδευματίας
    address_street: str = ""
    address_number: str = ""
    address_postal_code: str = ""
    address_city: str = ""
    registration_date: Optional[str] = None
    deactivation_date: Optional[str] = None
    kad_list: list[KADInfo] = field(default_factory=list)
    primary_kad: Optional[str] = None  # Main KAD code
    lookup_date: Optional[str] = None  # When we fetched this
    
    @property
    def primary_kad_2digit(self) -> Optional[str]:
        """Get the 2-digit KAD prefix (sector level)."""
        if self.primary_kad:
            return self.primary_kad.split(".")[0]
        return None


@dataclass
class MyDataClassification:
    """Suggested myDATA classification based on KAD."""
    invoice_type: str              # e.g. "2.1"
    invoice_type_name: str         # e.g. "Τιμολόγιο Παροχής Υπηρεσιών"
    income_classification_type: str   # e.g. "E3_561_003"
    income_classification_category: str  # e.g. "category1_3"
    vat_category: int              # Default VAT category (1=24%, etc.)
    description: str               # Human-readable explanation
    confidence: str                # "high", "medium", "low"


# ──────────────────────────────────────────────
# KAD → myDATA Mapping Table
# ──────────────────────────────────────────────

# Maps 2-digit KAD prefix to default myDATA classification
# This covers the vast majority of cases. Edge cases need manual review.

KAD_TO_MYDATA = {
    # Agriculture, Forestry, Fishing (01-03)
    "01": ("1.1", "Πώληση αγροτικών προϊόντων", "E3_561_001", "category1_1", 13, "high"),
    "02": ("1.1", "Πώληση δασικών προϊόντων", "E3_561_001", "category1_1", 13, "high"),
    "03": ("1.1", "Πώληση αλιευμάτων", "E3_561_001", "category1_1", 13, "high"),
    
    # Mining (05-09)
    "05": ("1.1", "Πώληση ορυκτών", "E3_561_001", "category1_1", 1, "high"),
    "06": ("1.1", "Πώληση πετρελαιοειδών", "E3_561_001", "category1_1", 1, "high"),
    "07": ("1.1", "Πώληση μεταλλευμάτων", "E3_561_001", "category1_1", 1, "high"),
    "08": ("1.1", "Λοιπά ορυχεία", "E3_561_001", "category1_1", 1, "high"),
    "09": ("2.1", "Υποστηρικτικές εξόρυξης", "E3_561_003", "category1_3", 1, "medium"),
    
    # Manufacturing (10-33)
    "10": ("1.1", "Βιομηχανία τροφίμων", "E3_561_001", "category1_1", 13, "high"),
    "11": ("1.1", "Βιομηχανία ποτών", "E3_561_001", "category1_1", 1, "high"),
    "12": ("1.1", "Καπνοβιομηχανία", "E3_561_001", "category1_1", 1, "high"),
    "13": ("1.1", "Κλωστοϋφαντουργία", "E3_561_001", "category1_1", 1, "high"),
    "14": ("1.1", "Κατασκευή ενδυμάτων", "E3_561_001", "category1_1", 1, "high"),
    "15": ("1.1", "Βιομηχανία δέρματος", "E3_561_001", "category1_1", 1, "high"),
    "16": ("1.1", "Βιομηχανία ξύλου", "E3_561_001", "category1_1", 1, "high"),
    "17": ("1.1", "Χαρτοβιομηχανία", "E3_561_001", "category1_1", 1, "high"),
    "18": ("1.1", "Εκτυπώσεις", "E3_561_001", "category1_1", 1, "high"),
    "20": ("1.1", "Χημικά προϊόντα", "E3_561_001", "category1_1", 1, "high"),
    "21": ("1.1", "Φαρμακευτικά", "E3_561_001", "category1_1", 1, "high"),
    "22": ("1.1", "Πλαστικά/ελαστικά", "E3_561_001", "category1_1", 1, "high"),
    "23": ("1.1", "Μη μεταλλικά ορυκτά", "E3_561_001", "category1_1", 1, "high"),
    "24": ("1.1", "Βασικά μέταλλα", "E3_561_001", "category1_1", 1, "high"),
    "25": ("1.1", "Μεταλλικά προϊόντα", "E3_561_001", "category1_1", 1, "high"),
    "26": ("1.1", "Ηλεκτρονικά/Η.Υ.", "E3_561_001", "category1_1", 1, "high"),
    "27": ("1.1", "Ηλεκτρολογικός εξοπλισμός", "E3_561_001", "category1_1", 1, "high"),
    "28": ("1.1", "Μηχανήματα", "E3_561_001", "category1_1", 1, "high"),
    "29": ("1.1", "Μηχ. οχήματα", "E3_561_001", "category1_1", 1, "high"),
    "30": ("1.1", "Λοιπός εξοπλισμός μεταφορών", "E3_561_001", "category1_1", 1, "high"),
    "31": ("1.1", "Έπιπλα", "E3_561_001", "category1_1", 1, "high"),
    "32": ("1.1", "Άλλες μεταποιητικές", "E3_561_001", "category1_1", 1, "high"),
    "33": ("2.1", "Επισκευή/εγκατάσταση μηχ.", "E3_561_003", "category1_3", 1, "high"),
    
    # Utilities (35-39)
    "35": ("1.1", "Ηλεκτρισμός/φυσ.αέριο", "E3_561_001", "category1_1", 1, "high"),
    "36": ("1.1", "Ύδρευση", "E3_561_001", "category1_1", 1, "high"),
    "37": ("2.1", "Αποχέτευση", "E3_561_003", "category1_3", 1, "medium"),
    "38": ("2.1", "Διαχείριση αποβλήτων", "E3_561_003", "category1_3", 1, "medium"),
    "39": ("2.1", "Εξυγίανση", "E3_561_003", "category1_3", 1, "medium"),
    
    # Construction (41-43)
    "41": ("1.1", "Κατασκευή κτιρίων", "E3_561_001", "category1_1", 1, "high"),
    "42": ("1.1", "Έργα πολιτικού μηχανικού", "E3_561_001", "category1_1", 1, "high"),
    "43": ("2.1", "Εξειδικευμένες κατασκ. εργασίες", "E3_561_003", "category1_3", 1, "high"),
    
    # Trade - Wholesale & Retail (45-47)
    "45": ("1.1", "Εμπόριο/επισκευή οχημάτων", "E3_561_001", "category1_1", 1, "high"),
    "46": ("1.1", "Χονδρικό εμπόριο", "E3_561_001", "category1_1", 1, "high"),
    "47": ("1.1", "Λιανικό εμπόριο", "E3_561_005", "category1_5", 1, "high"),
    
    # Transport & Storage (49-53)
    "49": ("2.1", "Χερσαίες μεταφορές", "E3_561_003", "category1_3", 1, "high"),
    "50": ("2.1", "Θαλάσσιες μεταφορές", "E3_561_003", "category1_3", 1, "high"),
    "51": ("2.1", "Αεροπορικές μεταφορές", "E3_561_003", "category1_3", 1, "high"),
    "52": ("2.1", "Αποθήκευση & υποστήριξη μεταφ.", "E3_561_003", "category1_3", 1, "high"),
    "53": ("2.1", "Ταχυδρομικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    
    # Hospitality (55-56)
    "55": ("2.1", "Καταλύματα (ξενοδοχεία)", "E3_561_003", "category1_3", 2, "high"),
    "56": ("1.1", "Εστίαση", "E3_561_001", "category1_1", 2, "high"),
    
    # Information & Communication (58-63)
    "58": ("1.1", "Εκδόσεις", "E3_561_001", "category1_1", 1, "high"),
    "59": ("2.1", "Παραγωγή ταινιών/ήχου", "E3_561_003", "category1_3", 1, "high"),
    "60": ("2.1", "Ραδιοτηλεόραση", "E3_561_003", "category1_3", 1, "high"),
    "61": ("2.1", "Τηλεπικοινωνίες", "E3_561_003", "category1_3", 1, "high"),
    "62": ("2.1", "Πληροφορική / Προγραμματισμός", "E3_561_003", "category1_3", 1, "high"),
    "63": ("2.1", "Υπηρεσίες πληροφόρησης", "E3_561_003", "category1_3", 1, "high"),
    
    # Financial & Insurance (64-66)
    "64": ("2.1", "Χρηματοπιστωτικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    "65": ("2.1", "Ασφαλιστικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    "66": ("2.1", "Ασφαλιστική διαμεσολάβηση", "E3_561_003", "category1_3", 1, "high"),
    
    # Real Estate (68)
    "68": ("2.1", "Κτηματομεσιτικές / Ενοικιάσεις", "E3_561_003", "category1_3", 1, "high"),
    
    # Professional, Scientific, Technical (69-75)
    "69": ("2.1", "Νομικές & λογιστικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    "70": ("2.1", "Διοίκηση επιχειρήσεων / Σύμβουλοι", "E3_561_003", "category1_3", 1, "high"),
    "71": ("2.1", "Αρχιτεκτονικές & μηχανολογικές", "E3_561_003", "category1_3", 1, "high"),
    "72": ("2.1", "Έρευνα & ανάπτυξη", "E3_561_003", "category1_3", 1, "high"),
    "73": ("2.1", "Διαφήμιση & έρευνα αγοράς", "E3_561_003", "category1_3", 1, "high"),
    "74": ("2.1", "Λοιπές επαγγελματικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    "75": ("2.1", "Κτηνιατρικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
    
    # Administrative & Support (77-82)
    "77": ("2.1", "Ενοικίαση & χρηματοδοτική μίσθωση", "E3_561_003", "category1_3", 1, "high"),
    "78": ("2.1", "Δραστηριότητες απασχόλησης", "E3_561_003", "category1_3", 1, "high"),
    "79": ("2.1", "Τουριστικά γραφεία", "E3_561_003", "category1_3", 1, "high"),
    "80": ("2.1", "Ασφάλεια & ιδιωτική αστυνόμευση", "E3_561_003", "category1_3", 1, "high"),
    "81": ("2.1", "Υπηρεσίες σε κτίρια", "E3_561_003", "category1_3", 1, "high"),
    "82": ("2.1", "Διοικητική υποστήριξη", "E3_561_003", "category1_3", 1, "high"),
    
    # Education (85)
    "85": ("2.1", "Εκπαίδευση", "E3_561_003", "category1_3", 1, "high"),
    
    # Health & Social Work (86-88)
    "86": ("2.1", "Υγεία (ιατροί, κλινικές)", "E3_561_003", "category1_3", 1, "high"),
    "87": ("2.1", "Κοινωνική μέριμνα με παροχή καταλύματος", "E3_561_003", "category1_3", 1, "high"),
    "88": ("2.1", "Κοινωνική μέριμνα χωρίς κατάλυμα", "E3_561_003", "category1_3", 1, "high"),
    
    # Arts, Entertainment, Recreation (90-93)
    "90": ("2.1", "Τέχνες & ψυχαγωγία", "E3_561_003", "category1_3", 1, "high"),
    "91": ("2.1", "Βιβλιοθήκες/μουσεία", "E3_561_003", "category1_3", 1, "high"),
    "92": ("2.1", "Τυχερά παιχνίδια", "E3_561_003", "category1_3", 1, "high"),
    "93": ("2.1", "Αθλητικές δραστηριότητες", "E3_561_003", "category1_3", 1, "high"),
    
    # Other services (94-96)
    "94": ("2.1", "Οργανώσεις", "E3_561_003", "category1_3", 1, "medium"),
    "95": ("2.1", "Επισκευή Η/Υ & ειδών", "E3_561_003", "category1_3", 1, "high"),
    "96": ("2.1", "Άλλες προσωπικές υπηρεσίες", "E3_561_003", "category1_3", 1, "high"),
}


def get_classification_for_kad(kad_code: str) -> MyDataClassification:
    """Map a KAD code to the recommended myDATA classification.
    
    Uses the 2-digit prefix of the KAD to determine the sector,
    then returns the appropriate invoice type and E3 classification.
    """
    # Get 2-digit prefix
    prefix = kad_code.split(".")[0].zfill(2)
    
    if prefix in KAD_TO_MYDATA:
        inv_type, desc, e3_type, e3_cat, vat, conf = KAD_TO_MYDATA[prefix]
        return MyDataClassification(
            invoice_type=inv_type,
            invoice_type_name=desc,
            income_classification_type=e3_type,
            income_classification_category=e3_cat,
            vat_category=vat,
            description=f"ΚΑΔ {kad_code}: {desc}",
            confidence=conf,
        )
    
    # Default fallback: services invoice
    return MyDataClassification(
        invoice_type="2.1",
        invoice_type_name="Τιμολόγιο Παροχής Υπηρεσιών (default)",
        income_classification_type="E3_561_003",
        income_classification_category="category1_3",
        vat_category=1,
        description=f"ΚΑΔ {kad_code}: Δεν βρέθηκε ακριβής αντιστοίχιση, χρήση default (υπηρεσίες)",
        confidence="low",
    )


# ──────────────────────────────────────────────
# SQLite Cache
# ──────────────────────────────────────────────

class AFMCache:
    """SQLite cache for AFM lookup results. Avoids repeated SOAP calls."""
    
    def __init__(self, db_path: str = "afm_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                afm TEXT PRIMARY KEY,
                data JSON NOT NULL,
                lookup_date TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_lookup_date 
            ON businesses(lookup_date)
        """)
        conn.commit()
        conn.close()
    
    def get(self, afm: str, max_age_days: int = 90) -> Optional[BusinessInfo]:
        """Get cached business info. Returns None if not found or too old."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT data, lookup_date FROM businesses WHERE afm = ?", (afm,)
        ).fetchone()
        conn.close()
        
        if not row:
            return None
        
        data = json.loads(row[0])
        lookup_date = datetime.fromisoformat(row[1])
        age = (datetime.now() - lookup_date).days
        
        if age > max_age_days:
            return None  # Cache expired
        
        # Reconstruct BusinessInfo with KAD list
        kad_list = [KADInfo(**k) for k in data.pop("kad_list", [])]
        return BusinessInfo(**data, kad_list=kad_list)
    
    def put(self, info: BusinessInfo):
        """Store business info in cache."""
        data = asdict(info)
        now = datetime.now().isoformat()
        data["lookup_date"] = now
        
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO businesses (afm, data, lookup_date, updated_at)
               VALUES (?, ?, ?, ?)""",
            (info.afm, json.dumps(data, ensure_ascii=False), now, now)
        )
        conn.commit()
        conn.close()
    
    def list_all(self) -> list[dict]:
        """List all cached businesses (for agent reference)."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT afm, json_extract(data, '$.name'), "
            "json_extract(data, '$.primary_kad'), lookup_date "
            "FROM businesses ORDER BY updated_at DESC"
        ).fetchall()
        conn.close()
        return [
            {"afm": r[0], "name": r[1], "primary_kad": r[2], "cached": r[3]}
            for r in rows
        ]


# ──────────────────────────────────────────────
# AADE SOAP Client (RgWsPublic2)
# ──────────────────────────────────────────────

WSDL_URL = "https://www1.gsis.gr/wsaade/RgWsPublic2/RgWsPublic2?WSDL"


class AADELookupClient:
    """SOAP client for AADE RgWsPublic2 service (ΑΦΜ business lookup)."""
    
    def __init__(self, username: str, password: str, caller_afm: str = ""):
        transport = Transport(timeout=30)
        self.client = SoapClient(WSDL_URL, transport=transport)
        self.username = username
        self.password = password
        self.caller_afm = caller_afm
    
    def lookup(self, afm: str, reference_date: Optional[str] = None) -> BusinessInfo:
        """Look up business details for a given ΑΦΜ.
        
        reference_date: optional date in dd/MM/yyyy format.
        If not provided, uses current date.
        """
        if not validate_afm(afm):
            raise ValueError(f"Invalid ΑΦΜ: {afm}")
        
        # Build the request
        params = {
            "afm_called_by": self.caller_afm or "",
            "afm_called_for": afm,
        }
        
        # SOAP call with WS-Security header
        with self.client.settings(extra_http_headers={
            "Username": self.username,
            "Password": self.password,
        }):
            try:
                result = self.client.service.rgWsPublic2AfmMethod(
                    INPUT_REC={
                        "afm_called_by": params["afm_called_by"],
                        "afm_called_for": params["afm_called_for"],
                    }
                )
            except Exception as e:
                raise ConnectionError(f"AADE SOAP error: {e}")
        
        # Parse response into BusinessInfo
        basic = result.basic_rec if hasattr(result, 'basic_rec') else result
        
        info = BusinessInfo(afm=afm, name="")
        
        if hasattr(basic, 'onomasia'):
            info.name = basic.onomasia or ""
        if hasattr(basic, 'commer_title'):
            info.commercial_title = basic.commer_title or ""
        if hasattr(basic, 'doy'):
            info.doy_code = str(basic.doy or "")
        if hasattr(basic, 'doy_descr'):
            info.doy_description = basic.doy_descr or ""
        if hasattr(basic, 'legal_status_descr'):
            info.legal_status = basic.legal_status_descr or ""
        if hasattr(basic, 'deactivation_flag'):
            info.is_active = str(basic.deactivation_flag) == "1"
        if hasattr(basic, 'firm_flag_descr'):
            info.is_business = "ΕΠΙΤΗΔΕΥΜΑΤΙΑΣ" in str(basic.firm_flag_descr or "").upper()
        
        # Address
        if hasattr(basic, 'postal_address'):
            info.address_street = basic.postal_address or ""
        if hasattr(basic, 'postal_address_no'):
            info.address_number = basic.postal_address_no or ""
        if hasattr(basic, 'postal_zip_code'):
            info.address_postal_code = basic.postal_zip_code or ""
        if hasattr(basic, 'postal_area_description'):
            info.address_city = basic.postal_area_description or ""
        
        # KAD codes (activities)
        if hasattr(result, 'firm_act_tab') and result.firm_act_tab:
            activities = result.firm_act_tab
            if hasattr(activities, 'item'):
                for act in activities.item:
                    kad = KADInfo(
                        kad_code=str(act.firm_act_code or ""),
                        kad_description=str(act.firm_act_descr or ""),
                        kad_kind=str(act.firm_act_kind_descr or ""),
                        kad_kind_code=int(act.firm_act_kind or 2),
                    )
                    info.kad_list.append(kad)
                    if kad.kad_kind_code == 1:
                        info.primary_kad = kad.kad_code
        
        # If no primary KAD found, use first one
        if not info.primary_kad and info.kad_list:
            info.primary_kad = info.kad_list[0].kad_code
        
        return info


# ──────────────────────────────────────────────
# Main Lookup Class (combines all components)
# ──────────────────────────────────────────────

class AFMLookup:
    """Combined ΑΦΜ validation, AADE lookup, KAD mapping, and caching.
    
    This is the main class the agent uses.
    """
    
    def __init__(self, gsis_username: str = "", gsis_password: str = "",
                 caller_afm: str = "", cache_path: str = "afm_cache.db"):
        self.cache = AFMCache(cache_path)
        self._soap_client = None
        
        if gsis_username and gsis_password:
            self._soap_client = AADELookupClient(
                gsis_username, gsis_password, caller_afm
            )
    
    @classmethod
    def from_env(cls) -> "AFMLookup":
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            gsis_username=os.environ.get("GSIS_AFM_USERNAME", ""),
            gsis_password=os.environ.get("GSIS_AFM_PASSWORD", ""),
            caller_afm=os.environ.get("GSIS_CALLER_AFM", ""),
        )
    
    def validate(self, afm: str) -> bool:
        """Validate ΑΦΜ check digit locally."""
        return validate_afm(afm)
    
    def get_business_info(self, afm: str, force_refresh: bool = False) -> Optional[BusinessInfo]:
        """Get business info: first from cache, then from AADE if needed."""
        afm = afm.strip().replace("EL", "").replace("el", "")
        
        if not self.validate(afm):
            return None
        
        # Check cache first
        if not force_refresh:
            cached = self.cache.get(afm)
            if cached:
                return cached
        
        # Call AADE SOAP service
        if not self._soap_client:
            return None  # No credentials configured
        
        info = self._soap_client.lookup(afm)
        
        # Cache the result
        self.cache.put(info)
        
        return info
    
    def get_classification(self, afm: str) -> Optional[MyDataClassification]:
        """Get the recommended myDATA classification for a business ΑΦΜ.
        
        Looks up the business, finds its primary KAD, and maps it
        to invoice type + income classification.
        """
        info = self.get_business_info(afm)
        if not info or not info.primary_kad:
            return None
        
        return get_classification_for_kad(info.primary_kad)
    
    def get_classification_from_kad(self, kad_code: str) -> MyDataClassification:
        """Get classification directly from a KAD code (no lookup needed)."""
        return get_classification_for_kad(kad_code)
    
    def add_manual(self, afm: str, name: str, primary_kad: str, 
                   city: str = "", doy: str = ""):
        """Manually add a business to cache (when SOAP is not available)."""
        info = BusinessInfo(
            afm=afm,
            name=name,
            primary_kad=primary_kad,
            address_city=city,
            doy_description=doy,
            kad_list=[KADInfo(
                kad_code=primary_kad,
                kad_description="Manual entry",
                kad_kind="ΚΥΡΙΑ",
                kad_kind_code=1,
            )],
        )
        self.cache.put(info)
        return info
    
    def list_cached(self) -> list[dict]:
        """List all cached businesses."""
        return self.cache.list_all()
```

## Agent Tool Additions

Add these tools to the existing MYDATA_TOOLS list:

```python
LOOKUP_TOOLS = [
    {
        "name": "lookup_afm",
        "description": (
            "Αναζήτηση στοιχείων επιχείρησης βάσει ΑΦΜ. Επιστρέφει: επωνυμία, "
            "ΔΟΥ, νομική μορφή, διεύθυνση, ΚΑΔ (κωδικοί δραστηριότητας), "
            "και αν ο ΑΦΜ είναι ενεργός. Χρησιμοποιεί cache — η πρώτη αναζήτηση "
            "καλεί AADE, οι επόμενες είναι instant."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {
                    "type": "string",
                    "description": "ΑΦΜ (9 ψηφία, χωρίς EL)"
                },
                "force_refresh": {
                    "type": "boolean",
                    "default": False,
                    "description": "True για να ξανακαλέσει AADE αντί cache"
                }
            },
            "required": ["afm"]
        }
    },
    {
        "name": "validate_afm",
        "description": (
            "Έλεγχος εγκυρότητας ΑΦΜ (check digit). Δεν καλεί AADE, "
            "ελέγχει μόνο αν ο αριθμός είναι μαθηματικά σωστός."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {"type": "string"}
            },
            "required": ["afm"]
        }
    },
    {
        "name": "get_mydata_classification",
        "description": (
            "Βρίσκει αυτόματα τον σωστό τύπο τιμολογίου, χαρακτηρισμό εσόδων "
            "(E3 code), και κατηγορία ΦΠΑ βάσει του ΚΑΔ μιας επιχείρησης. "
            "Αν δοθεί ΑΦΜ, κάνει lookup. Αν δοθεί ΚΑΔ, κάνει mapping."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {
                    "type": "string",
                    "description": "ΑΦΜ επιχείρησης (θα γίνει lookup ΚΑΔ)"
                },
                "kad_code": {
                    "type": "string",
                    "description": "ΚΑΔ κωδικός (αν τον ξέρεις ήδη)"
                }
            }
        }
    },
    {
        "name": "add_business_manually",
        "description": (
            "Προσθήκη επιχείρησης στο τοπικό cache χειροκίνητα. "
            "Χρήσιμο όταν δεν υπάρχουν AADE SOAP credentials."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {"type": "string"},
                "name": {"type": "string", "description": "Επωνυμία"},
                "primary_kad": {"type": "string", "description": "Κύριος ΚΑΔ"},
                "city": {"type": "string"},
                "doy": {"type": "string"}
            },
            "required": ["afm", "name", "primary_kad"]
        }
    },
    {
        "name": "list_cached_businesses",
        "description": "Εμφανίζει όλες τις αποθηκευμένες επιχειρήσεις στο τοπικό cache.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    }
]
```

## Handler Implementation

```python
async def handle_lookup_tool(tool_name: str, tool_input: dict, 
                              lookup: AFMLookup) -> str:
    
    if tool_name == "lookup_afm":
        info = lookup.get_business_info(
            tool_input["afm"], 
            force_refresh=tool_input.get("force_refresh", False)
        )
        if not info:
            return f"❌ ΑΦΜ {tool_input['afm']}: Δεν βρέθηκε ή δεν είναι έγκυρος"
        
        kad_str = ", ".join(
            f"{k.kad_code} ({k.kad_description})" 
            for k in info.kad_list[:5]
        )
        
        return (
            f"📋 {info.name}\n"
            f"ΑΦΜ: {info.afm}\n"
            f"ΔΟΥ: {info.doy_description}\n"
            f"Μορφή: {info.legal_status}\n"
            f"Διεύθυνση: {info.address_street} {info.address_number}, "
            f"{info.address_postal_code} {info.address_city}\n"
            f"Κατάσταση: {'✅ Ενεργός' if info.is_active else '❌ Ανενεργός'}\n"
            f"ΚΑΔ: {kad_str}\n"
            f"Κύριος ΚΑΔ: {info.primary_kad}"
        )
    
    elif tool_name == "validate_afm":
        valid = lookup.validate(tool_input["afm"])
        return f"{'✅ Έγκυρος' if valid else '❌ Μη έγκυρος'} ΑΦΜ: {tool_input['afm']}"
    
    elif tool_name == "get_mydata_classification":
        if "kad_code" in tool_input and tool_input["kad_code"]:
            cls = lookup.get_classification_from_kad(tool_input["kad_code"])
        elif "afm" in tool_input and tool_input["afm"]:
            cls = lookup.get_classification(tool_input["afm"])
        else:
            return "❌ Δώσε ΑΦΜ ή ΚΑΔ"
        
        if not cls:
            return "❌ Δεν βρέθηκε αντιστοίχιση"
        
        return (
            f"📊 Προτεινόμενος χαρακτηρισμός:\n"
            f"Τύπος τιμολογίου: {cls.invoice_type} ({cls.invoice_type_name})\n"
            f"E3 κωδικός: {cls.income_classification_type}\n"
            f"Κατηγορία: {cls.income_classification_category}\n"
            f"ΦΠΑ: κατηγορία {cls.vat_category}\n"
            f"Βεβαιότητα: {cls.confidence}\n"
            f"Σημείωση: {cls.description}"
        )
    
    elif tool_name == "add_business_manually":
        info = lookup.add_manual(
            afm=tool_input["afm"],
            name=tool_input["name"],
            primary_kad=tool_input["primary_kad"],
            city=tool_input.get("city", ""),
            doy=tool_input.get("doy", ""),
        )
        return f"✅ Αποθηκεύτηκε: {info.name} (ΑΦΜ: {info.afm}, ΚΑΔ: {info.primary_kad})"
    
    elif tool_name == "list_cached_businesses":
        businesses = lookup.list_cached()
        if not businesses:
            return "Κενό cache — δεν έχουν αναζητηθεί επιχειρήσεις ακόμα."
        
        lines = [f"📁 {len(businesses)} αποθηκευμένες επιχειρήσεις:"]
        for b in businesses[:20]:
            lines.append(f"  • {b['name']} | ΑΦΜ: {b['afm']} | ΚΑΔ: {b['primary_kad']}")
        
        if len(businesses) > 20:
            lines.append(f"  ... και {len(businesses) - 20} ακόμα")
        
        return "\n".join(lines)
    
    return f"Άγνωστο tool: {tool_name}"
```

## Complete Agent Flow Example

```
Χρήστης: "Κόψε τιμολόγιο 1200€ στον 045678901"

Agent:
  1. validate_afm("045678901") → ✅ Έγκυρος
  2. lookup_afm("045678901") → 
     📋 TECH SOLUTIONS ΙΚΕ
     ΚΑΔ: 62.01 (Δραστηριότητες προγραμματισμού)
  3. get_mydata_classification(afm="045678901") →
     Τύπος: 2.1 (ΤΠΥ), E3_561_003, category1_3, ΦΠΑ 24%
  4. Agent: "Τιμολόγιο Παροχής Υπηρεσιών 1200€ + 288€ ΦΠΑ = 1488€
     προς TECH SOLUTIONS ΙΚΕ (ΑΦΜ 045678901, IT services).
     Στέλνω;"
  5. Χρήστης: "Ναι"
  6. send_mydata_invoice(...) → MARK: 400099887
  7. Agent: "✅ Εστάλη! MARK: 400099887"
```
