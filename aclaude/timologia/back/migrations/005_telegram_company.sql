ALTER TABLE users ADD COLUMN telegram_company_id INTEGER DEFAULT NULL REFERENCES companies(id);
