"""Persistent SaaS database for ShadowFix AI.
Stores Users, Tenants (Workspaces), Projects, Subscriptions, and Invoices.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paths import DATA_DIR

DB_FILE = DATA_DIR / "saas_db.json"

# Plan configurations
PLANS: dict[str, dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free",
        "price_monthly": 0,
        "daily_incidents": 3,
        "max_projects": 1,
        "ai_model": "Fast / Deterministic",
        "features": [
            "3 incident runs / day",
            "1 imported repository",
            "Local AST code index",
            "Monaco diff viewer",
            "Manual diff export",
        ],
        "pr_automation": False,
        "e2b_sandbox": False,
        "aws_jit": False,
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price_monthly": 29,
        "daily_incidents": 25,
        "max_projects": 5,
        "ai_model": "Gemini 2.5 Pro",
        "features": [
            "25 incident runs / day",
            "Up to 5 imported repositories",
            "Automated GitHub PR creation",
            "Gemini 2.5 Pro intelligent repair",
            "Deep AST symbol graph",
            "Priority incident queue",
        ],
        "pr_automation": True,
        "e2b_sandbox": True,
        "aws_jit": False,
    },
    "ultra": {
        "id": "ultra",
        "name": "Ultra",
        "price_monthly": 99,
        "daily_incidents": 100,
        "max_projects": 20,
        "ai_model": "Gemini Pro + Claude 3.5",
        "features": [
            "100 incident runs / day",
            "Up to 20 imported repositories",
            "E2B cloud execution sandbox",
            "Custom test runners & chaos probes",
            "Multi-branch PR automation",
            "Role-based team seats (up to 10)",
        ],
        "pr_automation": True,
        "e2b_sandbox": True,
        "aws_jit": False,
    },
    "pro_max": {
        "id": "pro_max",
        "name": "Pro Max (Enterprise)",
        "price_monthly": 249,
        "daily_incidents": 9999,
        "max_projects": 999,
        "ai_model": "Multi-Model Consensus",
        "features": [
            "Unlimited incident runs & projects",
            "AWS 15-minute JIT session minting",
            "Multi-LLM voting consensus",
            "Dedicated Temporal durable worker",
            "Full compliance & secret guardrails",
            "Dedicated Slack/Discord desk integration",
        ],
        "pr_automation": True,
        "e2b_sandbox": True,
        "aws_jit": True,
    },
}


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


class SaaSStore:
    def __init__(self, file_path: Path = DB_FILE) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "users": {},
            "tenants": {},
            "projects": {},
            "invoices": [],
            "audit_log": [],
            "settings": {
                "global_kill_switch": False,
                "allow_registrations": True,
            },
        }
        self._load()
        self._seed_defaults()

    def _load(self) -> None:
        if self.file_path.exists():
            try:
                content = self.file_path.read_text(encoding="utf-8")
                loaded = json.loads(content)
                self._data.update(loaded)
            except Exception:
                pass

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _seed_defaults(self) -> None:
        with self._lock:
            # Seed Super Admin if missing
            super_admin_email = "admin@shadowfix.ai"
            has_super_admin = any(
                u.get("role") == "super_admin" for u in self._data["users"].values()
            )
            if not has_super_admin:
                salt = secrets.token_hex(8)
                admin_id = "user_super_admin"
                tenant_id = "tenant_master"
                self._data["tenants"][tenant_id] = {
                    "id": tenant_id,
                    "name": "ShadowFix Master HQ",
                    "owner_id": admin_id,
                    "plan": "pro_max",
                    "status": "active",
                    "quota_used_today": 0,
                    "quota_limit": 9999,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._data["users"][admin_id] = {
                    "id": admin_id,
                    "name": "Shivam (Super Admin)",
                    "email": super_admin_email,
                    "role": "super_admin",
                    "tenant_id": tenant_id,
                    "salt": salt,
                    "hash": _hash_password("Shadowfix@4321", salt),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

            # Seed Shopkart Demo Tenant and Project if missing
            if "shopkart" not in self._data["tenants"]:
                self._data["tenants"]["shopkart"] = {
                    "id": "shopkart",
                    "name": "Shopkart Demo Organization",
                    "owner_id": "user_demo",
                    "plan": "pro",
                    "status": "active",
                    "quota_used_today": 0,
                    "quota_limit": PLANS["pro"]["daily_incidents"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            if "proj_shopkart" not in self._data["projects"]:
                self._data["projects"]["proj_shopkart"] = {
                    "id": "proj_shopkart",
                    "tenant_id": "shopkart",
                    "name": "Shopkart E-Commerce",
                    "repo_url": "https://github.com/shivam9473/shadowfix-ai",
                    "branch": "main",
                    "target_url": "http://127.0.0.1:8010",
                    "test_command": "pytest demo-shopkart/api",
                    "culprit_file": "demo-shopkart/api/checkout.py",
                    "language": "python",
                    "files_indexed": 4,
                    "status": "ready",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            self._save()

    # ── User Operations ──
    def register_user(self, name: str, email: str, password: str, organization_name: str | None = None) -> dict[str, Any]:
        with self._lock:
            email_clean = email.strip().lower()
            for u in self._data["users"].values():
                if u["email"].lower() == email_clean:
                    raise ValueError("An account with this email already exists.")

            user_id = f"usr_{uuid.uuid4().hex[:10]}"
            tenant_id = f"tnt_{uuid.uuid4().hex[:10]}"
            org_name = (organization_name or f"{name.strip()}'s Workspace").strip()

            # The registering user becomes the User Admin of their new Tenant/Workspace
            tenant = {
                "id": tenant_id,
                "name": org_name,
                "owner_id": user_id,
                "plan": "free",
                "status": "active",
                "quota_used_today": 0,
                "quota_limit": PLANS["free"]["daily_incidents"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._data["tenants"][tenant_id] = tenant

            salt = secrets.token_hex(8)
            user = {
                "id": user_id,
                "name": name.strip(),
                "email": email_clean,
                "role": "user_admin",  # Customer admin
                "tenant_id": tenant_id,
                "salt": salt,
                "hash": _hash_password(password, salt),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._data["users"][user_id] = user
            self._record_audit_locked("register", f"User Admin {email_clean} created workspace {org_name}")
            self._save()
            return self._safe_user(user, tenant)

    def authenticate_user(self, email: str, password: str) -> dict[str, Any]:
        with self._lock:
            email_clean = email.strip().lower()
            user = None
            for u in self._data["users"].values():
                if u["email"].lower() == email_clean:
                    user = u
                    break
            if not user:
                raise ValueError("Invalid email or password.")

            expected_hash = _hash_password(password, user["salt"])
            if not secrets.compare_digest(expected_hash, user["hash"]):
                raise ValueError("Invalid email or password.")

            tenant = self._data["tenants"].get(user["tenant_id"]) or {}
            token = f"sfx_tok_{user['id']}_{secrets.token_hex(16)}"
            user["session_token"] = token
            self._record_audit_locked("login", f"{user['email']} ({user['role']}) logged in")
            self._save()
            safe = self._safe_user(user, tenant)
            safe["token"] = token
            return safe

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            user = self._data["users"].get(user_id)
            if not user:
                return None
            tenant = self._data["tenants"].get(user["tenant_id"]) or {}
            return self._safe_user(user, tenant)

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            for user in self._data["users"].values():
                if user.get("session_token") == token:
                    tenant = self._data["tenants"].get(user["tenant_id"]) or {}
                    return self._safe_user(user, tenant)
            return None

    def _safe_user(self, user: dict[str, Any], tenant: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "tenant_id": user["tenant_id"],
            "tenant_name": tenant.get("name", "Workspace"),
            "plan": tenant.get("plan", "free"),
            "plan_details": PLANS.get(tenant.get("plan", "free"), PLANS["free"]),
            "quota_used_today": tenant.get("quota_used_today", 0),
            "quota_limit": tenant.get("quota_limit", 3),
            "created_at": user.get("created_at"),
        }

    # ── Tenant & Subscription Operations ──
    def get_tenant(self, tenant_id: str) -> dict[str, Any] | None:
        with self._lock:
            t = self._data["tenants"].get(tenant_id)
            return dict(t) if t else None

    def list_all_tenants(self) -> list[dict[str, Any]]:
        with self._lock:
            res = []
            for t in self._data["tenants"].values():
                owner = self._data["users"].get(t.get("owner_id"), {})
                projects_count = sum(1 for p in self._data["projects"].values() if p.get("tenant_id") == t["id"])
                res.append({
                    **t,
                    "owner_name": owner.get("name", "Unknown"),
                    "owner_email": owner.get("email", "Unknown"),
                    "projects_count": projects_count,
                    "plan_info": PLANS.get(t.get("plan", "free"), PLANS["free"]),
                })
            return sorted(res, key=lambda x: x.get("created_at", ""), reverse=True)

    def upgrade_tenant_plan(self, tenant_id: str, new_plan: str, payment_method: str = "card_demo") -> dict[str, Any]:
        with self._lock:
            if new_plan not in PLANS:
                raise ValueError(f"Invalid plan '{new_plan}'. Must be one of: {list(PLANS.keys())}")
            tenant = self._data["tenants"].get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant {tenant_id} not found.")

            old_plan = tenant.get("plan", "free")
            plan_cfg = PLANS[new_plan]
            tenant["plan"] = new_plan
            tenant["quota_limit"] = plan_cfg["daily_incidents"]

            # Generate invoice
            invoice_id = f"inv_{uuid.uuid4().hex[:8]}"
            invoice = {
                "id": invoice_id,
                "tenant_id": tenant_id,
                "tenant_name": tenant.get("name"),
                "plan": new_plan,
                "amount": plan_cfg["price_monthly"],
                "currency": "USD",
                "payment_method": payment_method,
                "status": "paid",
                "date": datetime.now(timezone.utc).isoformat(),
            }
            self._data["invoices"].append(invoice)
            self._record_audit_locked("subscription_change", f"Tenant {tenant['name']} upgraded from {old_plan} to {new_plan} (${plan_cfg['price_monthly']}/mo)")
            self._save()
            return {"tenant": tenant, "invoice": invoice, "plan_info": plan_cfg}

    def set_tenant_status(self, tenant_id: str, status: str) -> dict[str, Any]:
        with self._lock:
            tenant = self._data["tenants"].get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant {tenant_id} not found.")
            tenant["status"] = status
            self._record_audit_locked("tenant_status", f"Tenant {tenant_id} status set to {status}")
            self._save()
            return tenant

    # ── Project Operations ──
    def create_project(
        self,
        tenant_id: str,
        name: str,
        repo_url: str,
        branch: str = "main",
        target_url: str = "",
        test_command: str = "",
        language: str = "python",
    ) -> dict[str, Any]:
        with self._lock:
            tenant = self._data["tenants"].get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant {tenant_id} not found.")

            # Check project limits for current plan
            plan_name = tenant.get("plan", "free")
            plan_cfg = PLANS.get(plan_name, PLANS["free"])
            current_projects = sum(1 for p in self._data["projects"].values() if p.get("tenant_id") == tenant_id)
            if current_projects >= plan_cfg["max_projects"]:
                raise PermissionError(
                    f"Plan '{plan_cfg['name']}' allows max {plan_cfg['max_projects']} project(s). "
                    f"Please upgrade to Pro, Ultra, or Pro Max to import more repositories."
                )

            project_id = f"proj_{uuid.uuid4().hex[:8]}"
            project = {
                "id": project_id,
                "tenant_id": tenant_id,
                "name": name.strip(),
                "repo_url": repo_url.strip(),
                "branch": (branch or "main").strip(),
                "target_url": target_url.strip(),
                "test_command": test_command.strip(),
                "language": language.lower(),
                "files_indexed": 0,
                "status": "ready",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._data["projects"][project_id] = project
            self._record_audit_locked("project_create", f"Tenant {tenant['name']} imported project '{name}' ({repo_url})")
            self._save()
            return project

    def list_projects_for_tenant(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock:
            projects = [p for p in self._data["projects"].values() if p.get("tenant_id") == tenant_id]
            return sorted(projects, key=lambda x: x.get("created_at", ""), reverse=True)

    def list_all_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            res = []
            for p in self._data["projects"].values():
                tenant = self._data["tenants"].get(p.get("tenant_id"), {})
                res.append({
                    **p,
                    "tenant_name": tenant.get("name", "Unknown"),
                    "plan": tenant.get("plan", "free"),
                })
            return sorted(res, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_project(self, project_id: str, tenant_id: str | None = None) -> bool:
        with self._lock:
            p = self._data["projects"].get(project_id)
            if not p:
                return False
            if tenant_id and p.get("tenant_id") != tenant_id:
                raise PermissionError("Access denied.")
            del self._data["projects"][project_id]
            self._record_audit_locked("project_delete", f"Deleted project {project_id}")
            self._save()
            return True

    def update_project_index(self, project_id: str, files_indexed: int) -> dict[str, Any]:
        with self._lock:
            p = self._data["projects"].get(project_id)
            if not p:
                raise KeyError(project_id)
            p["files_indexed"] = files_indexed
            p["status"] = "indexed"
            self._save()
            return p

    # ── Super Admin KPI & Analytics ──
    def get_superadmin_metrics(self) -> dict[str, Any]:
        with self._lock:
            tenants = list(self._data["tenants"].values())
            users = list(self._data["users"].values())
            projects = list(self._data["projects"].values())
            invoices = self._data["invoices"]

            total_mrr = sum(
                PLANS.get(t.get("plan", "free"), {}).get("price_monthly", 0)
                for t in tenants
                if t.get("status") == "active"
            )

            plan_distribution: dict[str, int] = {}
            for t in tenants:
                plan = t.get("plan", "free")
                plan_distribution[plan] = plan_distribution.get(plan, 0) + 1

            return {
                "mrr": total_mrr,
                "total_tenants": len(tenants),
                "total_users": len(users),
                "total_projects": len(projects),
                "total_invoices": len(invoices),
                "plan_distribution": plan_distribution,
                "global_kill_switch": self._data["settings"].get("global_kill_switch", False),
            }

    def set_global_kill_switch(self, enabled: bool) -> bool:
        with self._lock:
            self._data["settings"]["global_kill_switch"] = enabled
            self._record_audit_locked("global_kill_switch", f"Global kill switch set to {enabled}")
            self._save()
            return enabled

    def get_invoices(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if tenant_id:
                return [inv for inv in reversed(self._data["invoices"]) if inv.get("tenant_id") == tenant_id]
            return list(reversed(self._data["invoices"]))

    def record_audit(self, action: str, detail: str) -> None:
        with self._lock:
            self._record_audit_locked(action, detail)
            self._save()

    def _record_audit_locked(self, action: str, detail: str) -> None:
        self._data["audit_log"].append({
            "action": action,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self._data["audit_log"] = self._data["audit_log"][-200:]

    def get_audit_log(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(reversed(self._data["audit_log"]))


# Global Singleton Store
saas_store = SaaSStore()
