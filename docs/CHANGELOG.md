# Changelog — GridWatch AU

All notable changes are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Repo scaffolding & process machinery (PR #1), on branch `scaffold`.

### Added
- **Project skeleton** — `pyproject.toml` (requests, matplotlib; dev: pytest, ruff,
  pre-commit), `src/gridwatch/` package tree (contracts · ports · domain · adapters ·
  application · viz · cli), `README.md`, `CLAUDE.md` (project memory / method).
- **Spec layer** — PRD (`docs/prd/`), system architecture
  (`docs/architecture/system-architecture.md`), and ADR-001..005 (ports & adapters,
  data source, reading spine, file persistence, NEM-only scope).
- **Build plan** — `docs/build/build-plan.md` (tracks + critical path 0→1→2→3→5) and
  `docs/build/MERGE-PROTOCOL.md` (reviewed-PR-into-main rule).
- **Enforcement** — `tools/check_decision_hygiene.py` commit guard (changelog/ADR
  discipline), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`,
  `.claude/settings.json` PreToolUse hook.
- **Test fixture** — `tests/fixtures/nem_sa1_power_7d.json`, a captured real
  OpenElectricity v4 response, so the suite runs offline.
