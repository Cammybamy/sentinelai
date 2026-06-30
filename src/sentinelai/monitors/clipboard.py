from __future__ import annotations

import logging
import time

import pyperclip
from PyQt6.QtCore import QThread, pyqtSignal

from ..core.analyzer import analyze
from ..core.models import CommandContext, Verdict

logger = logging.getLogger(__name__)

# First token of the command must match one of these to be flagged.
_COMMAND_STARTERS = frozenset([
    # Download tools
    "curl", "wget",
    # PowerShell
    "powershell", "powershell.exe", "pwsh", "pwsh.exe",
    "iex", "irm", "iwr", "invoke-expression", "invoke-webrequest", "start-process",
    # POSIX shells
    "bash", "sh", "zsh", "fish", "dash",
    # Interpreted languages (inline -c / -e / -r execution is a common attack vector)
    "python", "python3", "python.exe",
    "ruby", "ruby.exe",
    "perl", "perl.exe",
    "node", "node.exe",
    "php", "php.exe",
    "lua", "lua.exe",
    # Dynamic evaluation — exec/eval as first word catches one-liner paste attacks
    "exec", "eval",
    # Package runners
    "pip", "pip3", "pip.exe",
    "npm", "yarn", "npx", "pnpm",
    # Privilege escalation
    "sudo", "su", "doas",
    # Destructive / persistence
    "chmod", "chown", "rm", "del", "rmdir",
    "reg", "regedit", "schtasks", "sc.exe",
    # Networking / reverse shells
    "nohup", "nc", "ncat", "netcat", "socat",
    # Windows shell
    "cmd", "cmd.exe",
    # Absolute paths
    "/bin/bash", "/bin/sh", "/usr/bin/python", "/usr/bin/python3",
    "/usr/bin/ruby", "/usr/bin/perl", "/usr/bin/node",
])

# Pipe-to-shell patterns are a strong signal regardless of the first token.
_PIPE_SHELL_PATTERNS = (
    "| bash", "|bash", "| sh", "|sh", "| zsh", "|zsh",
    "| pwsh", "|pwsh", "| powershell", "|powershell",
    "| python", "|python", "| ruby", "|ruby",
    "| perl", "|perl", "| node", "|node",
)

_MIN_LENGTH = 10


def _looks_like_command(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < _MIN_LENGTH:
        return False

    # A lone URL with no spaces is not a command.
    if stripped.startswith(("http://", "https://", "ftp://")) and " " not in stripped:
        return False

    lower = stripped.lower()

    # Strong signal: downloading and piping to a shell.
    if any(p in lower for p in _PIPE_SHELL_PATTERNS):
        return True

    # Extract the first meaningful token.  Split on whitespace first, then on
    # "(" to handle call syntax like exec(...) or eval(...) with no spaces.
    first_token = lower.split()[0].lstrip("$").rstrip(";")
    first_token = first_token.split("(")[0]
    return first_token in _COMMAND_STARTERS


class ClipboardMonitor(QThread):
    """
    Background thread that polls the clipboard and emits verdict_ready
    whenever a suspicious command is detected and analyzed.
    """
    verdict_ready = pyqtSignal(object)  # Verdict

    def __init__(self, poll_interval: float = 0.5, llm_model: str = "llama3:latest") -> None:
        super().__init__()
        self._poll_interval = poll_interval
        self._llm_model = llm_model
        self._last_seen: str = ""
        self._running: bool = False

    def run(self) -> None:
        self._running = True
        logger.info("Clipboard monitor started")

        while self._running:
            try:
                text = pyperclip.paste()
                if text and text != self._last_seen:
                    self._last_seen = text
                    if _looks_like_command(text):
                        logger.debug("Suspicious clipboard content detected, analyzing…")
                        ctx = CommandContext(command=text.strip(), source="clipboard")
                        verdict = analyze(ctx, llm_model=self._llm_model)
                        if verdict.should_warn:
                            self.verdict_ready.emit(verdict)
            except Exception as exc:
                logger.warning("Clipboard monitor error: %s", exc)

            time.sleep(self._poll_interval)

        logger.info("Clipboard monitor stopped")

    def reset(self) -> None:
        """Reset tracking so the next clipboard read is treated as new content.
        Call this after clearing the clipboard on Block so the same command
        triggers a fresh alert if the user copies it again immediately."""
        self._last_seen = ""

    def stop(self) -> None:
        self._running = False
