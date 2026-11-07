"""Production Database Engine for ShadowFix AI.
Supports PostgreSQL with connection pooling, ACID transactions, and auto-table creation,
with automatic fallback to JSON file store when DATABASE_URL is not configured.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("shadowfix_db")

metadata = MetaData()

# ── 1. Tenants Table ──
tenants_table = Table(
    "tenants",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("plan", String(32), nullable=False, default="free"),
    Column("quota_used_today", Integer, default=0),
    Column("quota_limit", Integer, default=3),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
)

# ── 2. Users Table ──
users_table = Table(
    "users",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("email", String(255), unique=True, nullable=False, index=True),
    Column("full_name", String(255), nullable=False, default=""),
    Column("password_hash", String(255), nullable=False),
    Column("password_salt", String(64), nullable=False),
    Column("tenant_id", String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role", String(32), default="owner"),
    Column("created_at", String(64), nullable=False),
)

# ── 3. Sessions Table ──
sessions_table = Table(
    "sessions",
    metadata,
    Column("token", String(128), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("expires_at", String(64), nullable=False),
)

# ── 4. Projects Table ──
projects_table = Table(
    "projects",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(255), nullable=False),
    Column("repo_url", String(512), default=""),
    Column("branch", String(128), default="main"),
    Column("status", String(64), default="active"),
    Column("created_at", String(64), nullable=False),
)

# ── 5. Invoices Table ──
invoices_table = Table(
    "invoices",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("tenant_id", String(64), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("plan", String(32), nullable=False),
    Column("amount_cents", Integer, nullable=False),
    Column("currency", String(16), default="INR"),
    Column("gateway", String(32), nullable=False),
    Column("gateway_order_id", String(128), default=""),
    Column("gateway_payment_id", String(128), default=""),
    Column("status", String(32), default="paid"),
    Column("created_at", String(64), nullable=False),
)

# ── 6. Audit Logs Table ──
audit_logs_table = Table(
    "audit_logs",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("action", String(128), nullable=False),
    Column("details", Text, default=""),
    Column("timestamp", String(64), nullable=False, index=True),
)

# ── 7. Settings Table ──
settings_table = Table(
    "settings",
    metadata,
    Column("key", String(128), primary_key=True),
    Column("value", Text, default=""),
)


class DatabaseManager:
    """Manages relational database connections, table creation, and queries."""

    def __init__(self, db_url: str = "") -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL", "")
        self.engine: Optional[Engine] = None
        self.is_connected: bool = False

        if self.db_url:
            self._connect()

    def _connect(self) -> None:
        try:
            # Handle postgres:// vs postgresql://
            url = self.db_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)

            # Connect with robust pooling
            self.engine = create_engine(
                url,
                pool_size=15,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=300,
            )
            # Create all tables if they don't exist
            metadata.create_all(self.engine)
            self.is_connected = True
            logger.info("Successfully connected to production PostgreSQL database (%s)", url.split("@")[-1])
        except Exception as exc:
            logger.warning("Could not connect to PostgreSQL database: %s. Falling back to local store.", exc)
            self.engine = None
            self.is_connected = False

    def health_check(self) -> dict[str, Any]:
        if not self.is_connected or not self.engine:
            return {"status": "disabled_or_fallback", "engine": "json_store"}
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "connected", "engine": "postgresql", "pool_size": 15}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


db_manager = DatabaseManager()
