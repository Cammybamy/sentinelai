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
    "curl", "wget", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
    "bash", "sh", "zsh", "fish", "dash",
    "python", "python3", "python.exe",
    "pip", "pip3", "pip.exe",
    "sudo", "su", "doas",
    "npm", "yarn", "npx", "pnpm",
    "iex", "irm", "iwr",
    "invoke-expression", "invoke-webrequest", "start-process",
    "chmod", "chown", "rm", "del", "rmdir",
    "reg", "regedit", "schtasks", "sc.exe",
    "nohup", "nc", "ncat", "netcat", "socat",
    "cmd", "cmd.exe",
    "/bin/bash", "/bin/sh", "/usr/bin/python", "/usr/bin/python3",
])

# Pipe-to-shell patterns are a strong signal regardless of the first token.
_PIPE_SHELL_PATTERNS = (
    "| bash", "|bash", "| sh", "|sh", "| zsh", "|zsh",
    "| pwsh", "|pwsh", "| powershell", "|powershell",
    "| python", "|python",
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

    # Check if the first word is a known shell command.
    first_token = lower.split()[0].lstrip("$").rstrip(";").rstrip("(")
    return first_token in _COMMAND_STARTERS


class ClipboardMonitor(QThread):
    """
    Background thread that polls the clipboard and emits verdict_ready
    whenever a suspicious command is detected and analyzed.
    """
    verdict_ready = pyqtSignal(object)  # Verdict

    def __init__(self, poll_interval: float = 0.5, llm_model: str = "llama3.1:8b") -> None:
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

    def stop(self) -> None:
        self._running = False
