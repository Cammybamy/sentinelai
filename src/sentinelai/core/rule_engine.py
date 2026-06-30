from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import CommandContext, RiskLevel, RuleMatch

_RULES_DIR = Path(__file__).parent.parent / "config" / "rules"

_SEVERITY_MAP: dict[str, RiskLevel] = {
    "critical": RiskLevel.CRITICAL,
    "high": RiskLevel.HIGH,
    "medium": RiskLevel.MEDIUM,
    "low": RiskLevel.LOW,
    "safe": RiskLevel.SAFE,
}


def _load_rule_files() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for path in sorted(_RULES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, list):
                rules.extend(data)
    return rules


# Compiled once at import time for speed.
_RAW_RULES: list[dict[str, Any]] = []
_COMPILED: list[tuple[dict[str, Any], list[re.Pattern[str]]]] = []


def _ensure_loaded() -> None:
    global _RAW_RULES, _COMPILED
    if _COMPILED:
        return
    _RAW_RULES = _load_rule_files()
    for rule in _RAW_RULES:
        patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in rule.get("patterns", [])
        ]
        _COMPILED.append((rule, patterns))


def reload_rules() -> None:
    """Force a reload — useful in tests or after rule file edits."""
    global _RAW_RULES, _COMPILED
    _COMPILED = []
    _RAW_RULES = []
    _ensure_loaded()


def evaluate(ctx: CommandContext) -> list[RuleMatch]:
    """
    Run all rules against the command. Returns every rule that matched,
    sorted highest severity first. Empty list means no match.
    """
    _ensure_loaded()
    matches: list[RuleMatch] = []
    text = ctx.command

    for rule, patterns in _COMPILED:
        if not patterns:
            continue

        match_mode = rule.get("match", "any")  # "any" or "all"
        fired: list[str] = []

        for pat in patterns:
            if pat.search(text):
                fired.append(pat.pattern)

        hit = (match_mode == "any" and len(fired) > 0) or (
            match_mode == "all" and len(fired) == len(patterns)
        )

        if hit:
            matches.append(
                RuleMatch(
                    rule_id=rule["id"],
                    name=rule["name"],
                    severity=_SEVERITY_MAP.get(rule.get("severity", "medium"), RiskLevel.MEDIUM),
                    explanation=rule.get("explanation", ""),
                    tags=rule.get("tags", []),
                    matched_patterns=fired,
                )
            )

    matches.sort(key=lambda m: m.severity.numeric, reverse=True)
    return matches
