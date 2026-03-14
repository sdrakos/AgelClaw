# Timologia Database Schema

SQLite WAL mode — `back/data/timologia.db`

## users
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| email | TEXT UNIQUE | NOT NULL |
| password_hash | TEXT | bcrypt |
| name | TEXT | NOT NULL |
| role | TEXT | `user` / `admin` |
| telegram_chat_id | TEXT | Telegram chat ID (linked via bot) |
| telegram_company_id | INTEGER FK | → companies(id), active company for Telegram |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

## companies
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| name | TEXT | Επωνυμία |
| afm | TEXT UNIQUE | 9-ψήφιο ΑΦΜ |
| aade_user_id | TEXT | Fernet encrypted |
| aade_subscription_key | TEXT | Fernet encrypted |
| aade_env | TEXT | `dev` / `prod` |
| default_branch | INTEGER | DEFAULT 0 |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

## company_members
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| user_id | INTEGER FK | → users(id) ON DELETE CASCADE |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| role | TEXT | `owner` / `accountant` / `viewer` |
| | | UNIQUE(user_id, company_id) |

## invoices
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| mark | TEXT | AADE MARK identifier |
| invoice_type | TEXT | Τύπος παραστατικού |
| series | TEXT | Σειρά |
| aa | TEXT | Αύξων αριθμός |
| issue_date | DATE | Ημερομηνία έκδοσης |
| counterpart_afm | TEXT | ΑΦΜ αντισυμβαλλομένου |
| counterpart_name | TEXT | Επωνυμία αντισυμβαλλομένου |
| net_amount | REAL | Καθαρό ποσό |
| vat_amount | REAL | ΦΠΑ |
| total_amount | REAL | Σύνολο |
| direction | TEXT | `sent` / `received` |
| raw_json | TEXT | Πλήρες JSON από ΑΑΔΕ |
| synced_at | DATETIME | Τελευταίο sync |
| | | UNIQUE(company_id, mark, direction) |

## chat_sessions
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| user_id | INTEGER FK | → users(id) ON DELETE CASCADE |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| messages | TEXT | JSON array of messages |
| created_at | DATETIME | |
| updated_at | DATETIME | |

## pending_actions
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| chat_session_id | INTEGER FK | → chat_sessions(id) ON DELETE CASCADE |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| action_type | TEXT | `send_invoice` / `cancel_invoice` / ... |
| payload | TEXT | JSON — original_args for replay |
| preview | TEXT | Dry-run preview text |
| status | TEXT | `pending` / `confirmed` / `expired` |
| expires_at | DATETIME | 5 minutes TTL |
| created_at | DATETIME | |

## report_schedules
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| created_by | INTEGER FK | → users(id) |
| preset | TEXT | Report preset name |
| params | TEXT | JSON — period, direction, etc. |
| cron | TEXT | Cron expression |
| recipients | TEXT | Comma-separated emails |
| enabled | INTEGER | 0/1 |
| last_run_at | DATETIME | |

## report_history
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| schedule_id | INTEGER FK | → report_schedules(id) ON DELETE SET NULL |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| user_id | INTEGER FK | → users(id) |
| preset | TEXT | |
| params | TEXT | JSON |
| file_path | TEXT | Path to generated Excel |
| status | TEXT | `success` / `error` |
| error | TEXT | Error message if failed |
| created_at | DATETIME | |

## invitations
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| invited_by | INTEGER FK | → users(id) |
| email | TEXT | Invited email address |
| role | TEXT | `owner` / `accountant` / `viewer` |
| token | TEXT UNIQUE | Invitation token |
| status | TEXT | `pending` / `accepted` |
| expires_at | DATETIME | 7 days TTL |
| created_at | DATETIME | |

## telegram_link_tokens
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| user_id | INTEGER FK | → users(id) ON DELETE CASCADE |
| company_id | INTEGER FK | → companies(id) ON DELETE CASCADE |
| token | TEXT UNIQUE | One-time link token (`tg_...`) |
| used | INTEGER | 0/1 |
| expires_at | DATETIME | 10 minutes TTL |
| created_at | DATETIME | |

## password_resets
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | AUTOINCREMENT |
| user_id | INTEGER FK | → users(id) ON DELETE CASCADE |
| token | TEXT UNIQUE | Reset token |
| used | INTEGER | 0/1 |
| expires_at | DATETIME | 1 hour TTL |
| created_at | DATETIME | |

---

## Relationships

```
users 1──N company_members N──1 companies
users 1──N chat_sessions N──1 companies
users 1──N report_schedules
companies 1──N invoices
companies 1──N pending_actions
companies 1──N invitations
companies 1──N report_history
report_schedules 1──N report_history
users 1──N password_resets
```

## Separate DB: afm_cache.db

`back/data/afm_cache.db` — GSIS AFM lookup cache (90-day TTL)

### businesses
| Column | Type | Notes |
|--------|------|-------|
| afm | TEXT PK | 9-digit AFM |
| data | JSON | name, doy, address, activities (KAD) |
| lookup_date | TEXT | ISO datetime of lookup |
