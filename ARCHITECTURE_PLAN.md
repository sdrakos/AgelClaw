# Proactive Agent — Multi-Tenant Architecture Plan

## Επισκόπηση

Μετατροπή του Proactive Agent σε **εμπορικό προϊόν** με:
- Εγκατάσταση στον υπολογιστή του πελάτη (τα δικά του API keys)
- VPS μόνο για έλεγχο πληρωμής (license server)
- Δυναμική δημιουργία subagents με skills (Claude ή OpenAI)
- Απλή εγκατάσταση χωρίς τεχνικές γνώσεις

---

## 1. Αρχιτεκτονική Υψηλού Επιπέδου

```
┌─────────────────────────────────────────────────────────────┐
│                    ΥΠΟΛΟΓΙΣΤΗΣ ΠΕΛΑΤΗ                       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Proactive Agent (Local)                              │  │
│  │                                                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │  │
│  │  │ API Server  │  │   Daemon    │  │ Telegram Bot │ │  │
│  │  │ :8000       │  │   :8420     │  │ (optional)   │ │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────────┘ │  │
│  │         │                │                            │  │
│  │         ▼                ▼                            │  │
│  │  ┌──────────────────────────────────────────┐        │  │
│  │  │          Agent Router                     │        │  │
│  │  │  (επιλέγει Claude ή OpenAI ανά task)     │        │  │
│  │  └──────────────┬───────────────────────────┘        │  │
│  │                 │                                     │  │
│  │    ┌────────────┼────────────┐                       │  │
│  │    ▼            ▼            ▼                        │  │
│  │  ┌──────┐  ┌──────────┐  ┌──────────┐               │  │
│  │  │Claude│  │  OpenAI  │  │ LiteLLM  │               │  │
│  │  │Agent │  │  Agent   │  │ (other)  │               │  │
│  │  │ SDK  │  │   SDK    │  │          │               │  │
│  │  └──────┘  └──────────┘  └──────────┘               │  │
│  │                 │                                     │  │
│  │                 ▼                                     │  │
│  │  ┌──────────────────────────────────────────┐        │  │
│  │  │     Subagent Manager                      │        │  │
│  │  │  - Δημιουργεί subagents on-the-fly       │        │  │
│  │  │  - Εκτελεί tasks με skills               │        │  │
│  │  │  - Monitoring σε real-time               │        │  │
│  │  └──────────────────────────────────────────┘        │  │
│  │                 │                                     │  │
│  │                 ▼                                     │  │
│  │  ┌──────────────────────┐  ┌────────────────────┐   │  │
│  │  │ SQLite Memory        │  │ .Claude/Skills/    │   │  │
│  │  │ (tasks, convos,      │  │ (installed skills) │   │  │
│  │  │  learnings+rules,    │  │                    │   │  │
│  │  │  profile, kv_store)  │  │                    │   │  │
│  │  └──────────────────────┘  └────────────────────┘   │  │
│  │                                                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│                         │ License check (startup + daily)   │
│                         ▼                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │
                    HTTPS (encrypted)
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                       VPS (License Server)                   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  FastAPI License Server (:443)                         │  │
│  │                                                         │  │
│  │  POST /api/license/verify                              │  │
│  │    → Input: license_key, machine_id, version           │  │
│  │    → Output: {valid, plan, expires, features}          │  │
│  │                                                         │  │
│  │  POST /api/license/activate                            │  │
│  │    → Ενεργοποίηση νέου κλειδιού                        │  │
│  │                                                         │  │
│  │  GET /api/license/plans                                │  │
│  │    → Διαθέσιμα πλάνα & τιμές                           │  │
│  │                                                         │  │
│  │  POST /api/telemetry (optional)                        │  │
│  │    → Anonymous usage stats                             │  │
│  │                                                         │  │
│  │  ┌─────────────────────┐                               │  │
│  │  │ PostgreSQL          │                               │  │
│  │  │ - licenses          │                               │  │
│  │  │ - activations       │                               │  │
│  │  │ - payments          │                               │  │
│  │  │ - usage_stats       │                               │  │
│  │  └─────────────────────┘                               │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Stripe Webhook Handler                                │  │
│  │  → Αυτόματη ενεργοποίηση/ανανέωση license              │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Admin Dashboard (React)                               │  │
│  │  → Manage licenses, customers, usage                   │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Νέα Αρχεία & Δομή

### Local (Υπολογιστής Πελάτη)

```
proactive/
├── install.py                    # ΝΕΟ: One-click installer
├── setup_wizard.py               # ΝΕΟ: Interactive setup wizard (GUI)
├── config.yaml                   # ΝΕΟ: User config (αντί .env)
│
├── core/                         # ΝΕΟ: Refactored core
│   ├── __init__.py
│   ├── agent_router.py           # ΝΕΟ: Claude vs OpenAI routing
│   ├── subagent_manager.py       # ΝΕΟ: Dynamic subagent lifecycle
│   ├── license_client.py         # ΝΕΟ: License verification
│   ├── memory.py                 # ΜΕΤΑΚΙΝΗΣΗ: from memory.py
│   └── agent_config.py           # ΜΕΤΑΚΙΝΗΣΗ: from agent_config.py
│
├── agents/                       # ΝΕΟ: Agent implementations
│   ├── __init__.py
│   ├── claude_agent.py           # ΝΕΟ: Claude SDK wrapper
│   ├── openai_agent.py           # ΝΕΟ: OpenAI Agents SDK wrapper
│   └── base_agent.py             # ΝΕΟ: Abstract base
│
├── api_server.py                 # ΕΝΗΜΕΡΩΣΗ: + license middleware
├── daemon_v2.py                  # ΕΝΗΜΕΡΩΣΗ: + subagent support
├── telegram_bot.py               # ΥΠΑΡΧΕΙ
├── mem_cli.py                    # ΥΠΑΡΧΕΙ
├── skill_tools.py                # ΥΠΑΡΧΕΙ
│
├── react-claude-chat/            # ΕΝΗΜΕΡΩΣΗ: + subagent monitoring UI
│   └── src/components/
│       ├── SubagentPanel.tsx      # ΝΕΟ: Live subagent viewer
│       ├── SetupWizard.tsx        # ΝΕΟ: First-run web setup
│       └── CostDashboard.tsx      # ΝΕΟ: Token/cost tracking
│
├── data/                         # Τοπικά δεδομένα (δεν ανεβαίνουν)
│   └── agent_memory.db
├── logs/
└── .Claude/Skills/               # Installed skills
```

### VPS (License Server)

```
license-server/
├── main.py                       # FastAPI server
├── models.py                     # SQLAlchemy models
├── auth.py                       # License key generation/validation
├── stripe_webhook.py             # Payment processing
├── admin/                        # Admin dashboard
│   └── (React app)
├── alembic/                      # DB migrations
└── docker-compose.yml            # Deployment
```

---

## 3. Agent Router — Επιλογή Claude ή OpenAI

### `core/agent_router.py`

```python
"""
Agent Router
=============
Επιλέγει ποιο SDK θα χρησιμοποιηθεί (Claude ή OpenAI) ανά task,
με βάση: ρυθμίσεις χρήστη, κόστος, διαθεσιμότητα, task type.
"""

