# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-06

### Added

- `skill-scout` skill. It triggers at the start of a new task or on "what do I need for…"
  questions, checks what is already installed, searches plugin marketplaces, the official MCP
  Registry and GitHub, vets each candidate's author, freshness and permissions, and returns at
  most five recommendations with install commands. It never installs anything by itself.
- `/scout <task>` command.
- `scout.py` helper with `inventory`, `plugins`, `mcp`, `github` and `inspect` commands.
  Read-only, standard library only, Python 3.8+.
- Reference notes on sources, fallbacks, install commands and the vetting rubric.
- Eval suite for `claude plugin eval` (design, code, research, marketing and a negative case)
  and offline unit tests.
- MIT license.

[0.1.0]: https://github.com/Jokesflow/skill-scout/releases/tag/skill-scout--v0.1.0
