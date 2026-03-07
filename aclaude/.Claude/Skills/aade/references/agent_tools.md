# Agent Tool Definitions for myDATA

Tool schemas compatible with Claude Agent SDK, OpenAI function calling, and LangChain.

## Tool Definitions (Claude Agent SDK format)

```python
MYDATA_TOOLS = [
    {
        "name": "send_mydata_invoice",
        "description": (
            "Στέλνει τιμολόγιο στο AADE myDATA. Υποστηρίζει τιμολόγια πώλησης (1.1), "
            "παροχής υπηρεσιών (2.1), πιστωτικά (5.1/5.2), αποδείξεις λιανικής (11.1/11.2) "
            "και άλλους τύπους. Επιστρέφει MARK (μοναδικός αριθμός καταχώρησης) σε επιτυχία. "
            "Υποστηρίζει πολλαπλά ΑΦΜ — αν δοθεί issuer_afm, φορτώνει credentials από SQLite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "ΑΦΜ εκδότη (issuer). Αν δοθεί, φορτώνει credentials από SQLite. Αν δεν δοθεί, χρησιμοποιεί default ΑΦΜ ή .env."
                },
                "counterpart_vat": {
                    "type": "string",
                    "description": "ΑΦΜ πελάτη/αντισυμβαλλόμενου (9 ψηφία)"
                },
                "invoice_type": {
                    "type": "string",
                    "enum": ["1.1", "2.1", "2.4", "3.1", "5.1", "5.2", "11.1", "11.2"],
                    "description": (
                        "Τύπος παραστατικού: "
                        "1.1=Τιμολόγιο Πώλησης, "
                        "2.1=Τιμολόγιο Παροχής Υπηρεσιών, "
                        "2.4=Συμβόλαιο-Έσοδο, "
                        "3.1=Τίτλος Κτήσης, "
                        "5.1=Πιστωτικό (συσχετιζόμενο), "
                        "5.2=Πιστωτικό (μη συσχετιζόμενο), "
                        "11.1=Απόδειξη Λιανικής, "
                        "11.2=Απόδειξη Παροχής Υπηρεσιών"
                    )
                },
                "series": {
                    "type": "string",
                    "description": "Σειρά τιμολογίου (π.χ. 'Α', 'Β', 'ΤΠΥ')"
                },
                "number": {
                    "type": "integer",
                    "description": "Αύξων αριθμός τιμολογίου"
                },
                "items": {
                    "type": "array",
                    "description": "Γραμμές τιμολογίου",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Περιγραφή υπηρεσίας/προϊόντος"
                            },
                            "net_value": {
                                "type": "number",
                                "description": "Καθαρή αξία σε EUR"
                            },
                            "vat_category": {
                                "type": "integer",
                                "enum": [1, 2, 3, 4, 5, 6, 7, 8],
                                "description": (
                                    "Κατηγορία ΦΠΑ: "
                                    "1=24%, 2=13%, 3=6%, "
                                    "4=17%(νησί), 5=9%(νησί), 6=4%(νησί), "
                                    "7=0%(απαλλαγή), 8=χωρίς ΦΠΑ"
                                )
                            },
                            "quantity": {
                                "type": "number",
                                "description": "Ποσότητα (προαιρετικό)"
                            },
                            "unit_price": {
                                "type": "number",
                                "description": "Τιμή μονάδας (προαιρετικό)"
                            }
                        },
                        "required": ["net_value", "vat_category"]
                    }
                },
                "payment_method": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4, 5, 6, 7],
                    "description": (
                        "Τρόπος πληρωμής: "
                        "1=Τράπεζα εσωτ., 2=Τράπεζα εξωτ., "
                        "3=Μετρητά, 4=Επιταγή, "
                        "5=Πίστωση, 6=Web banking, 7=POS"
                    )
                },
                "counterpart_country": {
                    "type": "string",
                    "default": "GR",
                    "description": "Κωδικός χώρας αντισυμβαλλόμενου (ISO 2-letter)"
                },
                "counterpart_name": {
                    "type": "string",
                    "description": "Επωνυμία αντισυμβαλλόμενου (υποχρεωτικό για εξωτερικό)"
                },
                "issue_date": {
                    "type": "string",
                    "description": "Ημερομηνία έκδοσης YYYY-MM-DD (default: σήμερα)"
                }
            },
            "required": ["counterpart_vat", "invoice_type", "series", "number", "items", "payment_method"]
        }
    },
    {
        "name": "get_mydata_invoices",
        "description": (
            "Ανακτά τιμολόγια από το AADE myDATA. Μπορεί να φέρει εισερχόμενα "
            "(τιμολόγια που σας εκδόθηκαν) ή εξερχόμενα (τιμολόγια που εκδόσατε). "
            "Επιστρέφει λίστα με MARK, ΑΦΜ, ποσά, ημερομηνίες."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "ΑΦΜ εκδότη για φόρτωση credentials από SQLite (προαιρετικό)"
                },
                "direction": {
                    "type": "string",
                    "enum": ["received", "sent"],
                    "description": "received=εισερχόμενα, sent=εξερχόμενα"
                },
                "date_from": {
                    "type": "string",
                    "description": "Από ημερομηνία (dd/MM/yyyy)"
                },
                "date_to": {
                    "type": "string",
                    "description": "Έως ημερομηνία (dd/MM/yyyy)"
                },
                "mark": {
                    "type": "integer",
                    "default": 0,
                    "description": "Επιστρέφει τιμολόγια με MARK > αυτού (για pagination)"
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "cancel_mydata_invoice",
        "description": (
            "Ακυρώνει τιμολόγιο στο AADE myDATA χρησιμοποιώντας το MARK του. "
            "Η ακύρωση είναι μη αναστρέψιμη. Επιστρέφει cancellation MARK σε επιτυχία."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "ΑΦΜ εκδότη για φόρτωση credentials από SQLite (προαιρετικό)"
                },
                "mark": {
                    "type": "integer",
                    "description": "MARK του τιμολογίου προς ακύρωση"
                }
            },
            "required": ["mark"]
        }
    },
    {
        "name": "get_mydata_income_summary",
        "description": (
            "Ανακτά σύνοψη εσόδων από AADE myDATA για συγκεκριμένο χρονικό διάστημα. "
            "Χρήσιμο για αναφορές, λογιστική κατάσταση, σύγκριση περιόδων."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "ΑΦΜ εκδότη για φόρτωση credentials από SQLite (προαιρετικό)"
                },
                "date_from": {
                    "type": "string",
                    "description": "Από ημερομηνία (dd/MM/yyyy)"
                },
                "date_to": {
                    "type": "string",
                    "description": "Έως ημερομηνία (dd/MM/yyyy)"
                }
            },
            "required": ["date_from", "date_to"]
        }
    },
    {
        "name": "get_mydata_expenses_summary",
        "description": (
            "Ανακτά σύνοψη εξόδων από AADE myDATA για συγκεκριμένο χρονικό διάστημα."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {
                    "type": "string",
                    "description": "ΑΦΜ εκδότη για φόρτωση credentials από SQLite (προαιρετικό)"
                },
                "date_from": {
                    "type": "string",
                    "description": "Από ημερομηνία (dd/MM/yyyy)"
                },
                "date_to": {
                    "type": "string",
                    "description": "Έως ημερομηνία (dd/MM/yyyy)"
                }
            },
            "required": ["date_from", "date_to"]
        }
    },
    {
        "name": "generate_mydata_xml",
        "description": (
            "Παράγει valid myDATA XML χωρίς να το στείλει στο AADE. "
            "Χρήσιμο για preview, validation, ή manual upload μέσω portal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "issuer_afm": {"type": "string", "description": "ΑΦΜ εκδότη (προαιρετικό)"},
                "counterpart_vat": {"type": "string"},
                "invoice_type": {"type": "string"},
                "series": {"type": "string"},
                "number": {"type": "integer"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "net_value": {"type": "number"},
                            "vat_category": {"type": "integer"},
                            "description": {"type": "string"}
                        },
                        "required": ["net_value", "vat_category"]
                    }
                },
                "payment_method": {"type": "integer"}
            },
            "required": ["counterpart_vat", "invoice_type", "series", "number", "items", "payment_method"]
        }
    },

    # ── Credential Management Tools (multi-AFM) ──

    {
        "name": "add_mydata_credentials",
        "description": (
            "Αποθηκεύει credentials myDATA (user_id, subscription_key) για ένα ΑΦΜ στη SQLite βάση. "
            "Αν το ΑΦΜ υπάρχει ήδη, ενημερώνει τα credentials. "
            "Χρήσιμο για λογιστές με πολλούς πελάτες ή επιχειρήσεις με πολλαπλά ΑΦΜ."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {
                    "type": "string",
                    "description": "ΑΦΜ (9 ψηφία)"
                },
                "user_id": {
                    "type": "string",
                    "description": "MYDATA_USER_ID από AADE"
                },
                "subscription_key": {
                    "type": "string",
                    "description": "MYDATA_SUBSCRIPTION_KEY (OCP-APIM-Subscription-Key)"
                },
                "env": {
                    "type": "string",
                    "enum": ["dev", "prod"],
                    "default": "dev",
                    "description": "Περιβάλλον: dev=sandbox, prod=production"
                },
                "label": {
                    "type": "string",
                    "description": "Περιγραφή/επωνυμία (π.χ. 'Εταιρεία Παπαδόπουλος ΑΕ')"
                }
            },
            "required": ["afm", "user_id", "subscription_key"]
        }
    },
    {
        "name": "list_mydata_credentials",
        "description": (
            "Εμφανίζει όλα τα αποθηκευμένα ΑΦΜ με τα labels τους. "
            "Δεν εμφανίζει τα κλειδιά (subscription keys) για λόγους ασφαλείας."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "remove_mydata_credentials",
        "description": (
            "Διαγράφει τα credentials myDATA για ένα ΑΦΜ από τη βάση."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {
                    "type": "string",
                    "description": "ΑΦΜ προς διαγραφή"
                }
            },
            "required": ["afm"]
        }
    },
    {
        "name": "set_default_mydata_afm",
        "description": (
            "Ορίζει ποιο ΑΦΜ θα χρησιμοποιείται αυτόματα όταν δεν δίνεται issuer_afm. "
            "Χρήσιμο για λογιστές που δουλεύουν κυρίως με ένα πελάτη."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "afm": {
                    "type": "string",
                    "description": "ΑΦΜ που θα οριστεί ως default"
                }
            },
            "required": ["afm"]
        }
    }
]
```

