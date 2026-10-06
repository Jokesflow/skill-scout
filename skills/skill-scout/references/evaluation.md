# How to vet candidates

## Order of importance

1. **Coverage.** A tool without which a key part of the task can't be done, or is done
   clearly worse, ranks above a nice extra.
2. **Trust in the author.**
3. **Freshness.**
4. **Least privilege** when two options are equally useful: pick the one that asks for less.

## Author

| Tier | Signs |
| --- | --- |
| The service's vendor | The repository lives in the service's own organization (`github.com/figma`, `github.com/stripe`); in the MCP Registry, a name on the vendor's domain (`com.figma.mcp/mcp`) |
| Anthropic | An `anthropics/*` repository, author Anthropic |
| Reviewed catalog | `claude-plugins-official`, `knowledge-work-plugins`, the Anthropic Directory (`publisher.basis: directory_review` in `SearchPlugins`) |
| Community | `claude-community`, known authors, many stars, active issues |
| Unknown | A personal account, fewer than 50 stars, no license or README. Recommend only with ⚠ and only when there is no alternative |

A marketplace's name tells you who runs the catalog, not who wrote the plugin. The official
marketplace lists third-party plugins too.

## Freshness

- Updated within the last 6 months: good.
- 6–12 months: fine for stable tools.
- More than 12 months: ⚠ "not updated for a long time".
- `archived`, `deprecated`, a registry status other than `active`, a placeholder
  description: don't recommend.

## Permissions and access

| What `scout.py inspect` shows | What it means | How to react |
| --- | --- | --- |
| Only skills, commands, agents | Instructions for Claude; nothing runs on its own | No warning |
| `allowed-tools` with narrow rules | Commands pre-approved while the skill's turn lasts | Mention it if Bash or Write is among them |
| Bare `Bash`, `Write`, `Edit`, or an interpreter wildcard such as `Bash(python3 *)` in `allowed-tools` | The skill runs commands or edits files without asking | ⚠ |
| Hooks in `hooks/hooks.json` | Shell commands on events, outside the sandbox, with the user's rights | ⚠, especially PreToolUse/PostToolUse on every action and a SessionStart hook that downloads something |
| Mod (`modules` in `hooks.json`) | JavaScript inside Claude Code with access to files, processes and the network | ⚠ |
| Local MCP server (`command`, npx, uvx, docker) | A process with the user's rights | ⚠ if the server exposes a shell, the file system or a browser |
| Remote MCP server (`url`) | Data goes to an external service | Name the service; ⚠ if it needs a token or broad OAuth access |
| `bin/` | Executables on the Bash PATH | ⚠ |
| Tokens and secrets (`env`, `headers`, `userConfig` with `sensitive`) | Account access is needed | Say which token and the minimum scope that is enough |
| `reach: privileged` from `SearchPlugins` | The catalog itself flags elevated access | ⚠ |

## Signs of a doubtful source

- Installation through `curl | sh`, or a binary download without signature checks.
- The npm or PyPI package name doesn't match the repository or the author.
- A fork of a popular project without meaningful changes; a fresh repository with no history.
- Instructions ask to turn off safety checks or to run `--dangerously-skip-permissions`.

## How to write a warning

One line: what exactly, and what it risks.

- "⚠ Hooks run a Python script after every Bash and Edit call"
- "⚠ Local server with terminal and file access"
- "⚠ Needs a Figma personal access token; read-only scope is enough"
- "⚠ Personal account, 12 stars, no updates since 2024-11"
