# Safely Onboarding Third-Party Agents

A practical guide for evaluating, scanning, and approving agents from external libraries before they enter your production environment.

---

## Why Agent Onboarding Matters

Third-party agent libraries are like npm packages: convenient but potentially dangerous. When you pull an agent from a shared library, you are granting that agent access to your environment, your files, and potentially your credentials. An agent with overly broad permissions or poor prompt boundaries can:

- **Leak credentials** by reading `.env` files or auth tokens and including them in outputs.
- **Bypass security reviews** by instructing the host agent to skip approval workflows.
- **Execute destructive operations** such as deleting files, overwriting configurations, or corrupting data.
- **Serve as a vector for prompt injection** by embedding instructions that override the host agent's core directives.

You need a formal evaluation process. In a recent production deployment, an audit of 154 third-party agents from an agent library found 2 that required modification before they were safe to use. That is a 1.3% failure rate — low enough to feel safe, high enough to cause real damage if you skip the review.

Do not trust agents by default. Verify them.

---

## Evaluation Flow

Follow these seven steps for every agent before it enters your environment.

### Step 1: Inventory

List all agents in the library. Categorize each one by function: content creation, compliance, analytics, code generation, data transformation, and so on. This gives you a surface-area map and helps prioritize review effort.

### Step 2: Keyword Scan

Run an automated scan of every agent definition file. Look for dangerous patterns — credential access, destructive commands, remote code execution, instruction overrides. This is your first filter and it catches the obvious problems fast.

### Step 3: Risk Classification

Based on scan results, tag each agent as **LOW**, **MEDIUM**, or **HIGH** risk. LOW-risk agents have zero findings. MEDIUM-risk agents have findings that are likely benign but warrant a quick check. HIGH-risk agents have findings that could cause real harm.

### Step 4: Manual Review

Every HIGH-risk agent gets a human review before approval. A qualified reviewer reads the agent definition, understands its intent, and determines whether the flagged patterns are genuinely dangerous or false positives.

### Step 5: Modification

Agents that fail manual review but have valuable functionality get patched. Agents that cannot be patched safely get rejected. No exceptions.

### Step 6: Installation

Approved agents are added to the allowlist. Only agents on the allowlist can run in your environment.

### Step 7: Post-Install Audit

Monitor every newly installed agent for 48 hours. Watch for scope violations, unexpected behavior, and sensitive data exposure. If anything looks wrong, pull the agent immediately.

---

## Keyword Scanning

The following script scans agent definition files for dangerous patterns. It checks for instruction overrides, credential access, destructive commands, remote code execution, encoding tricks, privilege escalation, dynamic execution, security bypass attempts, hardcoded secrets, and audit evasion.

```python
#!/usr/bin/env python3
"""Scan agent definitions for dangerous patterns."""
import re
import sys
from pathlib import Path

DANGEROUS_PATTERNS = [
    (r"ignore.*(?:previous|prior|above).*instructions", "CRITICAL", "Instruction override attempt"),
    (r"(?:read|cat|output).*(?:\.env|credentials|auth.*\.json|secrets)", "HIGH", "Credential file access"),
    (r"(?:rm\s+-rf|del\s+/|format\s+c:)", "CRITICAL", "Destructive command"),
    (r"(?:curl|wget|fetch).*\|.*(?:sh|bash|exec)", "CRITICAL", "Remote code execution"),
    (r"(?:base64|hex).*(?:decode|encode)", "MEDIUM", "Encoding that may hide payloads"),
    (r"(?:sudo|chmod\s+777|chown)", "HIGH", "Privilege escalation"),
    (r"(?:eval|exec)\s*\(", "HIGH", "Dynamic code execution"),
    (r"bypass.*(?:security|review|approval)", "CRITICAL", "Security bypass attempt"),
    (r"(?:api[_-]?key|token|password|secret)\s*[:=]", "HIGH", "Hardcoded credentials"),
    (r"disable.*(?:log|audit|monitor)", "HIGH", "Audit evasion"),
]

def scan_file(filepath: Path) -> list:
    findings = []
    content = filepath.read_text()
    for pattern, severity, description in DANGEROUS_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            line_num = content[:match.start()].count("\n") + 1
            findings.append({
                "file": str(filepath),
                "line": line_num,
                "severity": severity,
                "description": description,
                "match": match.group()[:80],
            })
    return findings

def scan_directory(directory: str) -> list:
    all_findings = []
    for ext in ["*.md", "*.yaml", "*.yml", "*.json", "*.txt"]:
        for f in Path(directory).rglob(ext):
            all_findings.extend(scan_file(f))
    return all_findings

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    findings = scan_directory(target)

    for f in sorted(findings, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}[x["severity"]]):
        print(f"[{f['severity']}] {f['file']}:{f['line']} — {f['description']}")
        print(f"  Matched: {f['match']}")
        print()

    critical = sum(1 for f in findings if f["severity"] == "CRITICAL")
    high = sum(1 for f in findings if f["severity"] == "HIGH")
    print(f"Summary: {critical} CRITICAL, {high} HIGH, {len(findings) - critical - high} MEDIUM")
    if critical > 0:
        print("CRITICAL findings — do NOT install without manual review")
        sys.exit(1)
```