from dataclasses import dataclass
from enum import Enum

class Provider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    AUTO = "auto"  # Αυτόματη επιλογή βάσει κόστους

@dataclass
class AgentConfig:
    provider: Provider
    model: str          # e.g. "sonnet", "gpt-4.1"
    max_turns: int = 30
    temperature: float = 0.7

# Αντιστοίχιση task type → προτεινόμενο provider
TASK_ROUTING = {
    "code_review":    AgentConfig(Provider.CLAUDE, "sonnet"),
    "code_generation": AgentConfig(Provider.CLAUDE, "sonnet"),
    "research":       AgentConfig(Provider.OPENAI, "gpt-4.1"),
    "data_analysis":  AgentConfig(Provider.OPENAI, "gpt-4.1"),
    "creative":       AgentConfig(Provider.CLAUDE, "opus"),
    "simple":         AgentConfig(Provider.OPENAI, "gpt-4.1-mini"),
    "default":        AgentConfig(Provider.AUTO, "auto"),
}

class AgentRouter:
    def __init__(self, config: dict):
        self.default_provider = Provider(config.get("default_provider", "auto"))
        self.claude_key = config.get("anthropic_api_key")
        self.openai_key = config.get("openai_api_key")
        self.cost_limit_daily = config.get("cost_limit_daily", 10.0)  # USD

    def route(self, task_type: str = "default", prefer: str = None) -> AgentConfig:
        """Αποφασίζει ποιο provider/model να χρησιμοποιηθεί."""

        # Αν ο χρήστης ζητάει συγκεκριμένο
        if prefer:
            return self._resolve_preference(prefer)

        # Αν υπάρχει routing rule
        if task_type in TASK_ROUTING:
            config = TASK_ROUTING[task_type]
            # Fallback αν δεν υπάρχει κλειδί
            if config.provider == Provider.CLAUDE and not self.claude_key:
                return AgentConfig(Provider.OPENAI, "gpt-4.1")
            if config.provider == Provider.OPENAI and not self.openai_key:
                return AgentConfig(Provider.CLAUDE, "sonnet")
            return config

        # Auto: επέλεξε βάσει κόστους
        return self._auto_route()

    def _auto_route(self) -> AgentConfig:
        """Αυτόματη επιλογή βάσει διαθεσιμότητας και κόστους."""
        if self.claude_key and self.openai_key:
            # Προτίμησε Claude για code, OpenAI για γενικά
            return AgentConfig(Provider.CLAUDE, "sonnet")
        elif self.claude_key:
            return AgentConfig(Provider.CLAUDE, "sonnet")
        elif self.openai_key:
            return AgentConfig(Provider.OPENAI, "gpt-4.1")
        else:
            raise ValueError("No API key configured")

    def _resolve_preference(self, prefer: str) -> AgentConfig:
        if prefer.startswith("claude"):
            return AgentConfig(Provider.CLAUDE, prefer.replace("claude/", ""))
        elif prefer.startswith("openai"):
            return AgentConfig(Provider.OPENAI, prefer.replace("openai/", ""))
        return AgentConfig(Provider.AUTO, prefer)
