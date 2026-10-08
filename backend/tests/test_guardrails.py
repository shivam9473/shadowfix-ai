import pytest

from security.guardrails import AnsibleTask, assert_target_allowed, scan_secrets, validate_playbook


def test_blocks_shell_command_and_rm():
    with pytest.raises(ValueError):
        AnsibleTask(name="wipe", module="ansible.builtin.shell", args={"cmd": "echo hi"})
    with pytest.raises(ValueError):
        AnsibleTask(name="wipe", module="ansible.builtin.command", args={"argv": ["echo"]})
    with pytest.raises(ValueError):
        validate_playbook(
            {
                "name": "bad",
                "hosts": "web-1",
                "tasks": [{"name": "wipe", "module": "ansible.builtin.copy", "args": {"content": "rm -rf /"}}],
            }
        )


def test_allows_copy_module():
    play = validate_playbook(
        {
            "name": "safe",
            "hosts": "web-1",
            "tasks": [{"name": "drop file", "module": "ansible.builtin.copy", "args": {"dest": "/tmp/a", "content": "ok"}}],
        }
    )
    assert play.tasks[0].module == "ansible.builtin.copy"


def test_target_allowlist():
    assert_target_allowed("shopkart", "shopkart://local")
    with pytest.raises(PermissionError):
        assert_target_allowed("shopkart", "https://example.com")


def test_secret_scan_flags_long_lived_aws_keys():
    assert scan_secrets("key AKIAIOSFODNN7EXAMPLE in the diff")
