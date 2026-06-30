from __future__ import annotations

import logging

from . import llm_client, rule_engine
from .models import CommandContext, RiskLevel, RuleMatch, Verdict, VerdictSource

logger = logging.getLogger(__name__)

# Commands at or above this severity get blocked immediately from rules alone.
# Commands below this threshold are escalated to the LLM for a second opinion.
_RULE_BLOCK_THRESHOLD = RiskLevel.HIGH

# Minimum LLM confidence required to act on its verdict.
# Below this, we fall back to the rule engine's highest match (or MEDIUM).
_LLM_CONFIDENCE_THRESHOLD = 0.6


def _verdict_from_rules(ctx: CommandContext, matches: list[RuleMatch]) -> Verdict:
    top = matches[0]
    all_explanations = [m.explanation for m in matches]
    dangerous_elements = [
        f"[{m.rule_id}] {m.name}" for m in matches
    ]
    combined_explanation = all_explanations[0]
    if len(matches) > 1:
        others = ", ".join(m.name for m in matches[1:])
        combined_explanation += f" Additional concerns: {others}."

    return Verdict(
        command=ctx.command,
        risk_level=top.severity,
        source=VerdictSource.RULE,
        explanation=combined_explanation,
        dangerous_elements=dangerous_elements,
        rule_matches=matches,
    )


def _fallback_verdict(ctx: CommandContext, matches: list[RuleMatch], skip_llm: bool = False) -> Verdict:
    """Used when LLM is unavailable (or intentionally skipped) and rules had no definitive match."""
    if matches:
        return _verdict_from_rules(ctx, matches)
    if skip_llm:
        # LLM was intentionally bypassed (e.g. shell hook). No rules fired = safe.
        return Verdict(
            command=ctx.command,
            risk_level=RiskLevel.SAFE,
            source=VerdictSource.RULE,
            explanation="No known threat patterns detected.",
        )
    return Verdict(
        command=ctx.command,
        risk_level=RiskLevel.LOW,
        source=VerdictSource.FALLBACK,
        explanation=(
            "This command could not be fully analyzed because the local AI model "
            "is not available. Review it carefully before running."
        ),
    )


def analyze(
    ctx: CommandContext,
    llm_model: str = "llama3.1:8b",
    skip_llm: bool = False,
) -> Verdict:
    """
    Full analysis pipeline:
      1. Run rule engine (always).
      2. If a critical/high rule fires → return rule verdict immediately.
      3. Otherwise escalate to LLM for deeper reasoning.
      4. If LLM unavailable → return best available rule verdict or fallback.
    """
    matches = rule_engine.evaluate(ctx)

    # Fast path: high-confidence rule match.
    if matches and matches[0].severity >= _RULE_BLOCK_THRESHOLD:
        logger.debug("Rule fast-path fired: %s", matches[0].rule_id)
        return _verdict_from_rules(ctx, matches)

    # LLM path for ambiguous or low-severity rule matches.
    if not skip_llm:
        llm_verdict = llm_client.analyze(ctx, model=llm_model)
        if llm_verdict is not None:
            confidence = llm_verdict.llm_confidence or 0.0
            if confidence >= _LLM_CONFIDENCE_THRESHOLD:
                # Attach any rule matches for context in the UI.
                llm_verdict.rule_matches = matches
                # If rules flagged something the LLM rated safe, trust the rules.
                if matches and llm_verdict.risk_level < matches[0].severity:
                    logger.debug(
                        "LLM rated lower than rules (%s vs %s); deferring to rules",
                        llm_verdict.risk_level,
                        matches[0].severity,
                    )
                    return _verdict_from_rules(ctx, matches)
                return llm_verdict
            logger.debug("LLM confidence too low (%.2f); falling back", confidence)

    return _fallback_verdict(ctx, matches, skip_llm=skip_llm)