```

---

## 4. Subagent Manager — Δυναμική Δημιουργία

### `core/subagent_manager.py`

```python
"""
Subagent Manager
=================
Δημιουργεί, παρακολουθεί, και τερματίζει subagents on-the-fly.
Υποστηρίζει Claude subagents (via Task tool) και OpenAI subagents
(via Runner.run with agents-as-tools).
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SubagentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentInstance:
    id: str
    name: str
    provider: str           # "claude" | "openai"
    skill: Optional[str]    # Skill name αν χρησιμοποιεί
    status: SubagentStatus
    task_id: Optional[int]  # Linked task
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


class SubagentManager:
    def __init__(self, router, memory):
        self.router = router
        self.memory = memory
        self.active_agents: dict[str, SubagentInstance] = {}
        self._listeners = []  # SSE event listeners

    def create_subagent(
        self,
        name: str,
        description: str,
        prompt: str,
        tools: list[str] = None,
        provider: str = "auto",
        skill: str = None,
        task_id: int = None,
    ) -> SubagentInstance:
        """Δημιουργεί νέο subagent instance."""
        agent_id = str(uuid.uuid4())[:8]

        instance = SubagentInstance(
            id=agent_id,
            name=name,
            provider=provider,
            skill=skill,
            status=SubagentStatus.PENDING,
            task_id=task_id,
            created_at=datetime.now(),
        )

        self.active_agents[agent_id] = instance
        self._emit("subagent_created", instance)
        return instance

    async def run_subagent(self, instance: SubagentInstance, input_text: str) -> str:
        """Εκτελεί τον subagent (Claude ή OpenAI)."""
        instance.status = SubagentStatus.RUNNING
        self._emit("subagent_started", instance)

        try:
            if instance.provider == "claude":
                result = await self._run_claude(instance, input_text)
            elif instance.provider == "openai":
                result = await self._run_openai(instance, input_text)
            else:
                # Auto-route
                config = self.router.route()
                instance.provider = config.provider.value
                if config.provider.value == "claude":
                    result = await self._run_claude(instance, input_text)
                else:
                    result = await self._run_openai(instance, input_text)

            instance.status = SubagentStatus.COMPLETED
            instance.result = result
            instance.completed_at = datetime.now()
            self._emit("subagent_completed", instance)
            return result

        except Exception as e:
            instance.status = SubagentStatus.FAILED
            instance.error = str(e)
            instance.completed_at = datetime.now()
            self._emit("subagent_failed", instance)
            raise

    async def _run_claude(self, instance, input_text):
        """Εκτέλεση μέσω Claude Agent SDK."""
        from claude_agent_sdk import query, ClaudeAgentOptions
        from core.agent_config import SYSTEM_PROMPT, ALLOWED_TOOLS

        options = ClaudeAgentOptions(
            system_prompt=instance.metadata.get("prompt", SYSTEM_PROMPT),
            allowed_tools=instance.metadata.get("tools", ALLOWED_TOOLS),
            permission_mode="bypassPermissions",
            cwd=str(instance.metadata.get("cwd", ".")),
            max_turns=30,
        )

        full_response = []
        async for message in query(prompt=input_text, options=options):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        full_response.append(block.text)
                        self._emit("subagent_text", {
                            "agent_id": instance.id,
                            "text": block.text,
                        })

        return "".join(full_response)

    async def _run_openai(self, instance, input_text):
        """Εκτέλεση μέσω OpenAI Agents SDK."""
        from agents import Agent, Runner, function_tool

        agent = Agent(
            name=instance.name,
            instructions=instance.metadata.get("prompt", "You are a helpful assistant."),
            model=instance.metadata.get("model", "gpt-4.1"),
        )

        result = await Runner.run(agent, input_text)
        instance.tokens_used = result.context_wrapper.usage.total_tokens
        return str(result.final_output)

    def get_active(self) -> list[SubagentInstance]:
        """Επιστρέφει ενεργούς subagents."""
        return [a for a in self.active_agents.values()
                if a.status == SubagentStatus.RUNNING]

    def get_all(self) -> list[SubagentInstance]:
        """Επιστρέφει όλους τους subagents."""
        return list(self.active_agents.values())

    def cancel(self, agent_id: str):
        """Ακυρώνει subagent."""
        if agent_id in self.active_agents:
            self.active_agents[agent_id].status = SubagentStatus.CANCELLED
            self._emit("subagent_cancelled", self.active_agents[agent_id])

    def add_listener(self, callback):
        self._listeners.append(callback)

    def _emit(self, event_type: str, data):
        for listener in self._listeners:
            listener(event_type, data)
```

---

## 5. License System

### Πλάνα

| Plan | Τιμή/μήνα | Features |
|------|-----------|----------|
| **Starter** | 9.99 | 1 device, 50 tasks/day, Claude only |
| **Pro** | 29.99 | 3 devices, unlimited tasks, Claude + OpenAI, Telegram |
| **Business** | 79.99 | 10 devices, unlimited, priority support, custom skills |
| **Enterprise** | Custom | Unlimited devices, on-premise, SLA |

### `core/license_client.py`

```python
"""
License Client
===============
Ελέγχει license στο VPS. Τρέχει:
- Στο startup (block αν invalid)
- Κάθε 24h (background check)
- Grace period 72h αν VPS unreachable
"""

import hashlib
import json
import platform
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx

LICENSE_SERVER = "https://license.proactive-agent.com/api"
CACHE_FILE = Path(__file__).parent.parent / "data" / ".license_cache"
GRACE_PERIOD_HOURS = 72


def get_machine_id() -> str:
    """Μοναδικό ID μηχανήματος (δεν αλλάζει)."""
    raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class LicenseClient:
    def __init__(self, license_key: str):
        self.license_key = license_key
        self.machine_id = get_machine_id()
        self._cache = self._load_cache()

    async def verify(self) -> dict:
        """Επαλήθευση license. Επιστρέφει plan info ή raises."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{LICENSE_SERVER}/license/verify",
                    json={
                        "license_key": self.license_key,
                        "machine_id": self.machine_id,
                        "version": "2.0.0",
                    },
                )
                data = resp.json()

                if resp.status_code == 200 and data.get("valid"):
                    self._save_cache(data)
                    return data
                else:
                    raise LicenseError(data.get("message", "Invalid license"))

        except httpx.RequestError:
            # VPS unreachable — check grace period
            return self._check_grace_period()

    def _check_grace_period(self) -> dict:
        """Αν VPS unreachable, δες cached license."""
        if not self._cache:
            raise LicenseError("Cannot verify license (server unreachable, no cache)")

        last_verified = datetime.fromisoformat(self._cache["verified_at"])
        if datetime.now() - last_verified > timedelta(hours=GRACE_PERIOD_HOURS):
            raise LicenseError(
                f"License not verified for {GRACE_PERIOD_HOURS}h. "
                "Please connect to internet."
            )

        return self._cache

    def _load_cache(self) -> dict:
        if CACHE_FILE.exists():
            try:
                return json.loads(CACHE_FILE.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self, data: dict):
        data["verified_at"] = datetime.now().isoformat()
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data))