## Tool Handler Implementation

```python
"""
Tool handler — connects agent tool calls to the MyDataClient.
Drop this into your agent's tool processing loop.

Supports multi-AFM: if tool_input contains 'issuer_afm', the handler
creates a client for that specific AFM from the SQLite credential store.
Otherwise uses the default client (from .env or default AFM).
"""

from datetime import date
from mydata_client import MyDataClient, CredentialStore, build_invoice_xml, InvoiceData, Party, InvoiceLine, PaymentInfo, InvoiceType, VatCategory, PaymentMethod
from decimal import Decimal
import json


def _get_client(tool_input: dict, default_client: MyDataClient) -> MyDataClient:
    """Get the right MyDataClient based on issuer_afm parameter."""
    afm = tool_input.pop("issuer_afm", None)
    if afm:
        return MyDataClient.from_db(afm)
    return default_client


async def handle_mydata_tool(tool_name: str, tool_input: dict, client: MyDataClient) -> str:
    """Handle a myDATA tool call from the agent. Returns a string result.

    Args:
        tool_name: The tool name from the agent
        tool_input: The tool input dict (may contain 'issuer_afm' to override client)
        client: Default MyDataClient (used when issuer_afm is not provided)
    """

    try:
        # ── Credential management tools (no client needed) ──

        if tool_name == "add_mydata_credentials":
            store = CredentialStore()
            store.add(
                afm=tool_input["afm"],
                user_id=tool_input["user_id"],
                subscription_key=tool_input["subscription_key"],
                env=tool_input.get("env", "dev"),
                label=tool_input.get("label", ""),
            )
            return f"Credentials saved for AFM {tool_input['afm']} ({tool_input.get('label', '')})"

        elif tool_name == "list_mydata_credentials":
            store = CredentialStore()
            creds = store.list_all()
            if not creds:
                return "No stored credentials. Use add_mydata_credentials to add."
            default_afm = store.get_default()
            lines = []
            for c in creds:
                default_mark = " [DEFAULT]" if c["afm"] == default_afm else ""
                lines.append(
                    f"  {c['afm']} — {c['label'] or '(no label)'} "
                    f"({c['env']}){default_mark}"
                )
            return f"Stored AFMs ({len(creds)}):\n" + "\n".join(lines)

        elif tool_name == "remove_mydata_credentials":
            store = CredentialStore()
            if store.remove(tool_input["afm"]):
                return f"Credentials removed for AFM {tool_input['afm']}"
            return f"AFM {tool_input['afm']} not found in credential store"

        elif tool_name == "set_default_mydata_afm":
            store = CredentialStore()
            creds = store.get(tool_input["afm"])
            if not creds:
                return f"AFM {tool_input['afm']} not found. Add credentials first."
            store.set_default(tool_input["afm"])
            return f"Default AFM set to {tool_input['afm']} ({creds.get('label', '')})"

        # ── Invoice tools (use client, support issuer_afm override) ──

        elif tool_name == "send_mydata_invoice":
            active_client = _get_client(tool_input, client)
            issue_date = None
            if "issue_date" in tool_input:
                issue_date = date.fromisoformat(tool_input["issue_date"])

            results = await active_client.send_invoice_simple(
                counterpart_vat=tool_input["counterpart_vat"],
                invoice_type=tool_input["invoice_type"],
                series=tool_input["series"],
                number=tool_input["number"],
                items=tool_input["items"],
                payment_method=tool_input["payment_method"],
                counterpart_country=tool_input.get("counterpart_country", "GR"),
                counterpart_name=tool_input.get("counterpart_name", ""),
                issue_date=issue_date,
            )
            
            output = []
            for r in results:
                if r.success:
                    output.append(
                        f"✅ Επιτυχία! MARK: {r.invoice_mark}, "
                        f"UID: {r.invoice_uid}"
                    )
                else:
                    errors = "; ".join(
                        f"[{e['code']}] {e['message']}" for e in r.errors
                    )
                    output.append(f"❌ Σφάλμα: {errors}")
            return "\n".join(output)
        
        elif tool_name == "get_mydata_invoices":
            active_client = _get_client(tool_input, client)
            direction = tool_input["direction"]
            mark = tool_input.get("mark", 0)
            date_from = tool_input.get("date_from")
            date_to = tool_input.get("date_to")

            if direction == "received":
                invoices = await active_client.get_received_invoices(mark, date_from, date_to)
            else:
                invoices = await active_client.get_sent_invoices(mark, date_from, date_to)
            
            if not invoices:
                return "Δεν βρέθηκαν τιμολόγια για τα κριτήρια αναζήτησης."
            
            return json.dumps(invoices, ensure_ascii=False, indent=2)
        
        elif tool_name == "cancel_mydata_invoice":
            active_client = _get_client(tool_input, client)
            results = await active_client.cancel_invoice(tool_input["mark"])
            
            for r in results:
                if r.success:
                    return f"✅ Ακυρώθηκε. Cancellation MARK: {r.cancellation_mark}"
                else:
                    errors = "; ".join(
                        f"[{e['code']}] {e['message']}" for e in r.errors
                    )
                    return f"❌ Αποτυχία ακύρωσης: {errors}"
        
        elif tool_name == "get_mydata_income_summary":
            active_client = _get_client(tool_input, client)
            result = await active_client.get_income(
                tool_input["date_from"], tool_input["date_to"]
            )
            return result.decode("utf-8")

        elif tool_name == "get_mydata_expenses_summary":
            active_client = _get_client(tool_input, client)
            result = await active_client.get_expenses(
                tool_input["date_from"], tool_input["date_to"]
            )
            return result.decode("utf-8")

        elif tool_name == "generate_mydata_xml":
            active_client = _get_client(tool_input, client)
            # Build XML without sending
            lines = []
            for i, item in enumerate(tool_input["items"], 1):
                lines.append(InvoiceLine(
                    line_number=i,
                    net_value=Decimal(str(item["net_value"])),
                    vat_category=VatCategory(item.get("vat_category", 1)),
                    description=item.get("description"),
                ))

            invoice = InvoiceData(
                issuer=active_client.issuer,
                counterpart=Party(vat_number=tool_input["counterpart_vat"]),
                invoice_type=InvoiceType(tool_input["invoice_type"]),
                series=tool_input["series"],
                number=tool_input["number"],
                issue_date=date.today(),
                lines=lines,
                payments=[PaymentInfo(
                    method=PaymentMethod(tool_input["payment_method"]),
                    amount=sum(l.gross_value for l in lines),
                )],
            )
            
            xml_bytes = build_invoice_xml(invoice)
            return xml_bytes.decode("utf-8")
        
        else:
            return f"Άγνωστο tool: {tool_name}"
    
    except Exception as e:
        return f"❌ Σφάλμα: {type(e).__name__}: {str(e)}"
```

