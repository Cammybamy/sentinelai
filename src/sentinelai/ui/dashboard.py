from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config.settings import AppSettings
from ..core import rule_engine
from ..storage import audit_log

_DARK = "#111111"
_PANEL = "#1a1a1a"
_BORDER = "#2a2a2a"
_TEXT = "#e5e5e5"
_MUTED = "#666666"
_RISK_COLORS = {
    "critical": "#dc2626",
    "high":     "#ea580c",
    "medium":   "#ca8a04",
    "low":      "#2563eb",
    "safe":     "#16a34a",
}

_GLOBAL_STYLE = f"""
QMainWindow, QWidget {{
    background: {_DARK};
    color: {_TEXT};
    font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid {_BORDER};
    background: {_PANEL};
}}
QTabBar::tab {{
    background: {_DARK};
    color: {_MUTED};
    padding: 10px 20px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}
QTabBar::tab:selected {{
    color: {_TEXT};
    border-bottom: 2px solid #3b82f6;
    background: {_PANEL};
}}
QTabBar::tab:hover:!selected {{
    color: #aaaaaa;
}}
QTableWidget {{
    background: {_PANEL};
    color: {_TEXT};
    border: none;
    gridline-color: {_BORDER};
    selection-background-color: #1e3a5f;
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {_BORDER};
}}
QHeaderView::section {{
    background: {_DARK};
    color: {_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {_BORDER};
    text-transform: uppercase;
}}
QScrollBar:vertical {{
    background: {_DARK};
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: #333333;
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QLineEdit {{
    background: {_DARK};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 7px 10px;
    font-size: 13px;
}}
QLineEdit:focus {{ border-color: #3b82f6; }}
QPushButton {{
    background: #1f2937;
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 7px 16px;
    font-size: 13px;
}}
QPushButton:hover {{ background: #374151; }}
QPushButton:pressed {{ background: #111827; }}
QGroupBox {{
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-size: 11px;
    font-weight: 600;
    color: {_MUTED};
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}}
QTextEdit {{
    background: {_PANEL};
    color: {_TEXT};
    border: none;
    font-size: 13px;
}}
QSplitter::handle {{ background: {_BORDER}; }}
"""


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {_BORDER};")
    f.setFixedHeight(1)
    return f


def _stat_card(label: str, value: str, color: str = _TEXT) -> QWidget:
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {_PANEL}; border: 1px solid {_BORDER}; border-radius: 8px; }}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(4)

    num = QLabel(value)
    num.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: 700; border: none;")
    num.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(num)

    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; border: none;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)

    return card


def _risk_badge(risk: str) -> QLabel:
    color = _RISK_COLORS.get(risk.lower(), _MUTED)
    badge = QLabel(f"  {risk.upper()}  ")
    badge.setStyleSheet(
        f"background: {color}22; color: {color}; "
        f"border: 1px solid {color}55; border-radius: 3px; "
        f"font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 1px 0;"
    )
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedWidth(80)
    return badge


