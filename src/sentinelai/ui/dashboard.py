from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
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

# ── Palette ───────────────────────────────────────────────────────────────────
_BG     = "#0d0d0d"   # window / deepest background
_PANEL  = "#161616"   # card / panel surface
_RAISED = "#1c1c1c"   # slightly elevated surface (table rows, hover)
_BORDER = "#242424"   # subtle separator
_TEXT   = "#e8e8e8"   # primary text
_SUB    = "#888888"   # secondary / muted text
_DIM    = "#444444"   # very muted (rules, timestamps)

_ACCENT = "#3b82f6"   # blue — active tab, focus ring

_RISK: dict[str, str] = {
    "critical": "#ef4444",
    "high":     "#f97316",
    "medium":   "#eab308",
    "low":      "#3b82f6",
    "safe":     "#22c55e",
}

# ── Global stylesheet ─────────────────────────────────────────────────────────
_STYLE = f"""
QMainWindow, QWidget {{
    background: {_BG};
    color: {_TEXT};
    font-family: -apple-system, 'SF Pro Text', 'Segoe UI', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: none;
    background: {_BG};
}}
QTabBar {{
    background: {_PANEL};
}}
QTabBar::tab {{
    background: transparent;
    color: {_SUB};
    padding: 11px 22px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QTabBar::tab:selected {{
    color: {_TEXT};
    border-bottom: 2px solid {_ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: #bbbbbb;
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
    padding: 0 12px;
    border-bottom: 1px solid {_BORDER};
}}
QTableWidget::item:selected {{
    background: #1a2d48;
    color: {_TEXT};
}}
QHeaderView::section {{
    background: {_BG};
    color: {_DIM};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {_BORDER};
    text-transform: uppercase;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 5px;
    border: none;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #333333;
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 0; }}
QLineEdit {{
    background: {_PANEL};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}}
QLineEdit:focus {{ border-color: {_ACCENT}; }}
QPushButton {{
    background: {_RAISED};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
}}
QPushButton:hover {{ background: #252525; border-color: #333333; }}
QPushButton:pressed {{ background: #111111; }}
QTextEdit {{
    background: {_PANEL};
    color: {_TEXT};
    border: none;
    font-size: 13px;
    selection-background-color: #1e3a5f;
}}
QSplitter::handle {{ background: {_BORDER}; width: 1px; height: 1px; }}
"""


# ── Component helpers ─────────────────────────────────────────────────────────

def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background: {_BORDER}; border: none;")
    line.setFixedHeight(1)
    return line


def _section_label(title: str) -> QWidget:
    """Inline section heading — label + extending rule, no QGroupBox."""
    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)

    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"color: {_DIM}; font-size: 10px; font-weight: 700; "
        f"letter-spacing: 1.5px;"
    )
    lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    row.addWidget(lbl)

    rule = QFrame()
    rule.setFrameShape(QFrame.Shape.HLine)
    rule.setStyleSheet(f"background: {_BORDER}; border: none;")
    rule.setFixedHeight(1)
    row.addWidget(rule, stretch=1)

    return container