## Complete Agent Example (Claude Agent SDK)

```python
"""
Complete myDATA agent using Claude Agent SDK.
Manages Greek invoices through natural language.
"""

import asyncio
import anthropic
from mydata_client import MyDataClient

# Import tools and handler from above
from mydata_tools import MYDATA_TOOLS, handle_mydata_tool


async def run_agent():
    claude = anthropic.Anthropic()
    mydata = MyDataClient.from_db_or_env()  # Uses default AFM from DB, or falls back to .env
    
    messages = []
    system = (
        "Είσαι βοηθός διαχείρισης τιμολογίων μέσω AADE myDATA. "
        "Μπορείς να στείλεις, ανακτήσεις και ακυρώσεις τιμολόγια. "
        "Ρώτα πάντα επιβεβαίωση πριν στείλεις τιμολόγιο. "
        "Απάντα στα ελληνικά."
    )
    
    print("myDATA Agent — Γράψε 'exit' για έξοδο")
    
    while True:
        user_input = input("\n> ")
        if user_input.lower() == "exit":
            break
        
        messages.append({"role": "user", "content": user_input})
        
        while True:
            response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system,
                tools=MYDATA_TOOLS,
                messages=messages,
            )
            
            # Process response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})
            
            # Check for tool use
            tool_uses = [b for b in assistant_content if b.type == "tool_use"]
            
            if not tool_uses:
                # No tools, just text
                for block in assistant_content:
                    if hasattr(block, "text"):
                        print(f"\n{block.text}")
                break
            
            # Execute tools
            tool_results = []
            for tool_use in tool_uses:
                print(f"  ⚙️  {tool_use.name}...")
                result = await handle_mydata_tool(
                    tool_use.name, tool_use.input, mydata
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                })
            
            messages.append({"role": "user", "content": tool_results})
    
    await mydata.close()


if __name__ == "__main__":
    asyncio.run(run_agent())
```
