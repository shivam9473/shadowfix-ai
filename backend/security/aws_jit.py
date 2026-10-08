"""15-minute STS sessions, minted only after a one-time admin approval."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from pydantic import BaseModel, SecretStr, field_validator

SESSION_SECONDS = 900


class ApprovalLedger:
    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def issue(self, incident_id: str) -> str:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = incident_id
        return token

    def consume(self, token: str, incident_id: str) -> None:
        found = self._tokens.pop(token, None)
        if found != incident_id:
            raise PermissionError("JIT credentials require a fresh admin approval")


class EphemeralCreds(BaseModel):
    access_key_id: str
    secret_access_key: SecretStr
    session_token: SecretStr
    expires_in_seconds: int
    mode: str

    @field_validator("access_key_id")
    @classmethod
    def must_be_temporary(cls, value: str) -> str:
        # AKIA is a long-lived IAM key. ASIA is the prefix STS uses.
        if not value.startswith("ASIA"):
            raise ValueError("permanent AWS keys are refused")
        return value

    @field_validator("expires_in_seconds")
    @classmethod
    def must_be_fifteen_minutes(cls, value: int) -> int:
        if value != SESSION_SECONDS:
            raise ValueError("session must be exactly 15 minutes")
        return value


@dataclass
class DeployResult:
    mode: str
    expires_in_seconds: int
    access_key_id_prefix: str
    message: str

    def public(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "expires_in_seconds": self.expires_in_seconds,
            "access_key_id_prefix": self.access_key_id_prefix,
            "message": self.message,
        }


def mint_jit_credentials(
    *,
    ledger: ApprovalLedger,
    approval_token: str,
    incident_id: str,
    role_arn: str,
    session_name: str,
    sts_client: Any | None = None,
) -> EphemeralCreds:
    """Consume the approval, then assume the deploy role for 900 seconds.

    Duration is not a caller argument. Dry-run (no role ARN) still returns an
    in-memory ASIA-shaped session so the approve path is the only mint path.
    """

    ledger.consume(approval_token, incident_id)
    if not role_arn:
        return EphemeralCreds(
            access_key_id="ASIASIMULATION000001",
            secret_access_key="simulation-only-discarded",
            session_token="simulation",
            expires_in_seconds=SESSION_SECONDS,
            mode="dry_run",
        )

    client = sts_client or boto3.client("sts")
    response = client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name[:64],
        DurationSeconds=SESSION_SECONDS,
    )
    raw = response["Credentials"]
    expiration = raw.get("Expiration")
    if isinstance(expiration, datetime):
        ttl = int((expiration - datetime.now(timezone.utc)).total_seconds())
        if ttl > SESSION_SECONDS + 30:
            raise PermissionError("STS returned a session longer than 15 minutes")
    return EphemeralCreds(
        access_key_id=raw["AccessKeyId"],
        secret_access_key=raw["SecretAccessKey"],
        session_token=raw["SessionToken"],
        expires_in_seconds=SESSION_SECONDS,
        mode="live",
    )


def public_view(creds: EphemeralCreds) -> DeployResult:
    if creds.mode == "live":
        message = "Temporary credentials were used for this request and were not stored."
    else:
        message = (
            "No deploy role is configured. A 15-minute simulation session was "
            "minted and discarded. Set SHADOWFIX_DEPLOY_ROLE_ARN to deploy."
        )
    return DeployResult(
        mode=creds.mode if creds.mode in {"dry_run", "live"} else "dry_run",
        expires_in_seconds=creds.expires_in_seconds,
        access_key_id_prefix=creds.access_key_id[:4],
        message=message,
    )


def session_deadline(minutes: int = 15) -> datetime:
    if minutes != 15:
        raise ValueError("only a 15-minute window is allowed")
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)
