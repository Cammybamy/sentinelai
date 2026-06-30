from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from ..core.models import RiskLevel, Verdict
from ..monitors.clipboard import ClipboardMonitor
from ..storage import audit_log
from .alert_dialog import AlertDialog

logger = logging.getLogger(__name__)

_RISK_COLOR: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "#dc2626",
    RiskLevel.HIGH:     "#ea580c",
    RiskLevel.MEDIUM:   "#ca8a04",
    RiskLevel.LOW:      "#2563eb",
    RiskLevel.SAFE:     "#16a34a",
}


def _make_tray_icon(color: str = "#16a34a") -> QIcon:
    """Generate a simple colored shield icon programmatically."""
    size = 22
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    # Draw a rounded square as a minimal shield stand-in.
    painter.drawRoundedRect(2, 2, size - 4, size - 4, 4, 4)
    painter.setPen(QColor("#ffffff"))
    painter.setFont(painter.font())
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    painter.end()
    return QIcon(pix)


class TrayApp(QObject):
    def __init__(self, app: QApplication, llm_model: str = "llama3.1:8b") -> None:
        super().__init__()
        self._app = app
        self._llm_model = llm_model
        self._paused = False
        self._pending_verdict: Verdict | None = None

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
        menu.setStyleSheet(
            "QMenu { background: #1a1a1a; color: #e5e5e5; border: 1px solid #333; }"
            "QMenu::item:selected { background: #2a2a2a; }"
        )

        status_action = QAction("🛡  SentinelAI — Active", self)
        status_action.setEnabled(False)
        menu.addAction(status_action)
        menu.addSeparator()

        self._pause_action = QAction("Pause Monitoring", self)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit SentinelAI", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    @pyqtSlot(object)
    def _on_verdict_ready(self, verdict: Verdict) -> None:
        if self._paused:
            return

        self._tray.setIcon(_make_tray_icon(_RISK_COLOR.get(verdict.risk_level, "#dc2626")))
        self._tray.setToolTip(
            f"SentinelAI — {verdict.risk_level.value.upper()} risk detected"
        )

        dialog = AlertDialog(verdict)
        dialog.exec()

        decision = dialog.user_decision
        audit_log.record(verdict, decision, source="clipboard")

        logger.info(
            "Verdict: %s | Risk: %s | Decision: %s",
            verdict.source.value,
            verdict.risk_level.value,
            decision,
        )

        if decision == "blocked":
            self._tray.showMessage(
                "Command Blocked",
                f"SentinelAI blocked a {verdict.risk_level.value} risk command.",
                QSystemTrayIcon.MessageIcon.Warning,
                3000,
            )

        # Reset icon to green (safe/idle) after interaction.
        self._tray.setIcon(_make_tray_icon("#16a34a"))
        self._tray.setToolTip("SentinelAI — Monitoring clipboard")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._tray.showMessage(
                "SentinelAI",
                "Monitoring your clipboard for dangerous commands.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_action.setText("Resume Monitoring")
            self._tray.setIcon(_make_tray_icon("#666666"))
            self._tray.setToolTip("SentinelAI — Paused")
        else:
            self._pause_action.setText("Pause Monitoring")
            self._tray.setIcon(_make_tray_icon("#16a34a"))
            self._tray.setToolTip("SentinelAI — Monitoring clipboard")

    def _quit(self) -> None:
        self._monitor.stop()
        self._monitor.wait(2000)
        self._tray.hide()
        self._app.quit()


def run(llm_model: str = "llama3.1:8b") -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Keep running even with no windows open.

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "SentinelAI", "System tray is not available on this desktop.")
        sys.exit(1)

    _tray_app = TrayApp(app, llm_model=llm_model)
    sys.exit(app.exec())