class LicenseError(Exception):
    pass
```

---

## 6. VPS License Server

### `license-server/main.py`

```python
"""
License Server (VPS)
=====================
Minimal FastAPI server. Ελέγχει:
- Εγκυρότητα license key
- Ενεργοποιημένα devices (machine_id)
- Λήξη subscription
- Stripe webhook για αυτόματη ενεργοποίηση

Deploy: docker-compose up -d
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import secrets
import hashlib

app = FastAPI(title="Proactive Agent License Server")

# ── Models ───────────────────────────────────────
class VerifyRequest(BaseModel):
    license_key: str
    machine_id: str
    version: str

class VerifyResponse(BaseModel):
    valid: bool
    plan: str           # starter | pro | business | enterprise
    expires: str        # ISO date
    features: dict      # max_devices, max_tasks_day, providers, telegram
    message: str = ""

class ActivateRequest(BaseModel):
    license_key: str
    email: str

# ── Endpoints ────────────────────────────────────
@app.post("/api/license/verify", response_model=VerifyResponse)
async def verify_license(req: VerifyRequest):
    """Κύριο endpoint - καλείται από κάθε client."""
    license = db.get_license(req.license_key)

    if not license:
        raise HTTPException(404, "License key not found")

    if license.expires_at < datetime.now():
        return VerifyResponse(
            valid=False, plan=license.plan,
            expires=license.expires_at.isoformat(),
            features={}, message="License expired"
        )

    # Check device limit
    devices = db.get_activations(req.license_key)
    max_devices = PLAN_LIMITS[license.plan]["max_devices"]

    if req.machine_id not in [d.machine_id for d in devices]:
        if len(devices) >= max_devices:
            return VerifyResponse(
                valid=False, plan=license.plan,
                expires=license.expires_at.isoformat(),
                features={}, message=f"Max {max_devices} devices reached"
            )
        # Auto-register new device
        db.add_activation(req.license_key, req.machine_id)

    return VerifyResponse(
        valid=True,
        plan=license.plan,
        expires=license.expires_at.isoformat(),
        features=PLAN_LIMITS[license.plan],
    )

@app.post("/api/license/activate")
async def activate_license(req: ActivateRequest):
    """Ενεργοποίηση νέου license key."""
    license = db.get_license(req.license_key)
    if not license:
        raise HTTPException(404, "Invalid license key")
    if license.activated:
        raise HTTPException(400, "Already activated")

    db.activate_license(req.license_key, req.email)
    return {"status": "activated", "plan": license.plan}

# ── Plan Limits ──────────────────────────────────
PLAN_LIMITS = {
    "starter": {
        "max_devices": 1,
        "max_tasks_day": 50,
        "providers": ["claude"],
        "telegram": False,
        "subagents_max": 3,
    },
    "pro": {
        "max_devices": 3,
        "max_tasks_day": -1,  # unlimited
        "providers": ["claude", "openai"],
        "telegram": True,
        "subagents_max": 10,
    },
    "business": {
        "max_devices": 10,
        "max_tasks_day": -1,
        "providers": ["claude", "openai", "litellm"],
        "telegram": True,
        "subagents_max": -1,  # unlimited
    },
}
```

---

## 7. Setup Wizard — Εγκατάσταση για Μη-Τεχνικούς

### `install.py` — One-Click Installer

```python
"""
Proactive Agent Installer
==========================
Τρέχει: python install.py

