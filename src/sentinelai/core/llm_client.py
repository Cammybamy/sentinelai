from __future__ import annotations

import json
import logging
from typing import Any

from .models import CommandContext, RiskLevel, Verdict, VerdictSource

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a terminal command security analyst. Your job is to evaluate whether a
shell command is dangerous and explain your reasoning in plain English that a
non-technical user can understand.

Focus on these threat categories:
- Remote code execution (downloading and running scripts)
- Credential theft (accessing password files, SSH keys)
- Persistence mechanisms (startup entries, cron jobs, registry keys)
- Defense evasion (disabling security tools, obfuscation)
- Data exfiltration (sending files to remote servers)
- Destructive actions (deleting system files)
- Privilege escalation (gaining elevated access)
- Reverse shells (giving remote control to an attacker)

Respond ONLY with valid JSON matching this schema:
{
  "risk_level": "safe" | "low" | "medium" | "high" | "critical",
  "confidence": 0.0–1.0,
  "verdict": "allow" | "warn" | "block",
  "explanation": "<plain English, 1-3 sentences, assume zero technical knowledge>",
  "dangerous_elements": ["<specific part of command>", ...]
}

If the command is clearly benign (ls, cd, echo, git status, etc.), return risk_level "safe".
Do not return markdown, code fences, or any text outside the JSON object.
"""

_RISK_MAP: dict[str, RiskLevel] = {
    "safe": RiskLevel.SAFE,
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
    "critical": RiskLevel.CRITICAL,
}


def _parse_response(raw: str, ctx: CommandContext) -> Verdict:
    data: dict[str, Any] = json.loads(raw)
    risk_level = _RISK_MAP.get(data.get("risk_level", "medium"), RiskLevel.MEDIUM)
    return Verdict(
        command=ctx.command,
        risk_level=risk_level,
        source=VerdictSource.LLM,
        explanation=data.get("explanation", "No explanation provided."),
        dangerous_elements=data.get("dangerous_elements", []),
        llm_confidence=float(data.get("confidence", 0.5)),
    )


def analyze(ctx: CommandContext, model: str = "llama3.1:8b") -> Verdict | None:
    """
    Send the command to a local Ollama model for analysis.
    Returns None if Ollama is unavailable or returns unparseable output.
    """
    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not installed — LLM analysis unavailable")
        return None

    user_message = (
        f"Shell type: {ctx.shell}\n"
        f"Source: {ctx.source}\n\n"
        f"Command to analyze:\n```\n{ctx.command}\n```"
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            format="json",
            options={"temperature": 0.1},
        )
        raw = response["message"]["content"]
        return _parse_response(raw, ctx)

    except Exception as exc:
        logger.warning("LLM analysis failed: %s", exc)
        return None
