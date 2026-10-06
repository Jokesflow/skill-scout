# Security policy

## What skill-scout touches

- It never installs, enables or connects anything. Installing is always the user's decision.
- Its skill pre-approves only discovery tools for the turn that invokes it: its own script
  (`python3 …/scripts/scout.py`), `claude plugin list`, `claude mcp list`, `WebSearch` and
  `WebFetch` for `registry.modelcontextprotocol.io`, `raw.githubusercontent.com`, `github.com`
  and `claude.com`.
- `scout.py` makes read-only HTTPS requests to `registry.modelcontextprotocol.io`,
  `raw.githubusercontent.com` and `api.github.com`, runs `claude plugin list`,
  `claude plugin marketplace list` and `claude mcp list`, and, when the GitHub API is
  unavailable, a blob-less `git fetch` into a temporary directory that it deletes afterwards.
- If `GH_TOKEN` or `GITHUB_TOKEN` is set, the token is sent only to `api.github.com` and never
  follows a redirect to another host.
- It caches Anthropic's public catalog files for 24 hours in a per-user folder
  (`$XDG_CACHE_HOME/skill-scout`, `%LOCALAPPDATA%\skill-scout` on Windows, otherwise
  `~/.cache/skill-scout`) created with owner-only permissions, and ignores cache files it
  doesn't own. No telemetry.
- Git refs and repository names taken from catalogs are validated before they reach `git`, and
  install commands quote every placeholder, so a pasted command can't turn `<TOKEN>` into a
  shell redirection.

## Reporting a vulnerability

Please report it privately through GitHub's **Security → Report a vulnerability**, not in a
public issue. If private reporting isn't enabled, open an issue that only asks for a contact,
without details. You can expect a first reply within 7 days.

## Scope

In scope: this repository's skills, command and `scout.py`. Third-party plugins and MCP
servers that skill-scout recommends are out of scope; report problems to their authors. Do
tell us if skill-scout missed a risk that `inspect` should have flagged.