Αυτόματα:
1. Ελέγχει Python version
2. Εγκαθιστά dependencies (pip)
3. Εγκαθιστά Node.js dependencies (npm)
4. Builds React UI
5. Δημιουργεί config.yaml
6. Εγκαθιστά PM2 globally
7. Εγκαθιστά ως Windows service (optional)
"""

import subprocess
import sys
import os
from pathlib import Path

REQUIRED_PYTHON = (3, 11)
BASE_DIR = Path(__file__).parent


def main():
    print("=" * 50)
    print("  Proactive Agent — Installer")
    print("=" * 50)
    print()

    # Step 1: Python version
    if sys.version_info < REQUIRED_PYTHON:
        print(f"ERROR: Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}+ required")
        print(f"You have: Python {sys.version}")
        input("Press Enter to exit...")
        sys.exit(1)
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor}")

    # Step 2: pip install
    print("\nInstalling Python packages...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-r",
        str(BASE_DIR / "requirements.txt")
    ], check=True)
    print("[OK] Python packages installed")

    # Step 3: npm install + build
    react_dir = BASE_DIR / "react-claude-chat"
    if react_dir.exists():
        print("\nBuilding React UI...")
        subprocess.run(["npm", "install"], cwd=str(react_dir), check=True)
        subprocess.run(["npm", "run", "build"], cwd=str(react_dir), check=True)
        print("[OK] React UI built")

    # Step 4: Create data dir
    (BASE_DIR / "data").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    print("[OK] Data directories created")

    # Step 5: Launch setup wizard
    print("\nLaunching setup wizard...")
    subprocess.run([sys.executable, str(BASE_DIR / "setup_wizard.py")])


if __name__ == "__main__":
    main()
```

### `setup_wizard.py` — Interactive Setup

```python
"""
Setup Wizard
=============
Εκτελείται μετά το install.py ή standalone.
Ρωτάει τον χρήστη:
1. License key
2. API keys (Claude/OpenAI)
3. Telegram bot (optional)
4. Port settings

