from __future__ import annotations

import platform
import subprocess
import threading
import time

_SYSTEM = platform.system()


def clear_clipboard() -> None:
    """Replace clipboard contents with an empty string immediately."""
    try:
        import pyperclip
        pyperclip.copy("")
    except Exception:
        pass


def cancel_pasted_command() -> None:
    """
    Best-effort: send Ctrl+C to whatever window regains focus after the
    SentinelAI dialog closes, cancelling any command that was already pasted
    into a terminal input line (but not yet executed).

    Safe in non-terminal apps too:
      - In bash/zsh/pwsh: cancels the typed line, shows a new prompt.
      - In a text editor or browser: Ctrl+C just copies selected text.
    """
    # Run in a background thread so the caller returns immediately.
    threading.Thread(target=_cancel_async, daemon=True).start()


def _cancel_async() -> None:
    # Give the dialog time to fully close and let the OS return focus
    # to the previous window (terminal).
    time.sleep(0.2)

    if _SYSTEM == "Darwin":
        _cancel_macos()
    elif _SYSTEM == "Windows":
        _cancel_windows()


def _cancel_macos() -> None:
    """Send Ctrl+C to the frontmost app via osascript (no extra deps needed)."""
    try:
        subprocess.run(
            [
                "osascript", "-e",
                # key code 8 = C; control down = Ctrl held
                'tell application "System Events" to key code 8 using control down',
            ],
            timeout=3,
            capture_output=True,
        )
    except Exception:
        pass


def _cancel_windows() -> None:
    """Send Ctrl+C via the keyboard module on Windows."""
    try:
        import keyboard  # pip install keyboard (Windows only, needs admin)
        keyboard.send("ctrl+c")
    except Exception:
        pass
