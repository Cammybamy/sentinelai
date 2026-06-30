from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Literal


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        return {"safe": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]

    def __gt__(self, other: RiskLevel) -> bool:
        return self.numeric > other.numeric

    def __ge__(self, other: RiskLevel) -> bool:
        return self.numeric >= other.numeric


class VerdictSource(str, Enum):
    RULE = "rule"
    LLM = "llm"
    FALLBACK = "fallback"  # LLM unavailable, rule had no match


@dataclass
class CommandContext:
    """Raw input to the analysis pipeline."""
    command: str
    shell: Literal["powershell", "cmd", "bash", "zsh", "sh", "unknown"] = "unknown"
    source: Literal["clipboard", "shell_hook", "api"] = "clipboard"


@dataclass
class RuleMatch:
    """A single rule that fired against the command."""
    rule_id: str
    name: str
    severity: RiskLevel
    explanation: str
    tags: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    """Final output of the analysis pipeline."""
    command: str
    risk_level: RiskLevel
    source: VerdictSource
    explanation: str
    dangerous_elements: list[str] = field(default_factory=list)
    rule_matches: list[RuleMatch] = field(default_factory=list)
    llm_confidence: float | None = None

    @property
    def should_block(self) -> bool:
        return self.risk_level >= RiskLevel.HIGH

    @property
    def should_warn(self) -> bool:
        return self.risk_level >= RiskLevel.MEDIUM