Αποθηκεύει σε config.yaml
"""

import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def wizard():
    print()
    print("=" * 50)
    print("  Proactive Agent — Setup")
    print("=" * 50)
    print()

    config = {}

    # License
    print("Step 1: License Key")
    print("  Get yours at https://proactive-agent.com/pricing")
    config["license_key"] = input("  License key: ").strip()
    print()

    # API Keys
    print("Step 2: AI Provider Keys")
    print("  You need at least ONE of these:")
    print()

    claude_key = input("  Anthropic API key (sk-ant-...): ").strip()
    if claude_key:
        config["anthropic_api_key"] = claude_key

    openai_key = input("  OpenAI API key (sk-...): ").strip()
    if openai_key:
        config["openai_api_key"] = openai_key

    if not claude_key and not openai_key:
        print("  WARNING: You need at least one API key!")
        return
    print()

    # Provider preference
    print("Step 3: Default AI Provider")
    if claude_key and openai_key:
        print("  1. Auto (smart routing by task type)")
        print("  2. Claude (Anthropic)")
        print("  3. OpenAI")
        choice = input("  Choice [1]: ").strip() or "1"
        config["default_provider"] = {"1": "auto", "2": "claude", "3": "openai"}[choice]
    elif claude_key:
        config["default_provider"] = "claude"
    else:
        config["default_provider"] = "openai"
    print()

    # Telegram (optional)
    print("Step 4: Telegram Bot (optional)")
    tg_token = input("  Bot token (from @BotFather, or Enter to skip): ").strip()
    if tg_token:
        config["telegram_bot_token"] = tg_token
        tg_users = input("  Allowed Telegram user IDs (comma-separated, or Enter for all): ").strip()
        if tg_users:
            config["telegram_allowed_users"] = tg_users
    print()

    # Ports
    print("Step 5: Ports (press Enter for defaults)")
    api_port = input("  API port [8000]: ").strip() or "8000"
    daemon_port = input("  Daemon port [8420]: ").strip() or "8420"
    config["api_port"] = int(api_port)
    config["daemon_port"] = int(daemon_port)
    print()

    # Cost limit
    print("Step 6: Daily Cost Limit (USD)")
    limit = input("  Max daily spend [$10.00]: ").strip() or "10.00"
    config["cost_limit_daily"] = float(limit)
    print()

    # Save
    CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False, allow_unicode=True))
    print(f"[OK] Configuration saved to {CONFIG_PATH}")
    print()

    # Start?
    print("Setup complete! To start the agent:")
    print(f"  cd {Path(__file__).parent}")
    print(f"  python -m pm2 start ecosystem.config.js")
    print()
    print("Or for quick test:")
    print(f"  python api_server.py")
    print()
    start = input("Start now? [Y/n]: ").strip().lower()
    if start != "n":
        import subprocess, sys
        subprocess.run([sys.executable, "api_server.py"])


if __name__ == "__main__":
    wizard()
```

### `config.yaml` (παράδειγμα)

```yaml
# Proactive Agent Configuration
# Generated by setup_wizard.py

license_key: "PA-XXXX-XXXX-XXXX-XXXX"

# AI Providers (τουλάχιστον ΕΝΑ required)
anthropic_api_key: "sk-ant-..."
openai_api_key: "sk-..."
default_provider: "auto"    # auto | claude | openai

# Telegram (optional)
telegram_bot_token: ""
telegram_allowed_users: ""

# Server
api_port: 8000
daemon_port: 8420

# Limits
cost_limit_daily: 10.00     # USD
max_concurrent_tasks: 3

# Advanced (μην αλλάξεις χωρίς λόγο)
check_interval: 300          # seconds
max_tasks_per_cycle: 3
```

---

## 8. Νέα API Endpoints (api_server.py)

### Subagent Management

```python
# GET /api/subagents — Λίστα ενεργών subagents
@app.get("/api/subagents")
async def list_subagents():
    return [asdict(a) for a in subagent_manager.get_all()]

# POST /api/subagents — Δημιουργία νέου subagent
@app.post("/api/subagents")
async def create_subagent(req: CreateSubagentRequest):
    instance = subagent_manager.create_subagent(
        name=req.name,
        description=req.description,
        prompt=req.prompt,
        tools=req.tools,
        provider=req.provider,
        skill=req.skill,
    )
    # Run async
    asyncio.create_task(
        subagent_manager.run_subagent(instance, req.input_text)
    )
    return {"id": instance.id, "status": "running"}

# DELETE /api/subagents/{id} — Ακύρωση
@app.delete("/api/subagents/{agent_id}")
async def cancel_subagent(agent_id: str):
    subagent_manager.cancel(agent_id)
    return {"status": "cancelled"}

# GET /api/subagents/events — SSE stream
@app.get("/api/subagents/events")
async def subagent_events():
    # SSE stream of subagent lifecycle events
    ...

# GET /api/costs — Token/cost tracking
@app.get("/api/costs")
async def get_costs():
    return {
        "today": memory.get_daily_cost(),
        "month": memory.get_monthly_cost(),
        "limit": config["cost_limit_daily"],
        "by_provider": memory.get_costs_by_provider(),
    }

# GET /api/license — License info
@app.get("/api/license")
async def license_info():
    return license_client.get_cached_info()
```

---

## 9. React UI — Νέα Components

### SubagentPanel.tsx

Δείχνει real-time:
- Ενεργοί subagents (spinner + progress)
- Provider badge (Claude / OpenAI)
- Skill που χρησιμοποιεί
- Token usage
- Δυνατότητα ακύρωσης

### CostDashboard.tsx

Δείχνει:
- Σημερινό κόστος vs daily limit (progress bar)
- Breakdown ανά provider (Claude / OpenAI)
- Μηνιαίο σύνολο
- Tokens ανά task

### SetupWizard.tsx (Web-based alternative)

Για χρήστες που προτιμούν web UI αντί terminal:
- Step-by-step form
- License key validation (real-time)
- API key testing (makes test call)
- Telegram bot testing

---

## 10. Φάσεις Υλοποίησης

### Phase 1: Core Refactoring (1 εβδομάδα)
- [ ] Δημιουργία `core/` module structure
- [ ] `agent_router.py` — Claude/OpenAI routing
- [ ] `config.yaml` — αντικατάσταση .env
- [ ] Update `api_server.py` + `daemon_v2.py` να διαβάζουν config.yaml
- [ ] `requirements.txt` με openai-agents + claude-agent-sdk

### Phase 2: Subagent Manager (1 εβδομάδα)
- [ ] `subagent_manager.py` — lifecycle management
- [ ] `agents/claude_agent.py` — Claude SDK wrapper
- [ ] `agents/openai_agent.py` — OpenAI Agents SDK wrapper
- [ ] API endpoints `/api/subagents/*`
- [ ] SSE events για subagent monitoring
- [ ] React `SubagentPanel.tsx`

### Phase 3: License System (1 εβδομάδα)
- [ ] VPS: `license-server/` (FastAPI + PostgreSQL)
- [ ] `core/license_client.py` — verification + cache
- [ ] Stripe integration (webhooks)
- [ ] License middleware στο api_server.py
- [ ] Grace period logic (72h offline)

### Phase 4: Installation & UX (3-5 μέρες)
- [ ] `install.py` — one-click installer
- [ ] `setup_wizard.py` — interactive setup
- [ ] `requirements.txt` — all dependencies
- [ ] React `SetupWizard.tsx` (web alternative)
- [ ] React `CostDashboard.tsx`
- [ ] Installer for Windows (.exe via PyInstaller)

### Phase 5: Testing & Polish (3-5 μέρες)
- [ ] End-to-end testing (fresh install)
- [ ] Non-technical user testing
- [ ] Documentation (README, FAQ)
- [ ] Error messages σε απλά ελληνικά/αγγλικά
- [ ] Auto-update mechanism

---

## 11. Requirements

### `requirements.txt`

```
# Core
claude-agent-sdk
openai-agents
fastapi
uvicorn[standard]
pydantic
python-dotenv
pyyaml
httpx

# Telegram (optional)
python-telegram-bot

# Database
# SQLite built-in, no extra deps

# License
# httpx already included

# Development
pytest
pytest-asyncio
```

### System Requirements (πελάτης)

- **OS**: Windows 10/11, macOS 12+, Ubuntu 20.04+
- **Python**: 3.11+
- **Node.js**: 18+ (για React UI build)
- **RAM**: 4GB minimum
- **Disk**: 500MB
- **Internet**: Required (API calls + license check)

---

## 12. Ασφάλεια

### Τα κλειδιά μένουν ΤΟΠΙΚΑ
- `config.yaml` ΔΕΝ ανεβαίνει ποτέ στο VPS
- License server βλέπει μόνο: license_key + machine_id + version
- API keys (Anthropic/OpenAI) μένουν στον υπολογιστή του πελάτη

### License key format
```
PA-XXXX-XXXX-XXXX-XXXX
```
- Generated via `secrets.token_hex()` + HMAC validation
- Bound to machine_id (SHA256 hash of hardware)
- Can be deactivated remotely (stolen key protection)

### Grace Period
- Αν VPS unreachable: cached license ισχύει 72 ώρες
- Μετά: agent σταματάει (soft lock — no data loss)
- Μήνυμα: "Συνδεθείτε στο internet για επαλήθευση license"

---

## 13. Μελλοντικές Επεκτάσεις

- **Skill Marketplace**: Πώληση/διαμοιρασμός skills μεταξύ χρηστών
- **Team Mode**: Shared tasks/skills μεταξύ ομάδας
- **Mobile App**: React Native (χρησιμοποίηση skill react-native-expo)
- **Voice Agent**: OpenAI Realtime ή Claude voice
- **Auto-Update**: Silent background updates
- **Analytics Dashboard**: Usage patterns, cost optimization suggestions
