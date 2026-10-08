import pytest

from security.aws_jit import SESSION_SECONDS, ApprovalLedger, EphemeralCreds, mint_jit_credentials, public_view


class FakeSTS:
    def __init__(self) -> None:
        self.kwargs = {}

    def assume_role(self, **kwargs):
        self.kwargs = kwargs
        return {
            "Credentials": {
                "AccessKeyId": "ASIATESTKEY00000001",
                "SecretAccessKey": "super-secret-value",
                "SessionToken": "session-secret",
                "Expiration": "ignored",
            }
        }


def test_assume_role_is_fifteen_minutes_and_one_time():
    ledger = ApprovalLedger()
    token = ledger.issue("inc-1")
    sts = FakeSTS()
    creds = mint_jit_credentials(
        ledger=ledger,
        approval_token=token,
        incident_id="inc-1",
        role_arn="arn:aws:iam::123456789012:role/ShadowFixDeploy",
        session_name="shadowfix-inc-1",
        sts_client=sts,
    )
    assert sts.kwargs["DurationSeconds"] == SESSION_SECONDS == 900
    assert creds.access_key_id.startswith("ASIA")
    view = public_view(creds)
    assert "super-secret-value" not in str(view.public())
    assert view.access_key_id_prefix == "ASIA"
    with pytest.raises(PermissionError):
        mint_jit_credentials(
            ledger=ledger,
            approval_token=token,
            incident_id="inc-1",
            role_arn="arn:aws:iam::123456789012:role/ShadowFixDeploy",
            session_name="again",
            sts_client=sts,
        )


def test_permanent_keys_are_refused():
    with pytest.raises(ValueError):
        EphemeralCreds(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="nope",
            session_token="nope",
            expires_in_seconds=900,
            mode="live",
        )


def test_dry_run_still_requires_approval():
    ledger = ApprovalLedger()
    with pytest.raises(PermissionError):
        mint_jit_credentials(
            ledger=ledger,
            approval_token="missing",
            incident_id="inc-2",
            role_arn="",
            session_name="shadowfix",
        )
