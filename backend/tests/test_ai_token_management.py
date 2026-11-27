import pytest
from saas_db import saas_store, PLANS


def test_tenant_ai_config_lifecycle():
    # Use existing shopkart demo tenant
    tenant_id = "shopkart"

    # 1. Check initial AI config defaults
    cfg = saas_store.get_tenant_ai_config(tenant_id)
    assert cfg["plan"] in PLANS
    assert "allowed_models" in cfg
    assert "monthly_token_quota" in cfg
    assert "tokens_used_this_month" in cfg

    # 2. SuperAdmin upgrades tenant to Ultra and sets Claude 3.5 API key
    saas_store.upgrade_tenant_plan(tenant_id, "ultra")
    updated = saas_store.update_tenant_ai_config(
        tenant_id,
        {
            "provider": "anthropic",
            "active_model": "claude-3-5-sonnet",
            "api_key": "sk-ant-admin-provisioned-key-999",
            "monthly_token_quota": 2_000_000,
        },
        updated_by="superadmin",
    )
    assert updated["plan"] == "ultra"
    assert updated["active_model"] == "claude-3-5-sonnet"
    assert updated["has_custom_key"] is True
    assert updated["api_key_source"] == "superadmin"
    assert updated["monthly_token_quota"] == 2_000_000

    # 3. Record token usage
    usage = saas_store.record_token_usage(tenant_id, prompt_tokens=150_000, completion_tokens=50_000, model="claude-3-5-sonnet")
    assert usage["tokens_used_this_month"] >= 200_000
    assert usage["percent_used"] > 0

    # 4. User switches model to GPT-4o (allowed on Ultra)
    user_updated = saas_store.update_tenant_ai_config(
        tenant_id,
        {"active_model": "gpt-4o", "provider": "openai"},
        updated_by="user",
    )
    assert user_updated["active_model"] == "gpt-4o"
    assert user_updated["provider"] == "openai"


def test_free_user_cannot_select_ultra_models():
    # Downgrade shopkart temporarily to free
    saas_store.upgrade_tenant_plan("shopkart", "free")

    # Free user attempting to select Claude 3.5 Sonnet must raise ValueError
    with pytest.raises(ValueError, match="not available on Free plan"):
        saas_store.update_tenant_ai_config("shopkart", {"active_model": "claude-3-5-sonnet"}, updated_by="user")

    # Restore to pro
    saas_store.upgrade_tenant_plan("shopkart", "pro")
