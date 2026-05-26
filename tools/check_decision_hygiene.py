#!/usr/bin/env python3
"""Decision-hygiene guard — keeps the method honest at the commit boundary.

Rules:
  * BLOCK if substantive source changed but docs/CHANGELOG.md was not updated.
  * WARN if the contract spine (src/gridwatch/contracts/ or ports/) changed with no
    ADR staged (a real design change should be recorded — see docs/.../decisions/).

Modes:
  (default)        git pre-commit / CLI — inspects STAGED files; exit 1 to block.
  --against REF    CI — inspects files changed since REF (e.g. a PR base sha).
  --selftest       no git; verifies the rule logic.
"""

import subprocess
import sys

SRC_PREFIX = "src/gridwatch/"
SPINE_PREFIXES = ("src/gridwatch/contracts/", "src/gridwatch/ports/")
ADR_DIR = "docs/architecture/decisions/"
CHANGELOG = "docs/CHANGELOG.md"


def evaluate(files):
    """Pure: files -> (ok, errors, warnings)."""
    errs, warns = [], []
    code = [
        f
        for f in files
        if f.startswith(SRC_PREFIX)
        and f.endswith(".py")
        and "/tests/" not in f
        and not f.endswith("__init__.py")
    ]
    spine = [f for f in files if f.startswith(SPINE_PREFIXES)]
    adr = [f for f in files if f.startswith(ADR_DIR) and f.endswith(".md")]
    changelog = CHANGELOG in files
    if code and not changelog:
        errs.append(
            f"source changed ({len(code)} file(s)) but {CHANGELOG} is not "
            f"updated — add an Unreleased changelog entry."
        )
    if spine and not adr:
        warns.append(
            "contract spine changed (contracts/ or ports/) with no ADR — "
            "if this is a design decision, record one."
        )
    return (not errs, errs, warns)


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.splitlines()


def _report(files):
    ok, errs, warns = evaluate([f.strip() for f in files if f.strip()])
    for w in warns:
        print(f"⚠ decision-hygiene: {w}", file=sys.stderr)
    for e in errs:
        print(f"✗ decision-hygiene: {e}", file=sys.stderr)
    return ok


def main():
    a = sys.argv[1:]
    if "--selftest" in a:
        ok, e, _ = evaluate(["src/gridwatch/contracts/readings.py"])
        assert not ok and any("CHANGELOG" in x for x in e)
        ok2, _, _ = evaluate(["src/gridwatch/contracts/readings.py", "docs/CHANGELOG.md"])
        assert ok2
        _, _, w3 = evaluate(["src/gridwatch/contracts/readings.py", "docs/CHANGELOG.md"])
        assert any("ADR" in x for x in w3)
        ok4, _, _ = evaluate(["README.md"])
        assert ok4
        print("selftest ok")
        sys.exit(0)
    if "--against" in a:
        ref = a[a.index("--against") + 1]
        sys.exit(0 if _report(_git("diff", "--name-only", f"{ref}...HEAD")) else 1)
    # default: git pre-commit / CLI
    sys.exit(0 if _report(_git("diff", "--cached", "--name-only")) else 1)


if __name__ == "__main__":
    main()
