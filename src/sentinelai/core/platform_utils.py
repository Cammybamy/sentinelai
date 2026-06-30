from __future__ import annotations

import logging
import platform
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()

# Terminal emulators to look for when targeting Ctrl+C.
_TERMINAL_APPS = ("Terminal", "iTerm2", "iTerm", "Warp", "Hyper", "kitty", "Alacritty")


def clear_clipboard() -> None:
    """Replace clipboard contents with an empty string immediately."""
    try:
        import pyperclip
        pyperclip.copy("")
    except Exception:
        pass


def get_frontmost_app() -> str | None:
    """Return the name of the currently frontmost application (macOS only).
    Call this BEFORE showing the alert dialog so you can restore focus later."""
    if _SYSTEM != "Darwin":
        return None
    try:
        result = subprocess.run(
            [
                "osascript", "-e",
                'tell application "System Events" to get name of '
                "first application process whose frontmost is true",
            ],
            timeout=3,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def cancel_pasted_command(target_app: str | None = None) -> None:
    """
    Best-effort: send Ctrl+C to the terminal window that was active before
    the SentinelAI alert appeared, cancelling any command that was already
    pasted into the input line (but not yet executed).

    Pass `target_app` (from get_frontmost_app() captured before the dialog)
    so we can target the right terminal directly instead of guessing.
    """
    threading.Thread(target=_cancel_async, args=(target_app,), daemon=True).start()


def _cancel_async(target_app: str | None = None) -> None:
    # Give the dialog time to fully close and release the event queue.
    time.sleep(0.4)

    if _SYSTEM == "Darwin":
        _cancel_macos(target_app)
    elif _SYSTEM == "Windows":
        _cancel_windows()


def _cancel_macos(target_app: str | None = None) -> None:
    """Send Ctrl+C to a terminal window via osascript."""
    if target_app and target_app in _TERMINAL_APPS:
        # We know exactly which terminal was frontmost — activate it directly.
        script = (
            f'tell application "{target_app}" to activate\n'
            f"delay 0.15\n"
            f"tell application \"System Events\" to key code 8 using control down"
        )
    else:
        # Scan running processes for any known terminal emulator.
        apps_str = "{" + ", ".join(f'"{a}"' for a in _TERMINAL_APPS) + "}"
        script = f"""\
set terminalApps to {apps_str}
tell application "System Events"
    set runningNames to name of every application process
    repeat with appName in terminalApps
        if runningNames contains appName then
            set frontmost of process appName to true
            delay 0.15
            key code 8 using control down
            return
        end if
    end repeat
end tell"""

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            timeout=5,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and result.stderr:
            logger.warning("osascript Ctrl+C error: %s", result.stderr.strip())
    except Exception as exc:
        logger.warning("cancel_pasted_command error: %s", exc)


def _cancel_windows() -> None:
    """Send Ctrl+C via the keyboard module on Windows."""
    try:
        import keyboard  # pip install keyboard (Windows only, needs admin)
        keyboard.send("ctrl+c")
    except Exception:
        pass
