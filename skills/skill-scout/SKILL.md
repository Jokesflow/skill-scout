---
name: skill-scout
description: >-
  Finds the skills, plugins and MCP servers a task needs: checks what is already installed,
  searches plugin marketplaces, the official MCP Registry and GitHub, vets each candidate's
  author, freshness and requested permissions, and returns at most 5 recommendations with
  install commands. Use when the user starts a new task (design, coding, research, marketing,
  data, documents, automation) or asks "what do I need for…", "which skills, plugins or MCP
  servers fit…", "is there a plugin or MCP server for…", «что мне нужно для…», «какие скиллы /
  плагины / MCP подойдут». Not for small edits, quick questions or a task already under way.
  Never installs anything by itself.
user-invocable: false
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/scout.py *) Bash(claude plugin list *) Bash(claude mcp list) WebFetch(domain:registry.modelcontextprotocol.io) WebFetch(domain:raw.githubusercontent.com) WebFetch(domain:github.com) WebFetch(domain:claude.com) WebSearch
---

# Skill Scout

You find the skills, plugins and MCP servers that the user's task is missing. You only search,
vet and recommend. Never install, enable or connect anything until the user has explicitly
chosen what to install.

Task, if it was passed as an argument: $ARGUMENTS
Without an argument, take the task from the user's latest message.

## Mode

- **Full.** The user asked for this: `/scout`, "what do I need for…", "which plugins fit…".
  Do every step.
- **Quick.** You invoked the skill yourself at the start of a new task. Do steps 1 and 2 and
  at most three searches for the main needs, without GitHub. If nothing is worth installing,
  answer in one line ("What you have is enough for this task: …" or "No extra tools needed")
  and carry on with the task. If you found something that clearly changes the result, show a
  short report and ask whether to install it before you start the work.
- Scout once per task. Don't repeat it at every step.

## Step 1. Break down the task

Work out the type (design, code, research, marketing, data, documents, automation), the stack
and external services (Figma, GitHub, Notion, Postgres, Google Drive…) and the end result (a
file and its format, a site, code or a PR, a report, a dashboard).

Turn that into 2–5 needs, such as "read the mockup from Figma" or "build a .pptx". Give each
need 1–3 English keywords: the product name first, then the action (`figma`, `postgres`,
`pptx`, `scraping`). If the task is too vague to scout for, ask one clarifying question
instead of searching.

## Step 2. Check what is already there

1. Your own context: the list of available skills with their descriptions, and the tools of
   connected MCP servers (`mcp__<server>__*`, including deferred ones you see only by name).
2. If the environment has `ListSkills`, `ListPlugins` or `ListConnectors` (claude.ai, Cowork;
   load deferred ones through ToolSearch), call them with your keywords.
3. In Claude Code with a shell: `python3 ${CLAUDE_SKILL_DIR}/scripts/scout.py inventory`
   (installed plugins, `claude mcp list`, skills in `~/.claude/skills` and `.claude/skills`).
   If there is no `python3`, try `python` or `py -3`; without a shell, stick to items 1–2.

The script is pre-approved only in the exact form
`python3 ${CLAUDE_SKILL_DIR}/scripts/scout.py <command> …`. Run every script command as its
own Bash call, without `cd`, variables, `;`, `&&`, `|` or redirects, or the user will have to
approve each run. Make independent calls in parallel. If a run is still denied or waits for
approval, don't retry it: take the fallback paths and say in one line that the check was
incomplete.

Built-in abilities count as "already available": reading and editing files, Bash, web
search, WebFetch, writing code. Don't look for a plugin for something Claude does itself. A
need that something installed already covers doesn't go to the search.

## Step 3. Find what is missing

Search only for needs that are still open; 2–4 queries are usually enough:

| Looking for | Main source | Also |
| --- | --- | --- |
| Plugins, including skill bundles | `scout.py plugins <kw>…` | `SearchPlugins`, if present |
| MCP servers | `scout.py mcp <kw>…` | `SearchMcpRegistry` (claude.ai connectors), if present |
| Standalone skills | `SearchSkills`, if present; the plugins above | `scout.py github <kw> --kind skill` |
| Anything else | `scout.py github <kw> --kind mcp\|plugin\|skill` | WebSearch `site:github.com` |

`scout.py plugins` searches the marketplaces the user has added and Anthropic's catalogs
(`claude-plugins-official`, `claude-community`, `anthropic-agent-skills`,
`knowledge-work-plugins`), even ones that aren't added. `scout.py mcp` searches the official
MCP Registry, which matches server names only, so use product names as keywords.

