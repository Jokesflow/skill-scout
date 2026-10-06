---
name: scout
description: Find the skills, plugins and MCP servers a task needs, e.g. /scout landing page from a Figma mockup in Next.js
argument-hint: <task description>
disable-model-invocation: true
---

The user ran `/scout`. Task: $ARGUMENTS

Use the Skill tool to invoke `skill-scout:skill-scout` and pass the task text as `args`. This
is an explicit request, so run its full mode. If the Skill tool is unavailable, read
`${CLAUDE_PLUGIN_ROOT}/skills/skill-scout/SKILL.md` and follow it.

If the task above is empty, take it from the user's recent messages. If there is no task
there either, ask in one sentence, in the user's language, what they need to do and what the
result should be.
