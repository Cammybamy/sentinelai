from __future__ import annotations

import logging
import sys

import platform

from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QCursor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

_IS_MAC = platform.system() == "Darwin"

from ..core.models import RiskLevel, Verdict
from ..core.platform_utils import cancel_pasted_command, clear_clipboard, get_frontmost_app
from ..monitors.clipboard import ClipboardMonitor
from ..storage import audit_log
from .alert_dialog import AlertDialog
from .dashboard import DashboardWindow

logger = logging.getLogger(__name__)

_RISK_COLOR: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "#dc2626",
    RiskLevel.HIGH:     "#ea580c",
    RiskLevel.MEDIUM:   "#ca8a04",
    RiskLevel.LOW:      "#2563eb",
    RiskLevel.SAFE:     "#16a34a",
}


def _make_tray_icon(color: str = "#16a34a") -> QIcon:
    size = 22
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 4, 4)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return QIcon(pix)


class TrayApp(QObject):
    def __init__(self, app: QApplication, llm_model: str = "llama3:latest") -> None:
        super().__init__()
        self._app = app
        self._llm_model = llm_model
        self._paused = False
        self._alert_active = False   # prevent stacking dialogs

        self._dashboard = DashboardWindow()

        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_make_tray_icon("#16a34a"))
        self._tray.setToolTip("SentinelAI — Monitoring clipboard")
        self._tray.activated.connect(self._on_tray_activated)

        self._build_menu()
        self._tray.show()

        self._monitor = ClipboardMonitor(llm_model=llm_model)
        self._monitor.verdict_ready.connect(self._on_verdict_ready)
        self._monitor.start()

        logger.info("SentinelAI tray started")

    def _build_menu(self) -> None:
        menu = QMenu()
        # macOS renders native menu bar menus — custom dark stylesheets make
        # the text invisible against the native background, so skip them on Mac.
        if not _IS_MAC:
            menu.setStyleSheet(
                "QMenu { background: #1a1a1a; color: #e5e5e5; border: 1px solid #333; font-size: 13px; }"
                "QMenu::item { padding: 6px 20px; }"
                "QMenu::item:selected { background: #2a2a2a; }"
                "QMenu::separator { height: 1px; background: #333; margin: 4px 0; }"
            )

        status_action = QAction("🛡  SentinelAI", self)
        status_action.setEnabled(False)
        menu.addAction(status_action)
        menu.addSeparator()

        dashboard_action = QAction("Open Dashboard", self)
        dashboard_action.triggered.connect(self._show_dashboard)
        menu.addAction(dashboard_action)

        menu.addSeparator()

        self._pause_action = QAction("Pause Monitoring", self)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit SentinelAI", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _show_dashboard(self) -> None:
        self._dashboard.refresh()
        self._dashboard.show()
        self._dashboard.raise_()
        self._dashboard.activateWindow()

    @pyqtSlot(object)
    def _on_verdict_ready(self, verdict: Verdict) -> None:
        if self._paused:
            return
        # Drop new alerts while one is already on screen — prevents dialog stacking
        # when clipboard changes rapidly or the same command is re-emitted.
        if self._alert_active:
            logger.debug("Alert already active, dropping verdict for: %s", verdict.risk_level)
            return

        self._alert_active = True
        self._tray.setIcon(_make_tray_icon(_RISK_COLOR.get(verdict.risk_level, "#dc2626")))
        self._tray.setToolTip(f"SentinelAI — {verdict.risk_level.value.upper()} risk detected")

        # Capture the active app NOW, before the dialog steals focus.
        # This lets us send Ctrl+C back to the right terminal window after Block.
        frontmost_app = get_frontmost_app()

        dialog = AlertDialog(verdict)
        dialog.exec()

        decision = dialog.user_decision

        if decision == "blocked":
            # Clear clipboard so the command can't be re-pasted.
            clear_clipboard()
            # Reset the monitor's last-seen state so the same command will
            # trigger a fresh alert if the user copies it again immediately.
            self._monitor.reset()
            # Send Ctrl+C to the terminal to cancel any already-pasted line.
            cancel_pasted_command(target_app=frontmost_app)

        self._alert_active = False

        audit_log.record(verdict, decision, source="clipboard")

        logger.info(
            "Verdict: %s | Risk: %s | Decision: %s",
            verdict.source.value,
            verdict.risk_level.value,
            decision,
        )

        # Refresh dashboard if it's open.
        if self._dashboard.isVisible():
            self._dashboard.refresh()

        if decision == "blocked":
            self._tray.showMessage(
                "Command Blocked",
                "Clipboard cleared. If you already pasted this command, it has been cancelled.",
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

        self._tray.setIcon(_make_tray_icon("#16a34a"))
        self._tray.setToolTip("SentinelAI — Monitoring clipboard")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if _IS_MAC:
            # macOS auto-shows the context menu via setContextMenu() on click —
            # don't also call popup() here or you get two menus.
            return
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_dashboard()

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_action.setText("Resume Monitoring")
            self._tray.setIcon(_make_tray_icon("#666666"))
            self._tray.setToolTip("SentinelAI — Paused")
            self._dashboard.set_monitoring_state(False)
        else:
            self._pause_action.setText("Pause Monitoring")
            self._tray.setIcon(_make_tray_icon("#16a34a"))
            self._tray.setToolTip("SentinelAI — Monitoring clipboard")
            self._dashboard.set_monitoring_state(True)

    def _quit(self) -> None:
        self._monitor.stop()
        self._monitor.wait(2000)
        self._tray.hide()
        self._dashboard.close()
        self._app.quit()


def run(llm_model: str = "llama3.1:8b") -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "SentinelAI", "System tray is not available on this desktop.")
        sys.exit(1)

    _tray_app = TrayApp(app, llm_model=llm_model)
    sys.exit(app.exec())
