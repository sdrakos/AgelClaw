"""
Persistent Memory System
========================
SQLite-based memory for the self-evolving agent.

Stores:
- Tasks (pending, in_progress, completed, failed)
- Conversation history (what user asked, what agent did)
- Installed skills registry
- Agent decisions and learnings
- Scheduled recurring tasks
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

log = logging.getLogger("memory")

from agelclaw.project import get_db_path
DB_PATH = get_db_path()


class Memory:
    def __init__(self, db_path: Path = None):
        if db_path is None:
            db_path = get_db_path()
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._embedding_store = None  # lazy init

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                -- Tasks: the core of proactive behavior
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending'
                        CHECK(status IN ('pending','in_progress','completed','failed','cancelled')),
                    priority INTEGER DEFAULT 5
                        CHECK(priority BETWEEN 1 AND 10),
                    category TEXT,
                    source TEXT DEFAULT 'user',
                    
                    -- Scheduling
                    due_at TEXT,
                    recurring_cron TEXT,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    max_retries INTEGER DEFAULT 3,
                    retry_count INTEGER DEFAULT 0,
                    
                    -- Results
                    result TEXT,
                    error TEXT,
                    
                    -- Metadata
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    completed_at TEXT,
                    
                    -- Context: what the agent needs to know
                    context JSON DEFAULT '{}',
                    dependencies JSON DEFAULT '[]'
                );

                -- Conversation log: full history of interactions
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                    content TEXT NOT NULL,
                    task_id INTEGER REFERENCES tasks(id),
                    session_id TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- Skills registry: what's installed and usage stats
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    path TEXT,
                    location TEXT CHECK(location IN ('user','project')),
                    installed_at TEXT DEFAULT (datetime('now')),
                    last_used_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                        CHECK(status IN ('active','disabled','error'))
                );

                -- Agent learnings: what worked, what didn't
                CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5
                        CHECK(confidence BETWEEN 0 AND 1),
                    source_task_id INTEGER REFERENCES tasks(id),
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- Key-value store for arbitrary persistent data
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                -- User profile: persistent facts about the user
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    source TEXT DEFAULT 'stated',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(category, key)
                );

                -- Indexes for performance
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_next_run ON tasks(next_run_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
                CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_task ON conversations(task_id);
                CREATE INDEX IF NOT EXISTS idx_profile_category ON user_profile(category);
            """)

            # Migration: add is_rule column to learnings (safe if already exists)
            try:
                conn.execute("ALTER TABLE learnings ADD COLUMN is_rule INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Migration: add assigned_to column to tasks (per-subagent task assignment)
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN assigned_to TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass  # Already exists
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_assigned ON tasks(assigned_to, status)")

    # ─────────────────────────────────────────
    # Embeddings (lazy init)
    # ─────────────────────────────────────────

    @property
    def embeddings(self):
        """Lazy-init EmbeddingStore. Returns None if unavailable."""
        if self._embedding_store is None:
            try:
                from agelclaw.core.config import load_config
                cfg = load_config()
                api_key = cfg.get("openai_api_key", "")
                if api_key:
                    from agelclaw.embeddings import EmbeddingStore
                    self._embedding_store = EmbeddingStore(self.db_path, api_key)
                    if not self._embedding_store.available:
                        self._embedding_store = False  # sentinel: tried, failed
                else:
                    self._embedding_store = False
            except Exception as e:
                log.warning(f"EmbeddingStore init failed: {e}")
                self._embedding_store = False
        return self._embedding_store if self._embedding_store is not False else None

    def _embed_async(self, method_name: str, *args):
        """Fire-and-forget embedding call. Logs warning on failure, never blocks."""
        store = self.embeddings
        if store is None:
            return
        try:
            getattr(store, method_name)(*args)
        except Exception as e:
            log.warning(f"Embedding {method_name} failed: {e}")

    def semantic_search(self, query: str, tables: list = None, limit: int = 5) -> list[dict]:
        """Semantic similarity search. Falls back to empty list if embeddings unavailable."""
        store = self.embeddings
        if store is None:
            return []
        return store.search(query, tables=tables, limit=limit)

    # ─────────────────────────────────────────
    # Tasks
    # ─────────────────────────────────────────

    def add_task(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        category: str = "general",
        source: str = "user",
        due_at: str = None,
        recurring_cron: str = None,
        context: dict = None,
        dependencies: list = None,
        assigned_to: str = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                   (title, description, priority, category, source,
                    due_at, recurring_cron, next_run_at, context, dependencies, assigned_to)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    title, description, priority, category, source,
                    due_at, recurring_cron,
                    due_at or (datetime.now().isoformat() if recurring_cron else None),
                    json.dumps(context or {}),
                    json.dumps(dependencies or []),
                    assigned_to,
                ),
            )
            return cur.lastrowid

    def get_task(self, task_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def get_pending_tasks(self, limit: int = 20) -> list[dict]:
        """Get tasks ready to execute now. Excludes scheduled tasks with future next_run_at."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status IN ('pending', 'in_progress')
                   AND (next_run_at IS NULL OR next_run_at <= ?)
                   ORDER BY priority ASC, created_at ASC
                   LIMIT ?""",
                (now, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_due_tasks(self) -> list[dict]:
        """Get tasks that are due now (scheduled or recurring)."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks 
                   WHERE status = 'pending'
                   AND next_run_at IS NOT NULL
                   AND next_run_at <= ?
                   ORDER BY priority ASC, next_run_at ASC""",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_next_due_time(self) -> Optional[datetime]:
        """Get the earliest next_run_at for pending tasks (for smart scheduler sleep)."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """SELECT MIN(next_run_at) as earliest
                   FROM tasks
                   WHERE status = 'pending'
                   AND next_run_at IS NOT NULL
                   AND next_run_at > ?""",
                (now,),
            ).fetchone()
            if row and row["earliest"]:
                try:
                    return datetime.fromisoformat(row["earliest"])
                except (ValueError, TypeError):
                    return None
            return None

    def get_scheduled_tasks(self) -> list[dict]:
        """Get tasks scheduled for the future (not yet due)."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status = 'pending'
                   AND next_run_at IS NOT NULL
                   AND next_run_at > ?
                   ORDER BY next_run_at ASC""",
                (now,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recurring_tasks(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE recurring_cron IS NOT NULL AND status != 'cancelled'"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_task(self, task_id: int, **kwargs) -> None:
        allowed = {
            "title", "description", "status", "priority", "category",
            "result", "error", "due_at", "next_run_at", "last_run_at",
            "retry_count", "context", "completed_at", "assigned_to",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return

        updates["updated_at"] = datetime.now().isoformat()

        if updates.get("status") == "completed":
            updates["completed_at"] = datetime.now().isoformat()

        # Serialize dicts/lists
        for key in ("context",):
            if key in updates and isinstance(updates[key], (dict, list)):
                updates[key] = json.dumps(updates[key])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]

        with self._conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?", values
            )

    def start_task(self, task_id: int) -> None:
        self.update_task(task_id, status="in_progress")
        # Create task folder + task_info.json
        self._write_task_info(task_id)

    def complete_task(self, task_id: int, result: str = "") -> None:
        task = self.get_task(task_id)
        updates = {"status": "completed", "result": result, "last_run_at": datetime.now().isoformat()}

        # If recurring, schedule next run instead of completing
        if task and task.get("recurring_cron"):
            next_run = self._calculate_next_run(task["recurring_cron"])
            updates["status"] = "pending"
            updates["next_run_at"] = next_run

        self.update_task(task_id, **updates)

        # Write result.md and update task_info.json in the task folder
        folder = self.get_task_folder(task_id)
        if result:
            (folder / "result.md").write_text(
                f"# Task #{task_id}: {task['title'] if task else 'Unknown'}\n\n{result}",
                encoding="utf-8",
            )
        self._write_task_info(task_id)

        # Embed the completed task (with result)
        if task:
            self._embed_async("embed_task", task_id, task.get("title", ""), task.get("description", ""), result)

    def fail_task(self, task_id: int, error: str = "") -> None:
        task = self.get_task(task_id)
        retry_count = (task.get("retry_count") or 0) + 1 if task else 1
        max_retries = task.get("max_retries", 3) if task else 3

        if retry_count < max_retries:
            self.update_task(task_id, status="pending", error=error, retry_count=retry_count)
        else:
            self.update_task(task_id, status="failed", error=error, retry_count=retry_count)

        # Update task folder with error info
        self._write_task_info(task_id)

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by ID. Returns True if task existed and was deleted."""
        with self._conn() as conn:
            # Check if task exists
            task = self.get_task(task_id)
            if not task:
                return False

            # Delete related conversations first (foreign key)
            conn.execute("DELETE FROM conversations WHERE task_id = ?", (task_id,))

            # Delete the task
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

            log.info(f"Task #{task_id} deleted: {task.get('title', 'Untitled')}")
            return True

    def get_task_stats(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
            ).fetchall()
            stats = {row["status"]: row["count"] for row in rows}
            stats["total"] = sum(stats.values())
            return stats

    def get_recent_completed(self, limit: int = 10) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status = 'completed'
                   ORDER BY completed_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────
    # Per-Subagent Tasks
    # ─────────────────────────────────────────

    def get_subagent_tasks(self, subagent_name: str, status: str = None, limit: int = 20) -> list[dict]:
        """Get tasks assigned to a specific subagent, optionally filtered by status."""
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    """SELECT * FROM tasks
                       WHERE assigned_to = ? AND status = ?
                       ORDER BY priority ASC, created_at ASC
                       LIMIT ?""",
                    (subagent_name, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM tasks
                       WHERE assigned_to = ?
                       ORDER BY priority ASC, created_at ASC
                       LIMIT ?""",
                    (subagent_name, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_subagent_pending_tasks(self, subagent_name: str, limit: int = 20) -> list[dict]:
        """Get pending/in_progress tasks for a subagent that are ready to execute."""
        now = datetime.now().isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE assigned_to = ?
                   AND status IN ('pending', 'in_progress')
                   AND (next_run_at IS NULL OR next_run_at <= ?)
                   ORDER BY priority ASC, created_at ASC
                   LIMIT ?""",
                (subagent_name, now, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_subagent_stats(self, subagent_name: str) -> dict:
        """Get task statistics for a specific subagent."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM tasks WHERE assigned_to = ? GROUP BY status",
                (subagent_name,),
            ).fetchall()
            stats = {row["status"]: row["count"] for row in rows}
            stats["total"] = sum(stats.values())
            return stats

    def assign_task(self, task_id: int, subagent_name: str) -> bool:
        """Assign an existing task to a subagent. Returns True if task existed."""
        task = self.get_task(task_id)
        if not task:
            return False
        self.update_task(task_id, assigned_to=subagent_name)
        return True

    def unassign_task(self, task_id: int) -> bool:
        """Remove subagent assignment from a task (make it global). Returns True if task existed."""
        task = self.get_task(task_id)
        if not task:
            return False
        with self._conn() as conn:
            conn.execute(
                "UPDATE tasks SET assigned_to = NULL, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), task_id),
            )
        return True

    # ─────────────────────────────────────────
    # Conversations
    # ─────────────────────────────────────────

    def log_conversation(
        self,
        role: str,
        content: str,
        task_id: int = None,
        session_id: str = None,
        tokens_used: int = 0,
        cost: float = 0,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO conversations
                   (role, content, task_id, session_id, tokens_used, cost)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (role, content, task_id, session_id, tokens_used, cost),
            )
            conv_id = cur.lastrowid
        self._embed_async("embed_conversation", conv_id, content)
        return conv_id

    def get_conversation_history(
        self, session_id: str = None, limit: int = 50
    ) -> list[dict]:
        with self._conn() as conn:
            if session_id:
                rows = conn.execute(
                    """SELECT * FROM conversations 
                       WHERE session_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def get_task_conversations(self, task_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE task_id = ? ORDER BY created_at",
                (task_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────
    # Skills
    # ─────────────────────────────────────────

    def register_skill(
        self, name: str, description: str, path: str, location: str = "user"
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO skills 
                   (name, description, path, location, installed_at)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (name, description, path, location),
            )

    def record_skill_use(self, name: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE skills 
                   SET use_count = use_count + 1, last_used_at = datetime('now')
                   WHERE name = ?""",
                (name,),
            )

    def get_all_skills(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skills WHERE status = 'active' ORDER BY use_count DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────
    # Learnings
    # ─────────────────────────────────────────

    def add_learning(
        self, category: str, insight: str, confidence: float = 0.5, source_task_id: int = None
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO learnings (category, insight, confidence, source_task_id)
                   VALUES (?, ?, ?, ?)""",
                (category, insight, confidence, source_task_id),
            )
            learning_id = cur.lastrowid
        self._embed_async("embed_learning", learning_id, category, insight)
        return learning_id

    def get_learnings(self, category: str = None, limit: int = 20) -> list[dict]:
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    """SELECT * FROM learnings WHERE category = ?
                       ORDER BY confidence DESC, created_at DESC LIMIT ?""",
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM learnings ORDER BY confidence DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ─────────────────────────────────────────
    # Hard Rules (promoted learnings)
    # ─────────────────────────────────────────

    def get_rules(self) -> list[dict]:
        """Get all learnings promoted to hard rules."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM learnings WHERE is_rule = 1 ORDER BY created_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def promote_rule(self, learning_id: int) -> bool:
        """Promote a learning to a hard rule. Returns True if updated."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE learnings SET is_rule = 1 WHERE id = ? AND is_rule = 0",
                (learning_id,),
            )
            return cur.rowcount > 0

    def demote_rule(self, learning_id: int) -> bool:
        """Demote a hard rule back to regular learning. Returns True if updated."""
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE learnings SET is_rule = 0 WHERE id = ? AND is_rule = 1",
                (learning_id,),
            )
            return cur.rowcount > 0

    def build_rules_prompt(self) -> str:
        """Build '## HARD RULES' section for system prompt injection.
        Returns empty string if no rules exist."""
        rules = self.get_rules()
        if not rules:
            return ""
        lines = ["\n\n## HARD RULES (enforced automatically — do NOT violate these)"]
        for i, r in enumerate(rules, 1):
            lines.append(f"{i}. [{r['category']}] {r['insight']}")
        return "\n".join(lines)

    # ─────────────────────────────────────────
    # KV Store (arbitrary persistent data)
    # ─────────────────────────────────────────

    def kv_set(self, key: str, value: any) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                (key, json.dumps(value) if not isinstance(value, str) else value),
            )

    def kv_get(self, key: str, default=None):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except (json.JSONDecodeError, TypeError):
                    return row["value"]
            return default

    def kv_delete(self, key: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))

    # ─────────────────────────────────────────
    # User Profile
    # ─────────────────────────────────────────

    def set_profile(self, category: str, key: str, value: str, confidence: float = 0.8, source: str = "stated") -> None:
        """Upsert a user profile fact."""
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO user_profile (category, key, value, confidence, source, updated_at)
                   VALUES (?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(category, key) DO UPDATE SET
                       value = excluded.value,
                       confidence = excluded.confidence,
                       source = excluded.source,
                       updated_at = datetime('now')""",
                (category, key, value, confidence, source),
            )

    def get_profile(self, category: str = None) -> list[dict]:
        """Get all profile facts, optionally filtered by category."""
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM user_profile WHERE category = ? ORDER BY key",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM user_profile ORDER BY category, key"
                ).fetchall()
            return [dict(r) for r in rows]

    def delete_profile(self, category: str, key: str) -> bool:
        """Remove a profile fact. Returns True if deleted."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM user_profile WHERE category = ? AND key = ?",
                (category, key),
            )
            return cur.rowcount > 0

    def get_profile_summary(self) -> str:
        """Build formatted profile string for context injection."""
        facts = self.get_profile()
        if not facts:
            return ""

        by_category = {}
        for f in facts:
            cat = f["category"]
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f)

        lines = []
        for cat, items in by_category.items():
            parts = [f"{it['key']}: {it['value']}" for it in items]
            lines.append(f"**{cat.title()}:** {' | '.join(parts)}")

        return "\n".join(lines)

    # ─────────────────────────────────────────
    # Context builder (for agent prompt)
    # ─────────────────────────────────────────

    def build_context_summary(self) -> str:
        """
        Build a comprehensive context summary for the agent.
        This is injected into every prompt so the agent knows its state.
        """
        stats = self.get_task_stats()
        pending = self.get_pending_tasks(limit=10)
        due = self.get_due_tasks()
        recent = self.get_recent_completed(limit=5)
        skills = self.get_all_skills()
        learnings = self.get_learnings(limit=10)

        parts = []

        # User profile (first, so agent always sees it)
        profile = self.get_profile_summary()
        if profile:
            parts.append("## User Profile")
            parts.append(profile)
            parts.append("")

        # Task overview
        parts.append("## Current State")
        parts.append(f"Tasks: {stats.get('pending', 0)} pending, "
                     f"{stats.get('in_progress', 0)} in progress, "
                     f"{stats.get('completed', 0)} completed, "
                     f"{stats.get('failed', 0)} failed")

        # Due tasks (urgent)
        if due:
            parts.append("\n## ⚠️ DUE NOW (execute these first!)")
            for t in due:
                parts.append(f"- [#{t['id']}] {t['title']} (priority: {t['priority']})")
                if t.get("description"):
                    parts.append(f"  Details: {t['description'][:200]}")

        # Pending tasks
        if pending:
            parts.append("\n## Pending Tasks")
            for t in pending:
                deps = json.loads(t.get("dependencies", "[]"))
                dep_str = f" (depends on: #{', #'.join(map(str, deps))})" if deps else ""
                assign_str = f" @{t['assigned_to']}" if t.get("assigned_to") else ""
                parts.append(f"- [#{t['id']}] {t['title']} "
                           f"[priority:{t['priority']}]{dep_str}{assign_str}")

        # Per-subagent task counts
        from agelclaw.project import get_subagents_dir
        subagents_root = get_subagents_dir()
        if subagents_root.exists():
            sa_lines = []
            for sub_dir in sorted(subagents_root.iterdir()):
                if sub_dir.is_dir() and (sub_dir / "SUBAGENT.md").exists():
                    sa_stats = self.get_subagent_stats(sub_dir.name)
                    if sa_stats.get("total", 0) > 0:
                        sa_lines.append(
                            f"- {sub_dir.name}: {sa_stats.get('pending', 0)} pending, "
                            f"{sa_stats.get('in_progress', 0)} running, "
                            f"{sa_stats.get('completed', 0)} completed"
                        )
            if sa_lines:
                parts.append("\n## Subagent Tasks")
                parts.extend(sa_lines)

        # Recently completed (context)
        if recent:
            parts.append("\n## Recently Completed")
            for t in recent:
                result_preview = (t.get("result") or "")[:100]
                parts.append(f"- [#{t['id']}] {t['title']}: {result_preview}")

        # Installed skills
        if skills:
            parts.append("\n## Installed Skills")
            for s in skills:
                parts.append(f"- {s['name']} (used {s['use_count']}x)")

        # Learnings
        if learnings:
            parts.append("\n## Learnings")
            for l in learnings:
                parts.append(f"- [{l['category']}] {l['insight']}")

        # Recent conversation history (so agent knows what was discussed)
        conversations = self.get_conversation_history(session_id="shared_chat", limit=20)
        if conversations:
            parts.append("\n## Recent Conversations")
            for c in conversations:
                prefix = "User" if c["role"] == "user" else "Assistant"
                content = c["content"]
                # Truncate long messages
                if len(content) > 300:
                    content = content[:300] + "..."
                parts.append(f"- [{c.get('created_at', '')}] {prefix}: {content}")

        return "\n".join(parts)

    # ─────────────────────────────────────────
    # Task Folders
    # ─────────────────────────────────────────

    def get_task_folder(self, task_id: int) -> Path:
        """Get (and create if needed) the filesystem folder for a task.
        Subagent tasks go to subagents/<name>/tasks/task_<id>/."""
        from agelclaw.project import get_subagents_dir, get_tasks_dir
        task = self.get_task(task_id)
        if task and task.get("assigned_to"):
            folder = get_subagents_dir() / task["assigned_to"] / "tasks" / f"task_{task_id}"
        else:
            folder = get_tasks_dir() / f"task_{task_id}"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _write_task_info(self, task_id: int) -> None:
        """Write task_info.json to the task folder from DB data."""
        task = self.get_task(task_id)
        if not task:
            return
        folder = self.get_task_folder(task_id)
        info = {
            "id": task["id"],
            "title": task["title"],
            "description": task.get("description", ""),
            "status": task["status"],
            "priority": task.get("priority", 5),
            "category": task.get("category", "general"),
            "created_at": task.get("created_at", ""),
            "updated_at": task.get("updated_at", ""),
            "completed_at": task.get("completed_at", ""),
        }
        (folder / "task_info.json").write_text(
            json.dumps(info, indent=2, default=str), encoding="utf-8"
        )

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _calculate_next_run(self, cron_expression: str) -> str:
        """
        Simple cron-like calculator.
        Supports: "every_Xm", "every_Xh", "daily_HH:MM", "weekly_D_HH:MM"
        """
        now = datetime.now()

        if cron_expression.startswith("every_") and cron_expression.endswith("m"):
            minutes = int(cron_expression[6:-1])
            return (now + timedelta(minutes=minutes)).isoformat()

        elif cron_expression.startswith("every_") and cron_expression.endswith("h"):
            hours = int(cron_expression[6:-1])
            return (now + timedelta(hours=hours)).isoformat()

        elif cron_expression.startswith("daily_"):
            time_str = cron_expression[6:]
            h, m = map(int, time_str.split(":"))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run.isoformat()

        elif cron_expression.startswith("weekly_"):
            parts = cron_expression[7:].split("_")
            day = int(parts[0])  # 0=Monday
            h, m = map(int, parts[1].split(":"))
            next_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
            days_ahead = day - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_run += timedelta(days=days_ahead)
            return next_run.isoformat()

        # Default: 1 hour from now
        return (now + timedelta(hours=1)).isoformat()
