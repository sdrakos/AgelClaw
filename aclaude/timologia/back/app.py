"""FastAPI application — main entry point."""
import json
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from db import run_migrations, get_db
from auth import get_current_user, register_user, login_user, get_member_role, require_role
from config import PORT, FERNET, REPORTS_DIR


@asynccontextmanager
async def lifespan(app):
    run_migrations()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(title="Timologia API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic models ---
class RegisterReq(BaseModel):
    email: str
    password: str
    name: str

class LoginReq(BaseModel):
    email: str
    password: str

class CompanyReq(BaseModel):
    name: str
    afm: str
    aade_user_id: str = ""
    aade_subscription_key: str = ""
    aade_env: str = "dev"

class MemberReq(BaseModel):
    email: str
    role: str = "viewer"


# --- Auth endpoints ---
@app.post("/api/auth/register")
def api_register(req: RegisterReq):
    return register_user(req.email, req.password, req.name)

@app.post("/api/auth/login")
def api_login(req: LoginReq):
    return login_user(req.email, req.password)

@app.get("/api/auth/me")
async def api_me(user=Depends(get_current_user)):
    return user


# --- Company endpoints ---
@app.get("/api/companies")
async def list_companies(user=Depends(get_current_user)):
    with get_db() as conn:
        if user["role"] == "admin":
            rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
        else:
            rows = conn.execute(
                "SELECT c.* FROM companies c "
                "JOIN company_members cm ON cm.company_id=c.id "
                "WHERE cm.user_id=? ORDER BY c.name",
                (user["id"],),
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d.pop("aade_user_id", None)
        d.pop("aade_subscription_key", None)
        result.append(d)
    return result

@app.post("/api/companies")
async def create_company(req: CompanyReq, user=Depends(get_current_user)):
    encrypted_uid = FERNET.encrypt(req.aade_user_id.encode()).decode() if req.aade_user_id else ""
    encrypted_key = FERNET.encrypt(req.aade_subscription_key.encode()).decode() if req.aade_subscription_key else ""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, afm, aade_user_id, aade_subscription_key, aade_env) "
            "VALUES (?, ?, ?, ?, ?)",
            (req.name, req.afm, encrypted_uid, encrypted_key, req.aade_env),
        )
        company_id = cur.lastrowid
        conn.execute(
            "INSERT INTO company_members (user_id, company_id, role) VALUES (?, ?, 'owner')",
            (user["id"], company_id),
        )
    return {"id": company_id, "name": req.name, "afm": req.afm}

@app.put("/api/companies/{company_id}")
async def update_company(company_id: int, req: CompanyReq, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    encrypted_uid = FERNET.encrypt(req.aade_user_id.encode()).decode() if req.aade_user_id else ""
    encrypted_key = FERNET.encrypt(req.aade_subscription_key.encode()).decode() if req.aade_subscription_key else ""
    with get_db() as conn:
        conn.execute(
            "UPDATE companies SET name=?, afm=?, aade_user_id=?, aade_subscription_key=?, aade_env=? WHERE id=?",
            (req.name, req.afm, encrypted_uid, encrypted_key, req.aade_env, company_id),
        )
    return {"ok": True}

@app.post("/api/companies/{company_id}/members")
async def add_member(company_id: int, req: MemberReq, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    with get_db() as conn:
        target = conn.execute("SELECT id FROM users WHERE email=?", (req.email,)).fetchone()
        if not target:
            raise HTTPException(404, "User not found")
        conn.execute(
            "INSERT OR REPLACE INTO company_members (user_id, company_id, role) VALUES (?, ?, ?)",
            (target["id"], company_id, req.role),
        )
    return {"ok": True}

@app.delete("/api/companies/{company_id}/members/{uid}")
async def remove_member(company_id: int, uid: int, user=Depends(get_current_user)):
    require_role(user["id"], company_id, "owner")
    with get_db() as conn:
        conn.execute(
            "DELETE FROM company_members WHERE user_id=? AND company_id=?", (uid, company_id)
        )
    return {"ok": True}


# --- Admin endpoints ---
@app.get("/api/admin/users")
async def admin_list_users(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    with get_db() as conn:
        rows = conn.execute("SELECT id, email, name, role, created_at FROM users").fetchall()
    return [dict(r) for r in rows]

@app.put("/api/admin/users/{uid}")
async def admin_update_user(uid: int, request: Request, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    body = await request.json()
    with get_db() as conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (body["role"], uid))
    return {"ok": True}


# --- Entry point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=True)