Run it against your agent library directory:

```bash
python3 scan_agents.py ./agents/library/
```

If the script exits with code 1, you have CRITICAL findings. Stop and review before proceeding.

This scanner is a starting point. Extend `DANGEROUS_PATTERNS` as you encounter new attack vectors in your environment. The patterns above are drawn from real findings — every one of them has been seen in the wild.

---

## High-Risk Agent Identification

An agent is classified as HIGH risk when it exhibits any of the following characteristics:

- **File system write access beyond its scope.** An analytics agent that requests write access to `/etc/` or the project root is a red flag.
- **References to credential files or environment variables.** Any agent that mentions `.env`, `credentials.json`, `auth_token`, or similar has no business touching those unless its explicit purpose requires it.
- **Instructions that could override the host agent's SOUL.** Look for phrases like "ignore previous instructions," "you are now," or "disregard your rules." These are prompt injection vectors, whether intentional or not.
- **Dynamic code execution.** Any use of `eval()`, `exec()`, or equivalent constructs means the agent can run arbitrary code at runtime. This is almost never necessary and almost always dangerous.
- **External network calls without clear purpose.** An agent that fetches remote URLs, especially ones that pipe output to a shell, is a potential remote code execution vector.
- **No defined scope limitation.** An agent without explicit boundaries on what it can read, write, and execute is an agent that can do anything. Treat the absence of constraints as a finding.

---

## Agent Modification (Patching)

When an agent fails review but provides valuable functionality, patch it rather than reject it outright. Apply the following modifications:

**Add explicit scope constraints.** Inject boundary instructions into the agent definition:

```yaml
constraints:
  file_access:
    read: ["/workspace/data/reports/"]
    write: ["/workspace/output/"]
  network: false
  shell_commands: false
```

**Remove or neutralize dangerous patterns.** If an agent contains `eval()` calls, replace them with safe alternatives. If it references credential files, remove those references and provide the required data through a secure injection mechanism instead.

**Add security review triggers.** For sensitive operations that cannot be removed entirely, add a requirement for human approval:

```yaml
review_required:
  - file_delete
  - external_api_call
  - configuration_change
```

**Add output sanitization rules.** Ensure the agent cannot leak sensitive information in its outputs:

```yaml
output_sanitization:
  strip_patterns:
    - "(?:api[_-]?key|token|password|secret)\\s*[:=]\\s*\\S+"
    - "(?:\\d{1,3}\\.){3}\\d{1,3}"
```

**Document all modifications.** Every change goes in a CHANGELOG associated with that agent. Record what was changed, why it was changed, who approved the change, and the date. This creates an audit trail and helps future reviewers understand the agent's history.

---

## Post-Installation Audit

After an agent is approved and installed, monitor it for 48 hours before considering it stable. Check the following:

- **Scope compliance.** Does the agent stay within its declared file access paths? Any access outside those paths is a violation.
- **Security review triggers.** Does the agent trigger unexpected security reviews? A sudden spike in review requests may indicate the agent is testing boundaries.
- **File access patterns.** Does the agent attempt to read files outside its declared scope? Even failed attempts are a finding.
- **Output contents.** Does the agent produce outputs containing credentials, internal paths, or other sensitive information? Review a sample of outputs manually.
- **Log and memory anomalies.** Review the agent's log files and any memory or state files it creates. Look for data accumulation that exceeds what the agent needs to function.

If any of these checks fail during the 48-hour window, pull the agent, investigate, and either patch or reject it.

---

## Allowlist Management

Only agents on the allowlist are permitted to run. This is enforced at the configuration level. Here is an example configuration:

```json
{
  "plugins": {
    "allow": [
      "content-writer",
      "compliance-checker",
      "analytics-reporter"
    ]
  }
}
```

Any agent not in the `allow` list is blocked. There is no "allow all" mode in production. When you add a new agent, you add it to this list explicitly after it passes the full evaluation flow.

Review the allowlist quarterly. Remove agents that are no longer in use. Re-scan agents when their upstream definitions change. Treat the allowlist as a living document, not a one-time configuration.

---

## Key Takeaways

A 1.3% failure rate across 154 agents means that skipping the review process is a gamble you will eventually lose. The scanning script catches the obvious problems. Manual review catches the subtle ones. Post-installation monitoring catches the ones that only manifest at runtime.

Build the process once. Run it every time. The cost of reviewing an agent is minutes. The cost of a credential leak or a destructive operation is considerably higher.
