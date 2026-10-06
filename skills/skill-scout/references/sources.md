# Sources, fallbacks and install commands

## What is already installed

| What | Where to look |
| --- | --- |
| Skills | The skill list in your context; `ListSkills`; `~/.claude/skills/*/SKILL.md` and `.claude/skills/*/SKILL.md` |
| Plugins | `claude plugin list --json`; `ListPlugins`; the Installed tab of `/plugin` |
| MCP servers | `mcp__<server>__*` tools in your context; `claude mcp list`; `ListConnectors` |

Connectors added on claude.ai are available in Claude Code automatically when the user is
signed in with the same claude.ai account. In `/mcp` they show up as `claude.ai <Name>`.

## Plugins

- **Marketplaces the user has added:** `claude plugin list --available --json` — fields
  `pluginId`, `description`, `version`, `source`, sometimes `installCount`.
  `claude plugin marketplace list --json` adds each marketplace's `repo` and local clone
  (`installLocation`).
- **Anthropic's catalogs**, even when they aren't added. The catalog file is
  `https://raw.githubusercontent.com/<repo>/HEAD/.claude-plugin/marketplace.json`.

  | Marketplace | Repository | Contents |
  | --- | --- | --- |
  | `claude-plugins-official` | `anthropics/claude-plugins-official` | Plugins by Anthropic and partners. Added automatically in an interactive terminal session |
  | `claude-community` | `anthropics/claude-plugins-community` | Third-party plugins submitted by their authors |
  | `anthropic-agent-skills` | `anthropics/skills` | `document-skills` (docx, xlsx, pptx, pdf), `example-skills` |
  | `knowledge-work-plugins` | `anthropics/knowledge-work-plugins` | marketing, design, data, sales, legal, finance and more |

- **Web catalog:** https://claude.com/marketplace/plugins
- **claude.ai and Cowork:** `SearchPlugins` searches the account's and organization's catalog
  and returns `author`, `publisher.tier`, `components` and `reach`.

## MCP servers

- **Official registry:**
  `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=<name>&version=latest&limit=50`.
  It matches a substring of the server name, not the description. One server:
  `GET /v0.1/servers/<urlencoded name>/versions/latest`.
- **The name shows the publisher:** `io.github.<login>/…` was published by the GitHub account
  `<login>`; `com.<vendor>.…/…` by the owner of the domain `<vendor>.com`, proven through DNS
  or HTTP. A subdomain of a shared host (`*.vercel.app`, `*.github.io`…) proves nothing about a
  vendor.
- **claude.ai connectors:** `SearchMcpRegistry` returns `installState`, `connected` and the
  tool list. Users connect them in Settings → Connectors.
- Many MCP servers ship inside plugins (figma, notion, linear, sentry…), so search the plugins
  too.

## Skills

- `SearchSkills` on claude.ai.
- `anthropics/skills`: `/plugin marketplace add anthropics/skills`, then
  `/plugin install document-skills@anthropic-agent-skills`.
- GitHub: `scout.py github <kw> --kind skill`, or WebSearch `site:github.com SKILL.md <kw>`.

## GitHub

- Search: `GET https://api.github.com/search/repositories?q=<kw> fork:false archived:false&sort=stars`.
  Without a token: 10 searches a minute; `GH_TOKEN` or `GITHUB_TOKEN` raises the limit.
- Repository: `GET /repos/<owner>/<repo>` (`stargazers_count`, `pushed_at`, `license`,
  `archived`, `owner.type`). Last change to a folder:
  `GET /repos/<owner>/<repo>/commits?path=<dir>&per_page=1`.
- Files without the API: `https://raw.githubusercontent.com/<owner>/<repo>/<ref or HEAD>/<path>`.
  `scout.py inspect` also falls back to a blob-less `git fetch` to list files.

## When a source is unavailable

- **The MCP Registry doesn't answer:** `SearchMcpRegistry`, plugins that bundle an MCP server,
  GitHub, WebSearch `"<product> MCP server"`. Say in the answer that the registry couldn't be
  checked.
- **GitHub rate limit:** WebSearch `site:github.com …`, WebFetch the repository page. Check
  permissions through `.claude-plugin/plugin.json`, `hooks/hooks.json` and `.mcp.json` on
  raw.githubusercontent.com.
- **No python or shell:** WebFetch the addresses above.
- **Nothing found:** the "Not found" section, no guesses.

## Install commands

| What | Command |
| --- | --- |
| Plugin from an added marketplace | `/plugin install <name>@<marketplace>`; in a shell `claude plugin install <name>@<marketplace>` (`--scope user` by default, `project`, `local`), then `/reload-plugins` |
| Marketplace | `/plugin marketplace add <owner/repo>` or `claude plugin marketplace add <owner/repo>` |
| Remote MCP server | `claude mcp add --transport http <name> <url>`; with a token add `--header "Authorization: Bearer <token>"`; for OAuth sign in with `/mcp` or `claude mcp login <name>` |
| Local MCP server from npm | `claude mcp add <name> -e KEY=<value> -- npx -y <package>@<version>` |
| Local MCP server from PyPI | `claude mcp add <name> -- uvx <package>@<version>` |
| Local MCP server in Docker | `claude mcp add <name> -- docker run -i --rm <image>` |

MCP scopes: `local` by default (this project, only you), `user` (all your projects),
`project` (a `.mcp.json` file in the repository, for the whole team).