def _stat_card(label: str, color: str = _TEXT) -> tuple[QFrame, QLabel]:
    """Returns (card_widget, number_label) so the caller can update the number."""
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {_PANEL}; border: 1px solid {_BORDER}; "
        f"border-radius: 10px; }}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(6)

    num = QLabel("—")
    num.setStyleSheet(
        f"color: {color}; font-size: 38px; font-weight: 700; "
        f"letter-spacing: -1px; border: none;"
    )
    num.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(num)

    lbl = QLabel(label)
    lbl.setStyleSheet(
        f"color: {_SUB}; font-size: 10px; font-weight: 600; "
        f"letter-spacing: 1.2px; border: none;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)

    return card, num


def _risk_pill(risk: str) -> QLabel:
    color = _RISK.get(risk.lower(), _SUB)
    pill = QLabel(risk.upper())
    pill.setStyleSheet(
        f"background: {color}18; color: {color}; "
        f"border: 1px solid {color}40; border-radius: 4px; "
        f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; "
        f"padding: 2px 8px;"
    )
    pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pill.setFixedWidth(74)
    return pill


# ── Dashboard window ──────────────────────────────────────────────────────────

class DashboardWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SentinelAI")
        self.setMinimumSize(900, 620)
        self.resize(1000, 700)
        self.setStyleSheet(_STYLE)

        self._monitoring_active = True
        self._settings = AppSettings.load()

        # Refs updated on refresh
        self._num_total:   QLabel | None = None
        self._num_blocked: QLabel | None = None
        self._num_allowed: QLabel | None = None
        self._status_dot:  QLabel | None = None
        self._status_text: QLabel | None = None
        self._feed_layout: QVBoxLayout | None = None
        self._audit_table: QTableWidget | None = None
        self._detail_pane: QTextEdit | None = None

        self._build_ui()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(30_000)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._build_monitor_tab(),   "  Monitor  ")
        tabs.addTab(self._build_audit_tab(),     "  Audit Log  ")
        tabs.addTab(self._build_settings_tab(),  "  Settings  ")
        vbox.addWidget(tabs)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setFixedHeight(60)
        header.setStyleSheet(
            f"background: {_PANEL}; border-bottom: 1px solid {_BORDER};"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(28, 0, 28, 0)
        row.setSpacing(0)

        logo_icon = QLabel("🛡")
        logo_icon.setStyleSheet("font-size: 18px; border: none;")
        row.addWidget(logo_icon)

        logo_text = QLabel("  SentinelAI")
        logo_text.setStyleSheet(
            f"color: {_TEXT}; font-size: 15px; font-weight: 700; "
            f"letter-spacing: -0.3px; border: none;"
        )
        row.addWidget(logo_text)

        row.addStretch()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: #22c55e; font-size: 9px; border: none;")
        row.addWidget(self._status_dot)

        self._status_text = QLabel("  Monitoring active")
        self._status_text.setStyleSheet(
            f"color: {_SUB}; font-size: 12px; border: none;"
        )
        row.addWidget(self._status_text)

        return header

    # ── Monitor Tab ───────────────────────────────────────────────────────────

    def _build_monitor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(24)

        # Stat cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        total_card,   self._num_total   = _stat_card("ANALYZED TODAY")
        blocked_card, self._num_blocked = _stat_card("BLOCKED",  "#ef4444")
        allowed_card, self._num_allowed = _stat_card("ALLOWED",  "#22c55e")

        cards_row.addWidget(total_card)
        cards_row.addWidget(blocked_card)
        cards_row.addWidget(allowed_card)
        layout.addLayout(cards_row)

        # Recent detections
        layout.addWidget(_section_label("RECENT DETECTIONS"))

        # Feed container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_PANEL}; border: 1px solid {_BORDER}; "
            f"border-radius: 10px; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {_PANEL}; }}"
        )

        feed_widget = QWidget()
        self._feed_layout = QVBoxLayout(feed_widget)
        self._feed_layout.setContentsMargins(0, 0, 0, 0)
        self._feed_layout.setSpacing(0)
        self._feed_layout.addStretch()

        scroll.setWidget(feed_widget)
        layout.addWidget(scroll, stretch=1)

        return tab

    def _refresh_monitor(self) -> None:
        stats = audit_log.stats_today()
        if self._num_total:   self._num_total.setText(str(stats["total"]))
        if self._num_blocked: self._num_blocked.setText(str(stats["blocked"]))
        if self._num_allowed: self._num_allowed.setText(str(stats["allowed"]))

        if not self._feed_layout:
            return

        # Clear existing rows (leave the trailing stretch)
        while self._feed_layout.count() > 1:
            item = self._feed_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        entries = audit_log.recent(limit=15)
        if not entries:
            empty = QLabel("No detections yet — SentinelAI is watching your clipboard.")
            empty.setStyleSheet(
                f"color: {_SUB}; font-size: 12px; padding: 32px 16px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._feed_layout.insertWidget(0, empty)
            return

        for i, entry in enumerate(entries):
            row = self._make_feed_row(entry)
            self._feed_layout.insertWidget(i, row)

    def _make_feed_row(self, entry: audit_log.AuditEntry) -> QWidget:
        color = _RISK.get(entry.risk_level, _SUB)
        is_blocked = entry.user_decision == "blocked"
        time_str = entry.timestamp[11:16]   # HH:MM

        row = QWidget()
        row.setStyleSheet(
            f"QWidget {{ background: transparent; border-bottom: 1px solid {_BORDER}; }}"
            f"QWidget:hover {{ background: {_RAISED}; }}"
        )
        row.setFixedHeight(50)
        row.setCursor(Qt.CursorShape.PointingHandCursor)

        hl = QHBoxLayout(row)
        hl.setContentsMargins(16, 0, 20, 0)
        hl.setSpacing(12)

        # Left accent stripe
        stripe = QLabel()
        stripe.setFixedSize(3, 22)
        stripe.setStyleSheet(f"background: {color}; border-radius: 2px; border: none;")
        hl.addWidget(stripe)

        # Timestamp
        ts = QLabel(time_str)
        ts.setStyleSheet(
            f"color: {_DIM}; font-size: 11px; "
            f"font-family: 'Menlo', 'Consolas', monospace; border: none;"
        )
        ts.setFixedWidth(38)
        hl.addWidget(ts)

        # Risk pill
        hl.addWidget(_risk_pill(entry.risk_level))

        # Command preview — setMinimumWidth(0) lets Qt shrink this below its
        # text width so the fixed-width decision label always gets its space.
        cmd = QLabel(entry.command[:100].replace("\n", " "))
        cmd.setMinimumWidth(0)
        cmd.setStyleSheet(
            f"color: {_TEXT}; font-size: 12px; "
            f"font-family: 'Menlo', 'Consolas', monospace; border: none;"
        )
        cmd.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        hl.addWidget(cmd, stretch=1)

        # Decision label — fixed width so the layout never squeezes it.
        dec = QLabel("BLOCKED" if is_blocked else "ALLOWED")
        dec.setStyleSheet(
            f"color: {'#ef4444' if is_blocked else '#22c55e'}; "
            f"font-size: 10px; font-weight: 700; letter-spacing: 0.8px; border: none;"
        )
        dec.setFixedWidth(76)
        dec.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hl.addWidget(dec)

        return row

    # ── Audit Log Tab ─────────────────────────────────────────────────────────

    def _build_audit_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._audit_table = QTableWidget()
        self._audit_table.setColumnCount(5)
        self._audit_table.setHorizontalHeaderLabels(
            ["Time", "Risk", "Decision", "Source", "Command"]
        )
        self._audit_table.horizontalHeader().setStretchLastSection(True)
        self._audit_table.setColumnWidth(0, 92)
        self._audit_table.setColumnWidth(1, 90)
        self._audit_table.setColumnWidth(2, 90)
        self._audit_table.setColumnWidth(3, 84)
        self._audit_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._audit_table.setShowGrid(False)
        self._audit_table.verticalHeader().setVisible(False)
        self._audit_table.itemSelectionChanged.connect(self._on_audit_row_selected)
        splitter.addWidget(self._audit_table)

        # Detail pane
        detail_wrap = QWidget()
        detail_wrap.setStyleSheet(
            f"background: {_PANEL}; border-top: 1px solid {_BORDER};"
        )
        dl = QVBoxLayout(detail_wrap)
        dl.setContentsMargins(20, 14, 20, 14)
        dl.setSpacing(8)

        pane_header = QLabel("DETAIL")
        pane_header.setStyleSheet(
            f"color: {_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;"
        )
        dl.addWidget(pane_header)

        self._detail_pane = QTextEdit()
        self._detail_pane.setReadOnly(True)
        self._detail_pane.setFont(QFont("Menlo, Consolas, Courier New", 11))
        self._detail_pane.setStyleSheet(
            f"background: transparent; color: {_SUB}; border: none; "
            f"font-size: 12px;"
        )
        self._detail_pane.setPlaceholderText("Select a row above to view the full analysis.")
        dl.addWidget(self._detail_pane)

        splitter.addWidget(detail_wrap)
        splitter.setSizes([440, 180])

        layout.addWidget(splitter)
        return tab

    def _refresh_audit_log(self) -> None:
        if not self._audit_table:
            return
        entries = audit_log.recent(limit=200)
        self._audit_table.setRowCount(len(entries))
        self._audit_table.setProperty("_entries", entries)

        for i, entry in enumerate(entries):
            color   = _RISK.get(entry.risk_level, _SUB)
            dec_col = "#ef4444" if entry.user_decision == "blocked" else "#22c55e"
            ts      = entry.timestamp[11:19]

            def _cell(text: str, fg: str = _TEXT) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setForeground(QColor(fg))
                return item

            self._audit_table.setItem(i, 0, _cell(ts, _DIM))
            self._audit_table.setItem(i, 1, _cell(entry.risk_level.upper(), color))
            self._audit_table.setItem(i, 2, _cell(entry.user_decision, dec_col))
            self._audit_table.setItem(i, 3, _cell(entry.verdict_source, _SUB))
            self._audit_table.setItem(i, 4, _cell(entry.command[:140].replace("\n", " ")))
            self._audit_table.setRowHeight(i, 38)

    def _on_audit_row_selected(self) -> None:
        if not self._audit_table or not self._detail_pane:
            return
        if not self._audit_table.selectedItems():
            return
        idx = self._audit_table.currentRow()
        entries = self._audit_table.property("_entries")
        if not entries or idx >= len(entries):
            return

        e: audit_log.AuditEntry = entries[idx]
        color = _RISK.get(e.risk_level, _SUB)

        cmd_safe = e.command.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        threats_html = ""
        if e.dangerous_elements:
            items = "".join(
                f'<div style="color:{color}; margin:2px 0;">• {x}</div>'
                for x in e.dangerous_elements
            )
            threats_html = (
                f'<div style="color:{_DIM}; font-size:10px; font-weight:700; '
                f'letter-spacing:1.2px; margin-top:10px; margin-bottom:4px;">THREATS</div>'
                + items
            )

        meta_html = ""
        if e.rule_ids:
            meta_html += (
                f'<div style="color:{_DIM}; font-size:11px; margin-top:8px;">'
                f'Rules: {", ".join(e.rule_ids)}</div>'
            )
        if e.llm_confidence is not None:
            meta_html += (
                f'<div style="color:{_DIM}; font-size:11px;">'
                f'LLM confidence: {e.llm_confidence:.0%}</div>'
            )

        self._detail_pane.setHtml(f"""
        <html><body style="margin:0; padding:0;
            font-family:-apple-system,'SF Pro Text','Segoe UI',sans-serif; color:{_TEXT};">
            <div style="font-family:'Menlo','Consolas',monospace; font-size:11px;
                color:#f87171; background:{_BG}; padding:8px 10px;
                border-radius:5px; margin-bottom:10px; word-break:break-all;">
                {cmd_safe}
            </div>
            <div style="color:{_TEXT}; font-size:12px; line-height:1.55;">
                {e.explanation}
            </div>
            {threats_html}
            {meta_html}
        </body></html>
        """)

    # ── Settings Tab ─────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(10)

        # AI Model
        outer.addWidget(_section_label("AI MODEL"))
        outer.addSpacing(4)

        model_desc = QLabel(
            "Local Ollama model used for deep analysis of unknown commands. "
            "Requires Ollama running at localhost:11434."
        )
        model_desc.setStyleSheet(f"color: {_SUB}; font-size: 12px;")
        model_desc.setWordWrap(True)
        outer.addWidget(model_desc)
        outer.addSpacing(8)

        llm_row = QHBoxLayout()
        llm_row.setSpacing(10)
        self._llm_input = QLineEdit(self._settings.llm_model)
        self._llm_input.setPlaceholderText("e.g. llama3:latest  or  phi3:mini")
        llm_row.addWidget(self._llm_input, stretch=1)

        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(80)
        save_btn.setStyleSheet(
            "QPushButton { background: #1d4ed8; color: #ffffff; border: none; "
            "border-radius: 6px; font-size: 13px; font-weight: 600; padding: 8px 18px; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:pressed { background: #1a3fbf; }"
        )
        save_btn.clicked.connect(self._save_settings)
        llm_row.addWidget(save_btn)
        outer.addLayout(llm_row)

        outer.addSpacing(28)

        # PowerShell hook
        outer.addWidget(_section_label("POWERSHELL SHELL HOOK"))
        outer.addSpacing(4)

        hook_desc = QLabel(
            "Intercepts PowerShell commands before they execute. "
            "Run the command below in an elevated PowerShell window on Windows."
        )
        hook_desc.setStyleSheet(f"color: {_SUB}; font-size: 12px;")
        hook_desc.setWordWrap(True)
        outer.addWidget(hook_desc)
        outer.addSpacing(8)

        hook_row = QHBoxLayout()
        hook_row.setSpacing(10)
        hook_cmd = QLineEdit(r".\shell\install_hook.ps1")
        hook_cmd.setReadOnly(True)
        hook_cmd.setFont(QFont("Menlo, Consolas, Courier New", 12))
        hook_cmd.setStyleSheet(
            f"background: {_BG}; color: #86efac; border: 1px solid {_BORDER}; "
            f"border-radius: 6px; padding: 8px 12px; letter-spacing: 0.3px;"
        )
        hook_row.addWidget(hook_cmd, stretch=1)

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedWidth(70)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(hook_cmd.text()))
        hook_row.addWidget(copy_btn)
        outer.addLayout(hook_row)

        outer.addSpacing(28)

        # About
        outer.addWidget(_section_label("ABOUT"))
        outer.addSpacing(8)

        try:
            rule_engine._ensure_loaded()
            rule_count = len(rule_engine._RAW_RULES)
        except Exception:
            rule_count = "?"

        for text in [
            f"SentinelAI  ·  v{self._settings.version}",
            f"{rule_count} detection rules loaded",
            "All analysis runs locally — nothing is sent externally.",
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {_SUB}; font-size: 12px;")
            outer.addWidget(lbl)
            outer.addSpacing(2)

        outer.addStretch()
        return tab

    def _save_settings(self) -> None:
        self._settings.llm_model = self._llm_input.text().strip() or "llama3:latest"
        self._settings.save()

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._refresh_monitor()
        self._refresh_audit_log()

    def set_monitoring_state(self, active: bool) -> None:
        self._monitoring_active = active
        if self._status_dot and self._status_text:
            if active:
                self._status_dot.setStyleSheet("color: #22c55e; font-size: 9px; border: none;")
                self._status_text.setText("  Monitoring active")
            else:
                self._status_dot.setStyleSheet(f"color: {_DIM}; font-size: 9px; border: none;")
                self._status_text.setText("  Monitoring paused")