If the script or a source is unavailable (no network, GitHub rate limit, the registry doesn't
answer), use the fallbacks in [references/sources.md](references/sources.md). Never make up
results in place of a source that failed.

## Step 4. Vet the candidates

Shortlist up to 6 plausible candidates and check each one:

- **Coverage:** which need it covers, fully or partly. Don't recommend overlapping
  candidates together; pick the best one.
- **Author:** the service's own vendor (a `github.com/figma/…` repository, a registry name on
  the vendor's domain such as `com.figma.mcp/mcp`) beats an Anthropic catalog entry by a third
  party, which beats an unknown personal repository. A catalog tells you who runs the catalog,
  not who wrote the plugin. The install count (`installs`) is an extra signal, not a
  substitute for checking.
- **Freshness:** the last update. Flag more than 12 months without changes; drop `archived`,
  `deprecated` and placeholder listings.
- **Permissions:** for every plugin on the final list run
  `scout.py inspect <name@marketplace | github-url | owner/repo>`. It shows hooks, local and
  remote MCP servers, executables, skills' `allowed-tools`, requested tokens, the last change
  and stars. For MCP servers the permissions are in the `scout.py mcp` output (remote server,
  local package, required secrets); `scout.py inspect <registry name>` adds the repository's
  stars and activity.

Warn (⚠) when a tool runs commands through hooks on every action, starts a local process
with shell or file access, asks for broad OAuth access (all mail, the whole drive, write
access) or a broadly scoped token, or when the author is unknown or the source is doubtful
(few stars, no license, stale, installs through `curl | sh`, a package name that doesn't
match the repository). Describe what a hook or a script does only from what you actually
read: if all you know is the file name, say which script runs and when ("runs
`hooks/session-start.mjs` at every session start"), not what you guess it does. Rules:
[references/evaluation.md](references/evaluation.md).

## Step 5. Answer

At most 5 recommendations, from most to least useful. Keep it short, write in the user's
language and start straight with the first section, without a preamble. Skip empty sections.
Don't retell the search or list rejected candidates; the exception is an obvious option
rejected for its permissions or a doubtful source, which gets one ⚠ line. If a source didn't
answer, say so in one line.

Section headings, in the user's language:

| English | Russian |
| --- | --- |
| **Already available** | **Уже есть и пригодится** |
| **Worth installing** | **Стоит поставить** |
| **Not found** | **Не найдено** |

For any other language, translate the English headings.

```
**Already available**
- **<name>** — <what it's for in this task>

**Worth installing**
1. **<name>** · <skill | plugin | MCP> — <what it gives this task>
   <link> · <author>, updated <date>
   `<install command>`
   ⚠ <warning, only if there is one>

**Not found**
- <part of the task> — <how to cover it without a tool>

Which ones should I install? Reply with the numbers — nothing gets installed without your confirmation.
```

In Russian the closing line is: «Что поставить? Напиши номера — без твоего подтверждения
ничего не устанавливаю.»

Rules:

- Take names, links, versions, dates and commands only from tool output in this session. If
  you didn't verify it, don't write it. If an install command couldn't be confirmed, link the
  README instead of giving a command.
- A plugin installs with `/plugin install <name>@<marketplace>`, which opens a card with the
  plugin's components and a scope choice. If the marketplace isn't added yet, first
  `/plugin marketplace add <owner/repo>`. For MCP servers give the `claude mcp add …` line from
  the script output; for claude.ai connectors, "connect in Settings → Connectors".
- If the task needs no extra tools, answer in one line: "No extra tools needed: <why>".

## After the answer

Install only what the user picked, and only after they confirm:

- **Plugin.** In a terminal the user runs `/plugin install <id>` themselves. If they ask you
  to do it, run `claude plugin install <id>` (user scope by default) and ask them to run
  `/reload-plugins`. If the marketplace isn't added, run
  `claude plugin marketplace add <owner/repo>` first.
- **MCP.** Run `claude mcp add …`. Never ask for secrets in the chat: give the command with a
  placeholder and let the user paste the token. Servers with OAuth need a sign-in through
  `/mcp` after they are added.
- **claude.ai and Cowork.** If `SuggestPluginInstall` or `SuggestConnectors` exists, show the
  install card for what the user picked.
- Check the result (`claude plugin list`, `claude mcp list`) and return to the original task.
