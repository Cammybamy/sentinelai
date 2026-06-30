from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..core.models import RiskLevel, Verdict

# (header_bg, header_text, badge_bg, badge_text, accent)
_THEME: dict[RiskLevel, tuple[str, str, str, str, str]] = {
    RiskLevel.CRITICAL: ("#1a0000", "#ffffff", "#dc2626", "#ffffff", "#dc2626"),
    RiskLevel.HIGH:     ("#1a0a00", "#ffffff", "#ea580c", "#ffffff", "#ea580c"),
    RiskLevel.MEDIUM:   ("#1a1500", "#ffffff", "#ca8a04", "#ffffff", "#ca8a04"),
    RiskLevel.LOW:      ("#00102a", "#ffffff", "#2563eb", "#ffffff", "#2563eb"),
    RiskLevel.SAFE:     ("#001a07", "#ffffff", "#16a34a", "#ffffff", "#16a34a"),
}

_RISK_LABEL: dict[RiskLevel, str] = {
    RiskLevel.CRITICAL: "CRITICAL RISK",
    RiskLevel.HIGH:     "HIGH RISK",
    RiskLevel.MEDIUM:   "MEDIUM RISK",
    RiskLevel.LOW:      "LOW RISK",
    RiskLevel.SAFE:     "SAFE",
}

_SOURCE_LABEL: dict[str, str] = {
    "rule":     "Detected by rule engine",
    "llm":      "Detected by AI analysis",
    "fallback": "Detected (AI offline — limited analysis)",
}


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #333333;")
    return line


class AlertDialog(QDialog):
    """
    Modal warning dialog shown when a dangerous command is detected.
    Caller reads `.user_decision` after exec() returns:
      "blocked"  — user clicked Block
      "allowed"  — user clicked Allow Anyway
    """

    def __init__(self, verdict: Verdict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verdict = verdict
        self.user_decision: str = "blocked"
        self._build_ui()

    def _build_ui(self) -> None:
        theme = _THEME.get(self.verdict.risk_level, _THEME[RiskLevel.MEDIUM])
        hdr_bg, hdr_fg, badge_bg, badge_fg, accent = theme

        self.setWindowTitle("SentinelAI — Dangerous Command Detected")
        self.setFixedWidth(660)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet("QDialog { background: #111111; border: 1px solid #333333; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background: {hdr_bg};")
        hdr_layout = QVBoxLayout(header)
        hdr_layout.setContentsMargins(20, 18, 20, 18)
        hdr_layout.setSpacing(8)

        top_row = QHBoxLayout()
        app_label = QLabel("🛡  SentinelAI")
        app_label.setStyleSheet(f"color: {hdr_fg}; font-size: 13px; font-weight: 600;")
        top_row.addWidget(app_label)
        top_row.addStretch()

        badge = QLabel(_RISK_LABEL[self.verdict.risk_level])
        badge.setStyleSheet(
            f"background: {badge_bg}; color: {badge_fg}; "
            f"font-size: 11px; font-weight: 700; "
            f"padding: 3px 10px; border-radius: 4px; letter-spacing: 1px;"
        )
        top_row.addWidget(badge)
        hdr_layout.addLayout(top_row)

        title = QLabel("Dangerous command detected in your clipboard")
        title.setStyleSheet(f"color: {hdr_fg}; font-size: 17px; font-weight: 700;")
        title.setWordWrap(True)
        hdr_layout.addWidget(title)

        source_note = QLabel(_SOURCE_LABEL.get(self.verdict.source.value, ""))
        source_note.setStyleSheet("color: #888888; font-size: 11px;")
        hdr_layout.addWidget(source_note)

        root.addWidget(header)
        root.addWidget(_divider())

        # ── Body ─────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: #111111;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(14)

        # Command box
        cmd_label = QLabel("Command")
        cmd_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        body_layout.addWidget(cmd_label)

        cmd_box = QPlainTextEdit()
        cmd_box.setPlainText(self.verdict.command)
        cmd_box.setReadOnly(True)
        cmd_box.setMaximumHeight(90)
        cmd_box.setFont(QFont("Menlo, Consolas, Courier New", 11))
        cmd_box.setStyleSheet(
            f"background: #0a0a0a; color: #f87171; "
            f"border: 1px solid {accent}; border-radius: 4px; padding: 8px;"
        )
        body_layout.addWidget(cmd_box)

        body_layout.addWidget(_divider())

        # Explanation
        why_label = QLabel("Why this is dangerous")
        why_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
        body_layout.addWidget(why_label)

        explanation = QLabel(self.verdict.explanation)
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color: #e5e5e5; font-size: 13px; line-height: 1.5;")
        explanation.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        body_layout.addWidget(explanation)

        # Dangerous elements (if any)
        if self.verdict.dangerous_elements:
            body_layout.addWidget(_divider())
            elem_label = QLabel("Specific threats identified")
            elem_label.setStyleSheet("color: #888888; font-size: 11px; font-weight: 600; letter-spacing: 1px;")
            body_layout.addWidget(elem_label)

            for elem in self.verdict.dangerous_elements[:5]:
                row = QLabel(f"  •  {elem}")
                row.setWordWrap(True)
                row.setStyleSheet(f"color: {accent}; font-size: 12px;")
                body_layout.addWidget(row)

        # Rule IDs (subtle, for technical users)
        if self.verdict.rule_matches:
            ids = "  ".join(m.rule_id for m in self.verdict.rule_matches)
            rule_note = QLabel(f"Rules: {ids}")
            rule_note.setStyleSheet("color: #444444; font-size: 10px; margin-top: 4px;")
            body_layout.addWidget(rule_note)

        root.addWidget(body)
        root.addWidget(_divider())

        # ── Footer / Buttons ─────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: #0a0a0a;")
        btn_layout = QHBoxLayout(footer)
        btn_layout.setContentsMargins(20, 14, 20, 14)
        btn_layout.setSpacing(10)

        advice = QLabel("Blocking clears your clipboard and cancels any pasted command.")
        advice.setStyleSheet("color: #666666; font-size: 11px;")
        advice.setWordWrap(True)
        btn_layout.addWidget(advice, stretch=1)

        allow_btn = QPushButton("Allow Anyway")
        allow_btn.setFixedHeight(36)
        allow_btn.setStyleSheet(
            "QPushButton { background: #1f1f1f; color: #888888; border: 1px solid #333333; "
            "border-radius: 4px; font-size: 13px; padding: 0 16px; }"
            "QPushButton:hover { background: #2a2a2a; color: #cccccc; }"
        )
        allow_btn.clicked.connect(self._on_allow)
        btn_layout.addWidget(allow_btn)

        block_btn = QPushButton("Block & Clear Clipboard")
        block_btn.setFixedHeight(36)
        block_btn.setDefault(True)
        block_btn.setStyleSheet(
            f"QPushButton {{ background: {accent}; color: #ffffff; border: none; "
            f"border-radius: 4px; font-size: 13px; font-weight: 600; padding: 0 20px; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
        )
        block_btn.clicked.connect(self._on_block)
        btn_layout.addWidget(block_btn)

        root.addWidget(footer)

    def _on_block(self) -> None:
        self.user_decision = "blocked"
        self.accept()

    def _on_allow(self) -> None:
        self.user_decision = "allowed"
        self.accept()