class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SentinelAI")
        self.setMinimumSize(860, 600)
        self.resize(960, 660)
        self.setStyleSheet(_GLOBAL_STYLE)

        self._monitoring_active = True
        self._settings = AppSettings.load()

        # Refs updated by refresh()
        self._stat_total: QLabel | None = None
        self._stat_blocked: QLabel | None = None
        self._stat_allowed: QLabel | None = None
        self._status_dot: QLabel | None = None
        self._status_text: QLabel | None = None
        self._feed_layout: QVBoxLayout | None = None
        self._audit_table: QTableWidget | None = None
        self._detail_pane: QTextEdit | None = None

        self._build_ui()
        self.refresh()

        # Auto-refresh every 30 seconds in case app is open during active monitoring.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(_divider())

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_monitor_tab(),   "  Monitor  ")
        tabs.addTab(self._build_audit_log_tab(), "  Audit Log  ")
        tabs.addTab(self._build_settings_tab(),  "  Settings  ")
        layout.addWidget(tabs)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setStyleSheet(f"background: {_PANEL}; border-bottom: 1px solid {_BORDER};")
        header.setFixedHeight(58)
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 0, 24, 0)

        logo = QLabel("🛡  SentinelAI")
        logo.setStyleSheet("font-size: 16px; font-weight: 700; letter-spacing: 0.5px;")
        row.addWidget(logo)

        row.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #16a34a; font-size: 11px;")
        row.addWidget(self._status_dot)

        self._status_text = QLabel("Monitoring active")
        self._status_text.setStyleSheet(f"color: {_MUTED}; font-size: 12px; margin-left: 6px;")
        row.addWidget(self._status_text)

        return header

    # ── Monitor Tab ──────────────────────────────────────────────────────────

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Stat cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        total_card = _stat_card("ANALYZED TODAY", "—")
        blocked_card = _stat_card("BLOCKED", "—", "#dc2626")
        allowed_card = _stat_card("ALLOWED", "—", "#16a34a")

        # Store refs for refresh()
        self._stat_total   = total_card.findChild(QLabel)
        self._stat_blocked = blocked_card.findChild(QLabel)
        self._stat_allowed = allowed_card.findChild(QLabel)

        # findChild returns first match (the number label) — works for our layout
        cards_row.addWidget(total_card)
        cards_row.addWidget(blocked_card)
        cards_row.addWidget(allowed_card)
        layout.addLayout(cards_row)

        # Recent detections
        feed_group = QGroupBox("RECENT DETECTIONS")
        feed_outer = QVBoxLayout(feed_group)
        feed_outer.setContentsMargins(0, 8, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        feed_widget = QWidget()
        feed_widget.setStyleSheet(f"background: {_PANEL};")
        self._feed_layout = QVBoxLayout(feed_widget)
        self._feed_layout.setContentsMargins(12, 8, 12, 8)
        self._feed_layout.setSpacing(1)
        self._feed_layout.addStretch()

        scroll.setWidget(feed_widget)
        feed_outer.addWidget(scroll)
        layout.addWidget(feed_group, stretch=1)

        return tab

    def _refresh_monitor(self) -> None:
        stats = audit_log.stats_today()

        # Update stat numbers (findChild gets the first QLabel = the number)
        if self._stat_total:
            self._stat_total.setText(str(stats["total"]))
        if self._stat_blocked:
            self._stat_blocked.setText(str(stats["blocked"]))
        if self._stat_allowed:
            self._stat_allowed.setText(str(stats["allowed"]))

        # Rebuild feed
        if not self._feed_layout:
            return
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        entries = audit_log.recent(limit=12)
        if not entries:
            empty = QLabel("No detections yet — SentinelAI is watching.")
            empty.setStyleSheet(f"color: {_MUTED}; font-size: 12px; padding: 16px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._feed_layout.insertWidget(0, empty)
            return

        for entry in entries:
            row_widget = self._make_feed_row(entry)
            self._feed_layout.insertWidget(self._feed_layout.count() - 1, row_widget)

    def _make_feed_row(self, entry: audit_log.AuditEntry) -> QWidget:
        color = _RISK_COLORS.get(entry.risk_level, _MUTED)
        icon = "⛔" if entry.user_decision == "blocked" else "⚠️"
        time_str = entry.timestamp[11:19]  # HH:MM:SS from ISO string

        row = QFrame()
        row.setStyleSheet(
            f"QFrame {{ background: {_DARK}; border-left: 3px solid {color}; "
            f"border-radius: 0; margin: 1px 0; }}"
            f"QFrame:hover {{ background: #181818; }}"
        )
        row.setFixedHeight(44)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(12, 0, 12, 0)
        row_layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(20)
        row_layout.addWidget(icon_lbl)

        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet(f"color: {_MUTED}; font-size: 11px; font-family: 'Menlo', 'Consolas', monospace;")
        time_lbl.setFixedWidth(70)
        row_layout.addWidget(time_lbl)

        risk_lbl = QLabel(entry.risk_level.upper())
        risk_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")
        risk_lbl.setFixedWidth(70)
        row_layout.addWidget(risk_lbl)

        cmd_lbl = QLabel(entry.command[:80].replace("\n", " "))
        cmd_lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 12px; font-family: 'Menlo', 'Consolas', monospace;"
        )
        cmd_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row_layout.addWidget(cmd_lbl, stretch=1)

        decision_lbl = QLabel(entry.user_decision)
        decision_lbl.setStyleSheet(
            f"color: {'#dc2626' if entry.user_decision == 'blocked' else '#16a34a'}; "
            f"font-size: 11px; font-weight: 600;"
        )
        decision_lbl.setFixedWidth(60)
        row_layout.addWidget(decision_lbl)

        return row

    # ── Audit Log Tab ─────────────────────────────────────────────────────────

    def _build_audit_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._audit_table = QTableWidget()
        self._audit_table.setColumnCount(5)
        self._audit_table.setHorizontalHeaderLabels(["Time", "Risk", "Decision", "Source", "Command"])
        self._audit_table.horizontalHeader().setStretchLastSection(True)
        self._audit_table.setColumnWidth(0, 90)
        self._audit_table.setColumnWidth(1, 90)
        self._audit_table.setColumnWidth(2, 80)
        self._audit_table.setColumnWidth(3, 80)
        self._audit_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._audit_table.setShowGrid(False)
        self._audit_table.verticalHeader().setVisible(False)
        self._audit_table.setAlternatingRowColors(False)
        self._audit_table.itemSelectionChanged.connect(self._on_audit_row_selected)
        splitter.addWidget(self._audit_table)

        # Detail pane
        detail_frame = QWidget()
        detail_frame.setStyleSheet(f"background: {_PANEL}; border-top: 1px solid {_BORDER};")
        detail_layout = QVBoxLayout(detail_frame)
        detail_layout.setContentsMargins(16, 12, 16, 12)

        detail_header = QLabel("Select a row to see the full analysis")
        detail_header.setStyleSheet(f"color: {_MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        detail_layout.addWidget(detail_header)

        self._detail_pane = QTextEdit()
        self._detail_pane.setReadOnly(True)
        self._detail_pane.setPlaceholderText("")
        self._detail_pane.setMaximumHeight(140)
        detail_layout.addWidget(self._detail_pane)

        splitter.addWidget(detail_frame)
        splitter.setSizes([420, 160])

        layout.addWidget(splitter)
        return tab

    def _refresh_audit_log(self) -> None:
        if not self._audit_table:
            return
        entries = audit_log.recent(limit=200)
        self._audit_table.setRowCount(len(entries))
        self._audit_table.setProperty("_entries", entries)

        for row_idx, entry in enumerate(entries):
            color = _RISK_COLORS.get(entry.risk_level, _MUTED)
            time_str = entry.timestamp[11:19]
            decision_color = "#dc2626" if entry.user_decision == "blocked" else "#16a34a"

            def cell(text: str, fg: str = _TEXT) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setForeground(QColor(fg))
                return item

            self._audit_table.setItem(row_idx, 0, cell(time_str, _MUTED))
            self._audit_table.setItem(row_idx, 1, cell(entry.risk_level.upper(), color))
            self._audit_table.setItem(row_idx, 2, cell(entry.user_decision, decision_color))
            self._audit_table.setItem(row_idx, 3, cell(entry.verdict_source))
            self._audit_table.setItem(row_idx, 4, cell(entry.command[:120].replace("\n", " ")))
            self._audit_table.setRowHeight(row_idx, 36)

    def _on_audit_row_selected(self) -> None:
        if not self._audit_table or not self._detail_pane:
            return
        rows = self._audit_table.selectedItems()
        if not rows:
            return
        row_idx = self._audit_table.currentRow()
        entries = self._audit_table.property("_entries")
        if not entries or row_idx >= len(entries):
            return
        entry: audit_log.AuditEntry = entries[row_idx]

        lines = [
            f"Command:  {entry.command}",
            f"",
            f"Explanation:  {entry.explanation}",
        ]
        if entry.dangerous_elements:
            lines.append("")
            lines.append("Threats identified:")
            for elem in entry.dangerous_elements:
                lines.append(f"  •  {elem}")
        if entry.rule_ids:
            lines.append("")
            lines.append(f"Rules:  {', '.join(entry.rule_ids)}")
        if entry.llm_confidence is not None:
            lines.append(f"LLM confidence:  {entry.llm_confidence:.0%}")

        self._detail_pane.setPlainText("\n".join(lines))

    # ── Settings Tab ─────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(20)

        # LLM model
        llm_group = QGroupBox("AI MODEL")
        llm_layout = QVBoxLayout(llm_group)
        llm_layout.setContentsMargins(16, 16, 16, 16)
        llm_layout.setSpacing(8)

        llm_desc = QLabel(
            "Local Ollama model used for deep analysis of unknown commands.\n"
            "Requires Ollama running at localhost:11434."
        )
        llm_desc.setStyleSheet(f"color: {_MUTED}; font-size: 12px; border: none;")
        llm_desc.setWordWrap(True)
        llm_layout.addWidget(llm_desc)

        llm_row = QHBoxLayout()
        self._llm_input = QLineEdit(self._settings.llm_model)
        self._llm_input.setPlaceholderText("e.g. llama3.1:8b  or  phi3:mini")
        llm_row.addWidget(self._llm_input, stretch=1)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(80)
        save_btn.setStyleSheet(
            "QPushButton { background: #1d4ed8; color: white; border: none; border-radius: 4px; font-weight: 600; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        save_btn.clicked.connect(self._save_settings)
        llm_row.addWidget(save_btn)
        llm_layout.addLayout(llm_row)
        outer.addWidget(llm_group)

        # PS Hook
        hook_group = QGroupBox("POWERSHELL SHELL HOOK")
        hook_layout = QVBoxLayout(hook_group)
        hook_layout.setContentsMargins(16, 16, 16, 16)
        hook_layout.setSpacing(8)

        hook_desc = QLabel(
            "Installs a PowerShell module that intercepts commands before they run.\n"
            "Run the command below in an elevated PowerShell window on Windows."
        )
        hook_desc.setStyleSheet(f"color: {_MUTED}; font-size: 12px; border: none;")
        hook_desc.setWordWrap(True)
        hook_layout.addWidget(hook_desc)

        hook_cmd = QLineEdit(r".\shell\install_hook.ps1")
        hook_cmd.setReadOnly(True)
        hook_cmd.setFont(QFont("Menlo, Consolas, Courier New", 12))
        hook_cmd.setStyleSheet(
            f"background: {_DARK}; color: #86efac; border: 1px solid {_BORDER}; "
            f"border-radius: 4px; padding: 8px 10px;"
        )
        hook_layout.addWidget(hook_cmd)

        copy_btn = QPushButton("Copy Command")
        copy_btn.setFixedWidth(140)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(hook_cmd.text()))
        hook_layout.addWidget(copy_btn)
        outer.addWidget(hook_group)

        # About
        about_group = QGroupBox("ABOUT")
        about_layout = QVBoxLayout(about_group)
        about_layout.setContentsMargins(16, 16, 16, 16)
        about_layout.setSpacing(6)

        try:
            rule_engine._ensure_loaded()
            rule_count = len(rule_engine._RAW_RULES)
        except Exception:
            rule_count = "?"

        about_lines = [
            f"SentinelAI  v{self._settings.version}",
            f"{rule_count} detection rules loaded",
            "Privacy-first — all analysis runs locally, nothing is sent externally.",
        ]
        for line in about_lines:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {_MUTED}; font-size: 12px; border: none;")
            about_layout.addWidget(lbl)

        outer.addWidget(about_group)
        outer.addStretch()
        return tab

    def _save_settings(self) -> None:
        self._settings.llm_model = self._llm_input.text().strip() or "llama3.1:8b"
        self._settings.save()

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload all data from SQLite and update every visible tab."""
        self._refresh_monitor()
        self._refresh_audit_log()

    def set_monitoring_state(self, active: bool) -> None:
        self._monitoring_active = active
        if self._status_dot and self._status_text:
            if active:
                self._status_dot.setStyleSheet("color: #16a34a; font-size: 11px;")
                self._status_text.setText("Monitoring active")
            else:
                self._status_dot.setStyleSheet(f"color: {_MUTED}; font-size: 11px;")
                self._status_text.setText("Monitoring paused")
