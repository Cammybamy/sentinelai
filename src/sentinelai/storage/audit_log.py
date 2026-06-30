from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from ..core.models import Verdict
from .db import get_connection

UserDecision = Literal["blocked", "allowed", "auto_blocked"]


@dataclass
class AuditEntry:
    id: int
    timestamp: str
    command: str
    risk_level: str
    verdict_source: str
    explanation: str
    dangerous_elements: list[str]
    rule_ids: list[str]
    llm_confidence: float | None
    user_decision: str
    shell: str
    source: str


def record(verdict: Verdict, decision: UserDecision, shell: str = "unknown", source: str = "clipboard") -> int:
    """Write a verdict + user decision to the audit log. Returns the new row id."""
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log
                (timestamp, command, risk_level, verdict_source, explanation,
                 dangerous_elements, rule_ids, llm_confidence, user_decision, shell, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                verdict.command,
                verdict.risk_level.value,
                verdict.source.value,
                verdict.explanation,
                json.dumps(verdict.dangerous_elements),
                json.dumps([m.rule_id for m in verdict.rule_matches]),
                verdict.llm_confidence,
                decision,
                shell,
                source,
            ),
        )
    return cur.lastrowid


def stats_today() -> dict[str, int]:
    """Return analyzed/blocked/allowed counts for today (UTC)."""
    conn = get_connection()
    today = datetime.now(timezone.utc).date().isoformat()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN user_decision = 'blocked' THEN 1 ELSE 0 END) AS blocked,
            SUM(CASE WHEN user_decision = 'allowed' THEN 1 ELSE 0 END) AS allowed
        FROM audit_log
        WHERE timestamp LIKE ?
        """,
        (f"{today}%",),
    ).fetchone()
    return {
        "total":   row["total"]   or 0,
        "blocked": row["blocked"] or 0,
        "allowed": row["allowed"] or 0,
    }


def recent(limit: int = 100) -> list[AuditEntry]:
    """Return the most recent audit entries, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        AuditEntry(
            id=r["id"],
            timestamp=r["timestamp"],
            command=r["command"],
            risk_level=r["risk_level"],
            verdict_source=r["verdict_source"],
            explanation=r["explanation"],
            dangerous_elements=json.loads(r["dangerous_elements"]),
            rule_ids=json.loads(r["rule_ids"]),
            llm_confidence=r["llm_confidence"],
            user_decision=r["user_decision"],
            shell=r["shell"],
            source=r["source"],
        )
        for r in rows
    ]
